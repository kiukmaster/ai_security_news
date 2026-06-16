"""증분 수집 상태 관리 — data/latest.md 읽기/쓰기.

latest.md 는 사람이 읽을 수 있는 마크다운 표 + 기계가 읽는 JSON 블록을
함께 담습니다. 다음 실행 시 JSON 블록의 '이미 본 항목 id'를 비교해
새 항목만 골라냅니다.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LATEST_MD = DATA_DIR / "latest.md"

MAX_IDS_PER_FEED = 300  # 피드당 보관하는 '이미 본 항목' id 개수 상한

_JSON_START = "<!-- STATE_JSON_START -->"
_JSON_END = "<!-- STATE_JSON_END -->"
_JSON_RE = re.compile(
    re.escape(_JSON_START) + r"\s*```json\s*(.*?)\s*```\s*" + re.escape(_JSON_END),
    re.S,
)


def _empty_state():
    return {"last_run": None, "last_report": None, "feeds": {}}


def load_state():
    """latest.md에서 상태를 읽어옴. 없거나 손상되면 빈 상태 반환."""
    if not LATEST_MD.exists():
        return _empty_state()
    try:
        text = LATEST_MD.read_text(encoding="utf-8")
    except OSError:
        return _empty_state()
    m = _JSON_RE.search(text)
    if not m:
        return _empty_state()
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return _empty_state()
    state = _empty_state()
    state.update(data)
    state.setdefault("feeds", {})
    return state


def seen_ids(state, feed_url):
    return set(state.get("feeds", {}).get(feed_url, {}).get("ids", []))


def last_max_date(state, feed_url):
    """피드별로 마지막에 본 가장 최신 발행시각(없으면 None)."""
    raw = state.get("feeds", {}).get(feed_url, {}).get("last_max_date")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def update_feed(state, feed_url, current_ids, max_date=None):
    """이번 실행 결과를 상태에 병합.

    - current_ids : 날짜 없는 항목의 중복 제거용 id 집합(최신 우선, 상한 적용)
    - max_date    : 이번에 본 가장 최신 발행시각(증분 기준점). 더 큰 값만 유지.
    """
    feeds = state.setdefault("feeds", {})
    entry = feeds.setdefault(feed_url, {"ids": []})
    merged = list(dict.fromkeys(list(current_ids) + entry.get("ids", [])))
    entry["ids"] = merged[:MAX_IDS_PER_FEED]
    entry["last_seen"] = datetime.now().isoformat(timespec="seconds")

    if max_date is not None:
        prev = last_max_date(state, feed_url)
        keep = max_date if (prev is None or max_date > prev) else prev
        entry["last_max_date"] = keep.isoformat()


def _markdown(state, feed_reports):
    last_run = state.get("last_run") or "-"
    last_report = state.get("last_report") or "-"
    lines = [
        "# 📌 수집 상태 기록 (latest.md)",
        "",
        "> 이 파일은 프로그램이 **자동으로 관리**합니다. 직접 수정하지 마세요.",
        "> 다음 실행 시 아래 기록된 지점 **이후의 새 정보만** 수집합니다.",
        "",
        f"- 🕒 마지막 실행: `{last_run}`",
        f"- 📄 마지막 보고서: `{last_report}`",
        "",
        "## 소스별 마지막 확인 지점",
        "",
        "| 소스 | 카테고리 | 이번 신규 | 마지막 확인 기사 | 상태 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for r in feed_reports:
        title = (r.get("last_title") or "-").replace("|", "/")
        if len(title) > 60:
            title = title[:60] + "…"
        lines.append(
            f"| {r['name']} | {r.get('category', '-')} | {r.get('new_count', 0)} | {title} | {r.get('status', '-')} |"
        )
    lines += ["", "---", "", _JSON_START, "```json"]
    lines.append(json.dumps(state, ensure_ascii=False, indent=2))
    lines += ["```", _JSON_END, ""]
    return "\n".join(lines)


def save_state(state, feed_reports):
    """상태를 latest.md로 저장."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now().isoformat(timespec="seconds")
    LATEST_MD.write_text(_markdown(state, feed_reports), encoding="utf-8")
    return LATEST_MD
