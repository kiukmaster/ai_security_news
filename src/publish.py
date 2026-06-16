"""생성된 보고서를 GitHub Pages용 공개 폴더(docs/)로 발행.

- docs/reports/ 에 그날의 보고서를 복사
- docs/index.html 에 '오늘의 브리핑 + 지난 보고서 목록'을 모바일 친화적으로 생성
- docs/.nojekyll 로 GitHub Pages의 Jekyll 처리를 비활성화

폰에서는 Pages 루트(index.html)만 북마크해 두면 항상 최신 보고서로 이동할 수 있습니다.
"""

import html
import re
import shutil
from datetime import datetime
from pathlib import Path

_NAME_RE = re.compile(r"report_(\d{4}-\d{2}-\d{2})(?:_(\d{4}))?\.html$")


def _label(name):
    """파일명 → 사람이 읽는 라벨/정렬키. ('2026-06-16 09:30', sortkey)."""
    m = _NAME_RE.search(name)
    if not m:
        return name, name
    date, hhmm = m.group(1), m.group(2)
    if hhmm:
        return f"{date} {hhmm[:2]}:{hhmm[2:]}", f"{date}_{hhmm}"
    return date, f"{date}_0000"


def _index_html(reports):
    """reports: 최신순 정렬된 Path 리스트."""
    if reports:
        latest = reports[0]
        l_label, _ = _label(latest.name)
        latest_html = (
            f'<a class="latest" href="reports/{html.escape(latest.name)}">'
            f'<span class="tag">오늘의 브리핑</span>'
            f'<span class="big">📰 {html.escape(l_label)}</span>'
            f'<span class="go">열기 →</span></a>'
        )
    else:
        latest_html = '<p class="empty">아직 보고서가 없습니다.</p>'

    past = []
    for p in reports[1:]:
        label, _ = _label(p.name)
        past.append(f'<a class="past" href="reports/{html.escape(p.name)}">🗂️ {html.escape(label)}</a>')
    past_title = '<div class="section-title">지난 보고서</div>' if past else ""
    past_html = "".join(past)

    updated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0f1318">
<title>보안 · AI 데일리 브리핑</title>
<style>
:root{{color-scheme:light dark;}}
*{{box-sizing:border-box;}}
body{{margin:0;background:#0f1318;color:#e7ebf0;min-height:100vh;
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Malgun Gothic",Roboto,sans-serif;}}
.wrap{{max-width:640px;margin:0 auto;padding:22px 16px 60px;}}
h1{{font-size:21px;margin:6px 0 2px;}}
.sub{{color:#9aa4b1;font-size:13px;margin:0 0 20px;}}
a{{text-decoration:none;color:inherit;display:block;}}
.latest{{background:linear-gradient(135deg,#1d4ed8,#3b66f5);border-radius:16px;
  padding:20px;margin-bottom:18px;box-shadow:0 6px 20px rgba(59,102,245,.35);}}
.latest .tag{{display:inline-block;background:rgba(255,255,255,.2);color:#fff;
  font-size:12px;padding:3px 10px;border-radius:999px;margin-bottom:10px;}}
.latest .big{{display:block;font-size:22px;font-weight:700;color:#fff;}}
.latest .go{{display:block;margin-top:10px;color:#dbe4ff;font-size:14px;}}
.section-title{{font-size:13px;color:#9aa4b1;margin:18px 4px 8px;}}
.past{{background:#171c23;border:1px solid #262d36;border-radius:12px;
  padding:14px 16px;margin-bottom:10px;font-size:15px;}}
.past:hover,.latest:hover{{filter:brightness(1.08);}}
.empty{{color:#9aa4b1;text-align:center;padding:40px 0;}}
.foot{{color:#5b6470;font-size:12px;text-align:center;margin-top:28px;}}
</style>
</head>
<body>
<div class="wrap">
  <h1>🛰️ 보안 · AI 데일리 브리핑</h1>
  <p class="sub">최종 갱신: {html.escape(updated)}</p>
  {latest_html}
  {past_title}
  {past_html}
  <p class="foot">매일 아침 자동 생성 · GitHub Actions</p>
</div>
</body>
</html>"""


def publish(report_path, public_dir):
    """report_path 보고서를 public_dir(docs)로 발행하고 index.html 경로를 반환."""
    public = Path(public_dir)
    rep_dir = public / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)

    src = Path(report_path)
    if src.exists():
        shutil.copyfile(src, rep_dir / src.name)

    reports = sorted(rep_dir.glob("report_*.html"), key=lambda p: _label(p.name)[1], reverse=True)
    (public / "index.html").write_text(_index_html(reports), encoding="utf-8")
    (public / ".nojekyll").write_text("", encoding="utf-8")
    return public / "index.html"
