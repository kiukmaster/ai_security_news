"""전체 파이프라인 오케스트레이션.

run() 흐름:
  1) latest.md 상태 로드
  2) 각 피드 수집 → 이미 본 항목 제외(증분)
  3) 휴리스틱 팩트체크
  4) 반응형 HTML 보고서 생성
  5) latest.md 상태 갱신(다음 실행 기준점)

progress_cb(current, total) / log_cb(message) 콜백으로 GUI/콘솔에 진행상황 전달.
"""

from datetime import datetime
from pathlib import Path

import collector
import daterange
import factcheck
import feeds as feeds_mod
import report as report_mod
import state as state_mod

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "data" / "reports"

# 한 번 실행에서 피드당 보고서에 싣는 신규 항목 최대 수.
# (나머지 신규도 '이미 봄'으로 기록되어 다음날 중복 노출되지 않습니다.)
MAX_NEW_PER_FEED = 40

# 헤드라인(꼭 읽어야 할 글) 개수
HEADLINE_COUNT = 6


def _newest_first(entries):
    from datetime import datetime, timezone
    far_past = datetime.min.replace(tzinfo=timezone.utc)
    return sorted(entries, key=lambda e: e.get("published") or far_past, reverse=True)


def _build_stats(entries, feed_reports, collect_date, headlines):
    cats, tiers = {}, {"high": 0, "medium": 0, "low": 0}
    for e in entries:
        cats[e.get("category", "etc")] = cats.get(e.get("category", "etc"), 0) + 1
        tiers[e.get("tier", "low")] = tiers.get(e.get("tier", "low"), 0) + 1
    return {
        "total": len(entries),
        "categories": cats,
        "tiers": tiers,
        "feed_reports": feed_reports,
        "collect_date": collect_date,
        "headlines": headlines,
    }


def run(progress_cb=None, log_cb=None):
    def log(msg):
        if log_cb:
            log_cb(msg)

    def progress(cur, total):
        if progress_cb:
            progress_cb(cur, total)

    st = state_mod.load_state()
    cutoff, day_end = daterange.day_window()
    collect_date = cutoff.strftime("%Y-%m-%d")
    last_run = st.get("last_run")
    if last_run:
        log(f"이전 실행: {last_run} — 그 이후의 새 정보만 수집합니다.")
    else:
        log("첫 실행입니다. 각 소스의 현재 항목을 기준점으로 수집합니다.")
    log(f"수집 대상일: {collect_date} (해당 날짜 00:00~24:00 발행분).")

    all_feeds = feeds_mod.DEFAULT_FEEDS
    total = len(all_feeds)
    log(f"총 {total}개 소스에서 수집 시작.")

    new_entries = []
    feed_reports = []
    for idx, feed in enumerate(all_feeds, 1):
        log(f"[{idx}/{total}] 수집 중: {feed['name']}")
        progress(idx - 1, total)

        entries, err = collector.collect(feed)
        if err:
            log(f"    ⚠️ 실패 — {err}")
            feed_reports.append({
                "name": feed["name"], "category": feed["category"],
                "new_count": 0, "last_title": "-", "status": f"실패: {err[:50]}",
            })
            continue

        seen = state_mod.seen_ids(st, feed["url"])
        last_max = state_mod.last_max_date(st, feed["url"])
        run_max = last_max
        use_dates = feed.get("dated", True)
        fresh_list = []
        undated = 0
        for e in entries:
            pub = e.get("published")
            if not use_dates:
                # 인기순 소스(신기술 등): 날짜 창 대신 '처음 보는 항목'만 누적
                if e["id"] not in seen:
                    fresh_list.append(e)
                continue
            if pub is not None:
                # 대상일 하루 안 + 증분(지난 실행 이후) 둘 다 만족해야 신규
                if cutoff <= pub < day_end and (last_max is None or pub > last_max):
                    fresh_list.append(e)
                if run_max is None or pub > run_max:
                    run_max = pub
            else:
                # 날짜가 없으면 '대상일' 발행 여부를 보장할 수 없어 제외
                undated += 1

        # 신기술·CVE는 인기/심각도(rank) 높은 순, 그 외는 최신순으로 정렬
        if feed.get("category") in ("tech", "vuln"):
            fresh = sorted(fresh_list, key=lambda e: e.get("rank", -1), reverse=True)
        else:
            fresh = _newest_first(fresh_list)
        capped = fresh[:feed.get("max_new", MAX_NEW_PER_FEED)]
        new_entries.extend(capped)
        # 발행시각 기준점(run_max)과 id 집합을 기록 → 다음 실행 때 그 이후만 수집
        state_mod.update_feed(st, feed["url"], [e["id"] for e in entries], run_max)
        extra = len(fresh) - len(capped)
        scope = f"{collect_date} " if use_dates else ""
        msg = f"    → 전체 {len(entries)}건 중 {scope}신규 {len(fresh)}건"
        if extra:
            msg += f" (상위 {len(capped)}건만 게재, {extra}건 생략)"
        if undated:
            msg += f" / 날짜없음 {undated}건 제외"
        log(msg)

        feed_reports.append({
            "name": feed["name"], "category": feed["category"],
            "new_count": len(capped),
            "last_title": entries[0]["title"] if entries else "-",
            "status": "정상",
        })

    progress(total, total)
    log(f"수집 완료 — 신규 항목 {len(new_entries)}건. 팩트체크 분석 중…")
    factcheck.analyze(new_entries)

    headlines = factcheck.pick_headlines(new_entries, HEADLINE_COUNT)
    log(f"헤드라인(꼭 읽어야 할 글) {len(headlines)}건 선별 완료.")

    generated_at = datetime.now().astimezone()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    # 파일명은 '수집 대상일' 기준(생성 시각이 자정을 넘겨도 뉴스 날짜와 일치)
    report_path = REPORTS_DIR / f"report_{collect_date}.html"
    if report_path.exists():
        report_path = REPORTS_DIR / f"report_{collect_date}_{generated_at:%H%M}.html"

    stats = _build_stats(new_entries, feed_reports, collect_date, headlines)
    report_mod.generate(new_entries, stats, report_path, generated_at)
    log(f"보고서 생성 완료 → {report_path.name}")

    st["last_report"] = str(report_path.relative_to(BASE_DIR)).replace("\\", "/")
    state_mod.save_state(st, feed_reports)
    log("상태 기록(latest.md) 갱신 완료.")

    return {
        "report_path": report_path,
        "new_count": len(new_entries),
        "stats": stats,
        "feed_reports": feed_reports,
    }
