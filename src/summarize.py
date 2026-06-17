"""Gemini API로 기사별 한국어 요약 생성 (Python 표준 라이브러리만 사용).

API 키는 코드에 하드코딩하지 않고 환경변수에서 읽습니다.
  - 로컬:       set/`$env:` 또는 .env 로 GEMINI_API_KEY 설정
  - GitHub:     저장소 Secret(GEMINI_API_KEY)을 워크플로 env로 주입

키가 없으면 요약을 건너뛰고 원문 발췌를 그대로 사용하므로,
키가 없어도 프로그램은 정상 동작합니다(무료 티어 한도 초과/오류도 안전 폴백).
"""

import concurrent.futures
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.request

API_ENV = "GEMINI_API_KEY"
# 환경변수 GEMINI_MODEL 로 덮어쓸 수 있음(빈 값이면 아래 기본값 사용)
MODEL = os.environ.get("GEMINI_MODEL") or "gemini-3.1-flash-lite"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 유료 티어 기준 병렬 처리. 동시 요청 수(무료 티어면 1~2로 낮추세요).
CONCURRENCY = int(os.environ.get("SUMMARY_CONCURRENCY", "8"))
TIMEOUT = 30
MAX_RETRY = 4        # 429/일시오류 시 지수 백오프 재시도


def available():
    return bool(os.environ.get(API_ENV))


def _load_dotenv():
    """프로젝트 루트의 .env가 있으면 GEMINI_* 키를 환경변수로 로드(로컬 편의)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def _call(prompt, key):
    url = ENDPOINT.format(model=MODEL) + f"?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 256},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        data = json.loads(resp.read())
    for cand in data.get("candidates", []):
        parts = cand.get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        if text:
            return text
    return ""


def _prompt(entry):
    title = entry.get("title", "")
    desc = entry.get("summary", "")
    return (
        "다음은 보안/AI 분야의 뉴스 또는 논문입니다. 한국어로 핵심만 2~3문장으로 요약하세요. "
        "과장 없이 사실 위주로, 무엇이 어떻게 중요한지 담되 군더더기·인사말은 빼고 요약문만 출력하세요.\n\n"
        f"제목: {title}\n내용: {desc}\n\n요약:"
    )


def _summarize_one(entry, key, log):
    for attempt in range(MAX_RETRY + 1):
        try:
            return _call(_prompt(entry), key)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < MAX_RETRY:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                back = int(retry_after) if (retry_after and retry_after.isdigit()) \
                    else min(45, 4 * (2 ** attempt))
                time.sleep(back)
                continue
            raise
        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError):
            if attempt < MAX_RETRY:
                time.sleep(5)
                continue
            raise


def summarize_entries(entries, log=lambda m: None, max_items=300):
    """entries 각 항목의 summary를 AI 요약으로 교체. 성공 건수 반환.

    실패/키 없음 시 해당 항목은 원문 발췌를 그대로 유지한다.
    """
    _load_dotenv()
    key = os.environ.get(API_ENV)
    if not key:
        log("GEMINI_API_KEY 미설정 — AI 요약 건너뜀(원문 발췌 표시).")
        return 0

    targets = [e for e in entries if e.get("summary")][:max_items]
    total = len(targets)
    if not total:
        return 0
    workers = max(1, min(CONCURRENCY, total))
    log(f"AI 요약 시작 ({MODEL}) — 대상 {total}건, 동시 {workers}개 병렬 처리…")

    counter = {"n": 0, "ok": 0}
    lock = threading.Lock()

    def work(e):
        try:
            summary = _summarize_one(e, key, log)
            ok = bool(summary)
            if ok:
                e["summary"] = summary
                e["ai_summary"] = True
        except Exception as ex:  # noqa: BLE001 — 한 건 실패가 전체를 막지 않도록
            log(f"    요약 실패({e.get('title', '')[:28]}…): {ex}")
            ok = False
        with lock:
            counter["n"] += 1
            if ok:
                counter["ok"] += 1
            n = counter["n"]
        if n % 20 == 0 or n == total:
            log(f"    AI 요약 진행 {n}/{total}…")
        return ok

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, targets))

    log(f"AI 요약 완료: {counter['ok']}/{total}건.")
    return counter["ok"]
