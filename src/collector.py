"""RSS / Atom / RDF 피드 수집 및 파싱 (Python 표준 라이브러리만 사용).

외부 패키지(feedparser 등)에 의존하지 않으므로 별도 설치가 필요 없습니다.
네트워크 오류·파싱 오류는 예외 대신 (entries, error) 형태로 반환하여
한 소스가 실패해도 전체 수집이 멈추지 않도록 합니다.
"""

import hashlib
import html as _html
import json
import re
import socket
import ssl
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

USER_AGENT = "Mozilla/5.0 (compatible; DailyBriefBot/1.0; local research use)"
TIMEOUT = 15  # 초

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


class FeedError(Exception):
    """피드 수집/파싱 실패."""


# --------------------------------------------------------------------------- #
# 네트워크
# --------------------------------------------------------------------------- #
def _request(url):
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )


def fetch(url):
    """피드 URL의 원본 바이트를 반환. 실패 시 FeedError.

    일부 환경에서는 로컬 CA 번들 누락으로 공개 피드(arXiv 등)의 인증서 검증이
    실패할 수 있습니다. 이 경우(공격이 아닌 환경 문제)에 한해 1회 검증을
    우회해 재시도합니다. 수집 대상은 공개 뉴스/논문 메타데이터입니다.
    """
    try:
        with urllib.request.urlopen(_request(url), timeout=TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise FeedError(f"HTTP {e.code}")
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        reason = getattr(e, "reason", e)
        # SSL 인증서 검증 실패(URLError로 감싸져 옴)는 로컬 CA 문제일 수 있으므로
        # 공개 피드에 한해 검증을 우회해 1회 재시도한다.
        if isinstance(reason, ssl.SSLCertVerificationError) or isinstance(e, ssl.SSLCertVerificationError):
            try:
                ctx = ssl._create_unverified_context()
                with urllib.request.urlopen(_request(url), timeout=TIMEOUT, context=ctx) as resp:
                    return resp.read()
            except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e2:
                raise FeedError(f"SSL 검증 실패 후 재시도 실패: {getattr(e2, 'reason', e2)}")
        raise FeedError(str(reason))


# --------------------------------------------------------------------------- #
# 파싱 헬퍼
# --------------------------------------------------------------------------- #
def _local(tag):
    """네임스페이스를 제거한 로컬 태그명."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _text(el):
    return (el.text or "").strip() if el is not None else ""


def _find(parent, name):
    """직계 자식 중 로컬 태그명이 name인 첫 요소."""
    for child in parent:
        if _local(child.tag) == name:
            return child
    return None


def _find_any(parent, *names):
    """여러 후보 태그명 중 먼저 발견되는 요소(없으면 None).

    주의: ElementTree에서 자식이 없는 Element는 bool()이 False이므로
    `_find(a) or _find(b)` 식으로 쓰면 안 된다(빈 요소를 놓침). 반드시 이 함수를 사용.
    """
    for name in names:
        el = _find(parent, name)
        if el is not None:
            return el
    return None


def _clean(raw, limit=400):
    """HTML 태그 제거 + 엔티티 복원 + 공백 정리 + 길이 제한."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = _html.unescape(text)
    text = _WS_RE.sub(" ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _parse_date(value):
    """RFC822(pubDate) 또는 ISO8601(Atom) 날짜 문자열 → aware datetime 또는 None."""
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt is not None:
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _hash_id(seed):
    return hashlib.sha1(seed.encode("utf-8", "ignore")).hexdigest()


def _parse_rss_item(item):
    title = _text(_find(item, "title"))
    link_el = _find(item, "link")
    link = _text(link_el)
    if not link and link_el is not None:
        link = link_el.get("href", "")
    guid = _text(_find(item, "guid")) or link or title
    desc = _text(_find(item, "description")) or _text(_find(item, "encoded"))
    date_el = _find_any(item, "pubDate", "date", "published", "updated")
    if not title and not link:
        return None
    return {
        "id": _hash_id(guid),
        "title": title or "(제목 없음)",
        "link": link,
        "summary": _clean(desc),
        "published": _parse_date(_text(date_el)),
    }


def _parse_atom_entry(entry):
    title = _text(_find(entry, "title"))
    link = ""
    for child in entry:
        if _local(child.tag) == "link":
            rel = child.get("rel", "alternate")
            href = child.get("href", "")
            if href and (rel == "alternate" or not link):
                link = href
    aid = _text(_find(entry, "id")) or link or title
    summary = _text(_find(entry, "summary")) or _text(_find(entry, "content"))
    date_el = _find_any(entry, "updated", "published", "issued", "date")
    if not title and not link:
        return None
    return {
        "id": _hash_id(aid),
        "title": title or "(제목 없음)",
        "link": link,
        "summary": _clean(summary),
        "published": _parse_date(_text(date_el)),
    }


_DECL_RE = re.compile(rb"^\s*<\?xml[^>]*\?>")
_ENC_RE = re.compile(rb'encoding=["\']([\w\-]+)["\']', re.I)


def _xml_root(content):
    """바이트 → ElementTree 루트. EUC-KR 등 멀티바이트 인코딩 피드도 처리.

    expat이 직접 지원하지 않는 인코딩(예: 한국 매체의 euc-kr)은 우리가 직접
    디코딩한 뒤 XML 선언을 제거하고 유니코드 문자열로 파싱한다.
    """
    try:
        return ET.fromstring(content)
    except (ET.ParseError, ValueError, UnicodeDecodeError):
        pass
    m = _ENC_RE.search(content[:200])
    declared = m.group(1).decode("ascii", "ignore") if m else None
    for enc in (declared, "utf-8", "euc-kr", "cp949"):
        if not enc:
            continue
        try:
            text = content.decode(enc, "replace")
        except (LookupError, UnicodeDecodeError):
            continue
        text = _DECL_RE.sub(b"", text.encode("utf-8")).decode("utf-8")  # 선언 제거
        try:
            return ET.fromstring(text)
        except (ET.ParseError, ValueError):
            continue
    raise FeedError("XML 파싱 실패(지원하지 않는 인코딩)")


def parse_feed(content):
    """원본 바이트를 항목 리스트로 변환. RSS2.0 / Atom / RDF(arXiv) 지원."""
    root = _xml_root(content)

    entries = []
    if _local(root.tag) == "feed":  # Atom
        for child in root:
            if _local(child.tag) == "entry":
                parsed = _parse_atom_entry(child)
                if parsed:
                    entries.append(parsed)
    else:  # RSS 2.0 또는 RDF — item 요소를 전부 탐색
        for el in root.iter():
            if _local(el.tag) == "item":
                parsed = _parse_rss_item(el)
                if parsed:
                    entries.append(parsed)
    return entries


# --------------------------------------------------------------------------- #
# 공개 API
# --------------------------------------------------------------------------- #
def _attach_meta(entries, feed):
    for en in entries:
        en.setdefault("source", feed["name"])
        en.setdefault("category", feed["category"])
        en.setdefault("trust", feed["trust"])
        en.setdefault("feed_url", feed["url"])
    return entries


_SEV_KO = {"CRITICAL": "심각", "HIGH": "높음", "MEDIUM": "중간", "LOW": "낮음"}


def _cvss(metrics):
    """NVD metrics → (baseScore, baseSeverity). CVSS 4.0 > 3.1 > 3.0 > 2.0 우선."""
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30"):
        arr = metrics.get(key)
        if arr:
            cd = arr[0].get("cvssData", {})
            return cd.get("baseScore"), cd.get("baseSeverity")
    arr = metrics.get("cvssMetricV2")
    if arr:
        cd = arr[0].get("cvssData", {})
        return cd.get("baseScore"), arr[0].get("baseSeverity")
    return None, None


def _collect_nvd(feed):
    """NVD에서 '어제(로컬 기준) 발행' CVE를 수집. 링크는 cvedetails.com로 연결.

    cvedetails.com이 자동 접근을 차단(403)하므로, 동일 원본인 NVD JSON API에서
    어제 0시~오늘 0시(로컬) 사이 발행분만 정확히 가져온다.
    """
    mid = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    start = (mid - timedelta(days=1)).astimezone(timezone.utc)
    end = mid.astimezone(timezone.utc)
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S.000")
    url = f"{feed['url']}?pubStartDate={fmt(start)}&pubEndDate={fmt(end)}&resultsPerPage=2000"

    try:
        raw = fetch(url)
        data = json.loads(raw)
    except FeedError as e:
        return [], str(e)
    except (json.JSONDecodeError, ValueError) as e:
        return [], f"NVD JSON 파싱 실패: {e}"

    entries = []
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        cid = cve.get("id")
        if not cid:
            continue
        descs = [d.get("value", "") for d in cve.get("descriptions", []) if d.get("lang") == "en"]
        score, sev = _cvss(cve.get("metrics", {}))
        sev_ko = _SEV_KO.get((sev or "").upper(), "등급미정")
        title = f"{cid} · {sev_ko}" + (f" {score}" if score is not None else "")
        entries.append({
            "id": _hash_id(cid),
            "title": title,
            "link": f"https://www.cvedetails.com/cve/{cid}/",
            "summary": _clean(descs[0] if descs else ""),
            "published": _parse_date(cve.get("published")),
            "rank": score if score is not None else -1,  # 정렬용(CVSS 점수)
        })
    return _attach_meta(entries, feed), None


# GitHub '신기술' 수집 파라미터
GITHUB_CREATED_DAYS = 14   # 최근 며칠 내 생성된 저장소를 대상으로
GITHUB_MIN_STARS = 10      # 최소 Star 수(노이즈 제거)


def _collect_github(feed):
    """최근 생성된 GitHub 저장소를 Star(인기) 많은 순으로 수집.

    '새롭게 생성된 기술'을 인기순으로 보여주기 위해 최근 N일 생성 + Star 정렬을 사용.
    날짜 창이 아닌 id 기반 중복 제거(pipeline의 dated=False)로 이미 본 것은 재노출하지 않음.
    """
    import urllib.parse
    since = (datetime.now() - timedelta(days=GITHUB_CREATED_DAYS)).strftime("%Y-%m-%d")
    q = urllib.parse.quote(f"created:>={since} stars:>={GITHUB_MIN_STARS}")
    url = f"{feed['url']}?q={q}&sort=stars&order=desc&per_page=50"
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout,
            ConnectionError, OSError, ValueError, json.JSONDecodeError) as e:
        return [], str(getattr(e, "reason", e))

    entries = []
    for it in data.get("items", []):
        name = it.get("full_name")
        if not name:
            continue
        stars = it.get("stargazers_count", 0)
        lang = it.get("language")
        title = f"{name} · ⭐{stars:,}" + (f" · {lang}" if lang else "")
        entries.append({
            "id": _hash_id("gh:" + name),
            "title": title,
            "link": it.get("html_url", ""),
            "summary": _clean(it.get("description") or ""),
            "published": _parse_date(it.get("created_at")),
            "rank": stars,  # 정렬용(Star 수)
        })
    return _attach_meta(entries, feed), None


def collect(feed):
    """피드 하나를 수집. (entries, error_or_None) 반환.

    feed["kind"]가 "nvd"면 NVD(CVE) 전용 핸들러를, 그 외에는 RSS/Atom 파서를 사용.
    각 entry에는 source / category / trust / feed_url 메타데이터가 부착됩니다.
    """
    kind = feed.get("kind")
    if kind == "nvd":
        return _collect_nvd(feed)
    if kind == "github":
        return _collect_github(feed)

    try:
        content = fetch(feed["url"])
        entries = parse_feed(content)
    except FeedError as e:
        return [], str(e)
    return _attach_meta(entries, feed), None
