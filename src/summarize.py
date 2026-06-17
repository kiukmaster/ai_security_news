"""Gemini API로 기사별 한국어 요약 생성 (Python 표준 라이브러리만 사용).

API 키는 코드에 하드코딩하지 않고 환경변수에서 읽습니다.
  - 로컬:       set/`$env:` 또는 .env 로 GEMINI_API_KEY 설정
  - GitHub:     저장소 Secret(GEMINI_API_KEY)을 워크플로 env로 주입

키가 없으면 요약을 건너뛰고 원문 발췌를 그대로 사용하므로,
키가 없어도 프로그램은 정상 동작합니다(무료 티어 한도 초과/오류도 안전 폴백).
"""

import json
import os
import socket
import time
import urllib.error
import urllib.request

API_ENV = "GEMINI_API_KEY"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# 무료 티어 한도(분당 15요청) 대응: 15건 처리 후 70초 대기 → 다시 15건 …
BATCH_SIZE = 15
BATCH_PAUSE = 70     # 초
TIMEOUT = 30
MAX_RETRY = 2


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
                back = 20 * (attempt + 1)
                log(f"    속도제한/일시오류({e.code}) — {back}s 대기 후 재시도")
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
    log(f"AI 요약 시작 ({MODEL}) — 대상 {total}건. "
        f"분당 {BATCH_SIZE}건씩 처리(한도 도달 시 {BATCH_PAUSE}초 대기).")

    done = 0
    for i, e in enumerate(targets):
        # 직전 배치(15건)를 채웠으면 다음 요청 전에 한도 회복까지 대기
        if i > 0 and i % BATCH_SIZE == 0:
            log(f"    분당 한도({BATCH_SIZE}건) 도달 — {BATCH_PAUSE}초 대기 후 계속… "
                f"({i}/{total})")
            time.sleep(BATCH_PAUSE)
        try:
            summary = _summarize_one(e, key, log)
            if summary:
                e["summary"] = summary
                e["ai_summary"] = True
                done += 1
        except Exception as ex:  # noqa: BLE001 — 한 건 실패가 전체를 막지 않도록
            log(f"    요약 실패({e.get('title', '')[:28]}…): {ex}")

    log(f"AI 요약 완료: {done}/{total}건.")
    return done
