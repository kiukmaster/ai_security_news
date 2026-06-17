"""수집·팩트체크 결과를 모바일/PC 겸용 반응형 HTML 보고서로 출력."""

import html
from datetime import datetime, timezone

import feeds as feeds_mod
from factcheck import TIER_LABELS

_TIER_ORDER = {"high": 0, "medium": 1, "low": 2}


def _esc(s):
    return html.escape(s or "", quote=True)


def _fmt_dt(dt):
    if not dt:
        return ""
    try:
        local = dt.astimezone()
    except (ValueError, OSError):
        local = dt
    return local.strftime("%Y-%m-%d %H:%M")


def _card(entry, rank_no=None, badge=None):
    tier = entry.get("tier", "low")
    tier_label = TIER_LABELS.get(tier, tier)
    score = entry.get("score", 0)
    title = _esc(entry.get("title", ""))
    link = _esc(entry.get("link", ""))
    title_html = f'<a href="{link}" target="_blank" rel="noopener">{title}</a>' if link else title

    summary = _esc(entry.get("summary", ""))
    corrob = entry.get("corroborators", [])
    reasons = entry.get("reasons", [])
    when = _fmt_dt(entry.get("published"))

    chips = "".join(
        f'<span class="chip">{_esc(r)}</span>' for r in reasons
    )
    corrob_html = ""
    if corrob:
        names = ", ".join(_esc(c) for c in corrob)
        corrob_html = f'<div class="corrob">🔗 교차보도: {names}</div>'

    meta_bits = [f'<span class="source">{_esc(entry.get("source", ""))}</span>']
    if badge:
        meta_bits.insert(0, f'<span class="catbadge">{_esc(badge)}</span>')
    if when:
        meta_bits.append(f'<span class="when">{when}</span>')
    meta_html = " · ".join(meta_bits)

    rank_html = f'<span class="rankno">{rank_no}</span>' if rank_no else ""
    head_badge = f'<span class="badge tier-{tier}">{tier_label} · {score}</span>'
    sum_label = "🤖 AI 요약 보기" if entry.get("ai_summary") else "📄 원문 발췌 보기"

    return f"""
      <article class="card tier-{tier}">
        <div class="card-head">
          {rank_html}{head_badge}
          <div class="meta">{meta_html}</div>
        </div>
        <h3 class="title">{title_html}</h3>
        {f'<details class="sumbox"><summary class="sumtoggle">{sum_label}</summary><p class="summary">{summary}</p></details>' if summary else ''}
        {corrob_html}
        <div class="chips">{chips}</div>
      </article>"""


def _section(category, entries):
    label = feeds_mod.CATEGORY_LABELS.get(category, category)
    if category in ("tech", "vuln"):
        # 인기순/심각도순(rank 큰 값이 위로)
        entries = sorted(entries, key=lambda e: -(e.get("rank") if e.get("rank") is not None else -1))
    else:
        entries = sorted(
            entries,
            key=lambda e: (_TIER_ORDER.get(e.get("tier", "low"), 9), -e.get("score", 0)),
        )
    cards = "".join(_card(e) for e in entries)
    return f"""
    <section class="cat" id="cat-{_esc(category)}">
      <h2 class="cat-title">{label} <span class="count">{len(entries)}</span></h2>
      {cards}
    </section>"""


def _headline_section(headlines):
    label = feeds_mod.CATEGORY_LABELS.get("headline", "📌 헤드라인")
    items = sorted(headlines, key=lambda e: -e.get("impact", 0))
    cards = ""
    for i, e in enumerate(items, 1):
        cat_label = feeds_mod.CATEGORY_LABELS.get(e.get("category"), e.get("category", ""))
        cards += _card(e, rank_no=i, badge=cat_label)
    return f"""
    <section class="cat headline" id="cat-headline">
      <h2 class="cat-title">{label} <span class="count">{len(items)}</span></h2>
      <p class="cat-note">오늘 하루 중 중요도(교차보도·고위험 키워드·취약점 심각도 등)를 기준으로 자동 선별했습니다.</p>
      {cards}
    </section>"""


def _feed_status_table(feed_reports):
    rows = []
    for r in feed_reports:
        status = _esc(r.get("status", "-"))
        cls = "ok" if status == "정상" else "fail"
        rows.append(
            f'<tr class="{cls}"><td>{_esc(r["name"])}</td>'
            f'<td class="num">{r.get("new_count", 0)}</td>'
            f'<td>{status}</td></tr>'
        )
    return (
        '<table class="status"><thead><tr><th>소스</th><th>신규</th><th>상태</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def generate(entries, stats, out_path, generated_at):
    """보고서 HTML 파일을 생성하고 경로를 반환."""
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc).astimezone()
    date_str = generated_at.strftime("%Y년 %m월 %d일 (%H:%M)")

    by_cat = {}
    for e in entries:
        by_cat.setdefault(e.get("category", "etc"), []).append(e)

    headlines = stats.get("headlines", [])

    sections = _headline_section(headlines) if headlines else ""
    for cat in feeds_mod.CATEGORY_ORDER:
        if by_cat.get(cat):
            sections += _section(cat, by_cat[cat])
    for cat, items in by_cat.items():
        if cat not in feeds_mod.CATEGORY_ORDER and items:
            sections += _section(cat, items)

    if not entries:
        sections = (
            '<section class="cat"><p class="empty">해당 날짜에 새로 수집된 항목이 없습니다. '
            '잠시 후 다시 시도하거나 소스를 추가해 보세요.</p></section>'
        )

    tier_counts = stats.get("tiers", {})
    cat_counts = stats.get("categories", {})
    summary_chips = "".join(
        f'<span class="stat"><b>{cat_counts.get(c, 0)}</b> {feeds_mod.CATEGORY_LABELS.get(c, c)}</span>'
        for c in feeds_mod.CATEGORY_ORDER
    )
    tier_chips = (
        f'<span class="stat high"><b>{tier_counts.get("high", 0)}</b> 높음</span>'
        f'<span class="stat medium"><b>{tier_counts.get("medium", 0)}</b> 보통</span>'
        f'<span class="stat low"><b>{tier_counts.get("low", 0)}</b> 주의</span>'
    )

    # 클릭하면 해당 카테고리 섹션으로 이동하는 내비게이션(헤드라인 맨 앞)
    nav_chips = ""
    if headlines:
        nav_chips += (
            f'<a class="nav-chip cat-headline" href="#cat-headline">'
            f'{feeds_mod.CATEGORY_LABELS.get("headline", "헤드라인")} <b>{len(headlines)}</b></a>'
        )
    nav_chips += "".join(
        f'<a class="nav-chip cat-{_esc(c)}" href="#cat-{_esc(c)}">'
        f'{feeds_mod.CATEGORY_LABELS.get(c, c)} <b>{len(by_cat.get(c, []))}</b></a>'
        for c in feeds_mod.CATEGORY_ORDER if by_cat.get(c)
    )
    nav_html = f'<nav class="catnav">{nav_chips}</nav>' if nav_chips else ""

    status_table = _feed_status_table(stats.get("feed_reports", []))

    doc = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>보안·AI 데일리 브리핑 — {date_str}</title>
<style>
{_CSS}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>🛰️ 보안 · AI 데일리 브리핑</h1>
    <p class="date">📅 {_esc(stats.get('collect_date', ''))} 하루 동안 · 신규 {stats.get('total', 0)}건 · 생성 {date_str}</p>
    <div class="stats">{summary_chips}</div>
    <div class="stats tiers">{tier_chips}</div>
  </header>

  {nav_html}

  {sections}

  <details class="sources">
    <summary>📡 이번 수집 소스 현황 ({len(stats.get('feed_reports', []))}개)</summary>
    {status_table}
  </details>

  <footer class="foot">
    <p>본 보고서는 RSS/공식 피드를 자동 수집해 휴리스틱(교차출처·출처신뢰도) 방식으로 신뢰도를 추정합니다.
       점수는 보조 지표이며 최종 판단 전 원문 확인을 권장합니다.</p>
    <p class="gen">생성 시각: {generated_at.strftime('%Y-%m-%d %H:%M:%S %Z')}</p>
  </footer>
</div>
</body>
</html>"""

    out_path.write_text(doc, encoding="utf-8")
    return out_path


_CSS = """
:root{
  --bg:#f5f6f8; --card:#ffffff; --text:#1b1f24; --muted:#5b6470; --line:#e4e7eb;
  --accent:#3b66f5; --high:#137333; --high-bg:#e6f4ea; --medium:#9a6700;
  --medium-bg:#fff4d6; --low:#b3261e; --low-bg:#fce8e6;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#0f1318; --card:#171c23; --text:#e7ebf0; --muted:#9aa4b1; --line:#262d36;
    --accent:#6f8cff; --high:#6cd58a; --high-bg:#10301d; --medium:#e8c46a;
    --medium-bg:#332a10; --low:#f08a82; --low-bg:#3a1614;
  }
}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",Roboto,sans-serif;
  line-height:1.5;-webkit-text-size-adjust:100%;}
.wrap{max-width:860px;margin:0 auto;padding:16px;}
.top{padding:14px 4px 6px;}
.top h1{font-size:22px;margin:0 0 4px;}
.date{color:var(--muted);margin:0 0 12px;font-size:14px;}
.stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px;}
.stat{background:var(--card);border:1px solid var(--line);border-radius:999px;
  padding:4px 12px;font-size:13px;color:var(--muted);}
.stat b{color:var(--text);font-size:14px;}
.stat.high b{color:var(--high);} .stat.medium b{color:var(--medium);} .stat.low b{color:var(--low);}
.catnav{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px;
  padding:10px 4px;margin:0 -4px 4px;background:var(--bg);
  border-bottom:1px solid var(--line);}
.nav-chip{text-decoration:none;font-size:13px;color:var(--text);background:var(--card);
  border:1px solid var(--line);border-radius:999px;padding:6px 13px;white-space:nowrap;}
.nav-chip:hover{border-color:var(--accent);color:var(--accent);}
.nav-chip b{color:var(--accent);}
.nav-chip.cat-vuln{border-color:var(--low);}
.nav-chip.cat-vuln b{color:var(--low);}
.nav-chip.cat-headline{border-color:var(--accent);background:rgba(59,102,245,.12);}
.cat.headline .cat-title{border-bottom-color:var(--accent);}
.cat-note{font-size:12px;color:var(--muted);margin:-6px 0 12px;}
.cat.headline .card{border-left-color:var(--accent);}
.rankno{display:inline-flex;align-items:center;justify-content:center;
  width:22px;height:22px;border-radius:50%;background:var(--accent);color:#fff;
  font-size:12px;font-weight:700;margin-right:2px;}
.catbadge{background:var(--bg);border:1px solid var(--line);border-radius:6px;
  padding:1px 7px;font-size:11px;}
.cat{margin:22px 0 8px;scroll-margin-top:60px;}
.cat-title{font-size:17px;display:flex;align-items:center;gap:8px;
  border-bottom:2px solid var(--line);padding-bottom:6px;margin:0 0 12px;}
.count{font-size:13px;color:#fff;background:var(--accent);border-radius:999px;
  padding:1px 9px;font-weight:600;}
.card{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--line);
  border-radius:12px;padding:14px 16px;margin-bottom:12px;}
.card.tier-high{border-left-color:var(--high);}
.card.tier-medium{border-left-color:var(--medium);}
.card.tier-low{border-left-color:var(--low);}
.card-head{display:flex;flex-wrap:wrap;align-items:center;gap:8px;justify-content:space-between;}
.badge{font-size:12px;font-weight:700;border-radius:6px;padding:2px 8px;white-space:nowrap;}
.badge.tier-high{color:var(--high);background:var(--high-bg);}
.badge.tier-medium{color:var(--medium);background:var(--medium-bg);}
.badge.tier-low{color:var(--low);background:var(--low-bg);}
.meta{font-size:12px;color:var(--muted);}
.meta .source{font-weight:600;color:var(--text);}
.title{font-size:16px;margin:8px 0 6px;line-height:1.4;}
.title a{color:var(--text);text-decoration:none;}
.title a:hover{color:var(--accent);text-decoration:underline;}
.sumbox{margin:2px 0 8px;}
.sumtoggle{cursor:pointer;display:inline-block;font-size:12px;color:var(--accent);
  background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:3px 10px;
  list-style:none;user-select:none;}
.sumtoggle::-webkit-details-marker{display:none;}
.sumtoggle::marker{content:"";}
.sumbox[open] .sumtoggle{margin-bottom:6px;border-color:var(--accent);}
.summary{font-size:14px;color:var(--muted);margin:0 0 4px;}
.corrob{font-size:12px;color:var(--accent);margin:0 0 8px;}
.chips{display:flex;flex-wrap:wrap;gap:6px;}
.chip{font-size:11px;color:var(--muted);background:var(--bg);border:1px solid var(--line);
  border-radius:6px;padding:2px 7px;}
.empty{color:var(--muted);text-align:center;padding:30px 0;}
.sources{margin:24px 0;background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:10px 14px;}
.sources summary{cursor:pointer;font-weight:600;font-size:14px;}
table.status{width:100%;border-collapse:collapse;margin-top:10px;font-size:13px;}
table.status th,table.status td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);}
table.status td.num,table.status th:nth-child(2){text-align:right;}
table.status tr.fail td{color:var(--low);}
.foot{color:var(--muted);font-size:12px;margin:24px 0 40px;text-align:center;}
.foot .gen{opacity:.7;margin-top:6px;}
@media (max-width:520px){
  .top h1{font-size:19px;} .title{font-size:15px;} .wrap{padding:12px;}
}
"""
