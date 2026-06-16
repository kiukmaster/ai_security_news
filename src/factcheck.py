"""휴리스틱(규칙 기반) 팩트체크.

LLM/외부 API 없이 다음 신호로 각 항목의 신뢰도 점수(0~100)를 계산합니다.
  1) 출처 신뢰도        : 매체별 trust 값 (0~50점)
  2) 교차출처 보도       : 다른 매체가 같은 사건을 보도했는가 (0~35점)
  3) 원문 링크 존재      : 검증 가능한 원문 링크 (0~10점)
  4) 발행 시각 명시      : 날짜 메타데이터 존재 (0~5점)

점수에 따라 tier(high/medium/low)를 부여합니다. 이는 '자동 검증'이 아니라
'교차검증을 돕는 보조 지표'이며, 보고서에 근거(reasons)를 함께 표기합니다.
"""

import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+")

# 키워드 비교에서 제외할 흔한 단어
_STOP = set(
    """the a an of to in on for and or with at by from is are was were be as it its this
    that into over after new latest report says will can has have not you your we our using
    use how why what when who where amid via about than then their""".split()
)

TIER_LABELS = {
    "high": "신뢰도 높음",
    "medium": "신뢰도 보통",
    "low": "주의 필요",
}


def _keywords(title):
    words = [w.lower() for w in _WORD_RE.findall(title)]
    return {w for w in words if len(w) >= 3 and w not in _STOP}


def _score(entry):
    reasons = []
    score = 0.0

    # 1) 출처 신뢰도 (0~50)
    trust = float(entry.get("trust", 0.5))
    score += trust * 50
    reasons.append(f"출처 신뢰도 {int(round(trust * 100))}%")

    # 2) 교차출처 보도 (0~35)
    n = len(entry.get("corroborators", []))
    if n > 0:
        score += min(35, 12 + (n - 1) * 11)
        reasons.append(f"{n}개 타 매체 교차보도")
    else:
        reasons.append("단독 보도(교차출처 미발견)")

    # 3) 원문 링크 (0~10)
    if entry.get("link"):
        score += 10
        reasons.append("원문 링크 확인")
    else:
        reasons.append("원문 링크 없음")

    # 4) 발행 시각 (0~5)
    if entry.get("published"):
        score += 5
    else:
        reasons.append("발행 시각 불명")

    score = max(0, min(100, round(score)))
    if score >= 75:
        tier = "high"
    elif score >= 55:
        tier = "medium"
    else:
        tier = "low"
    return score, reasons, tier


def analyze(entries):
    """항목 리스트에 corroborators / score / reasons / tier 필드를 채워 반환."""
    for e in entries:
        e["_kw"] = _keywords(e.get("title", ""))

    for i, e in enumerate(entries):
        corrob = set()
        for j, other in enumerate(entries):
            if i == j or other["source"] == e["source"]:
                continue
            # 의미 있는 키워드 2개 이상 공유 → 같은 사건으로 간주
            if len(e["_kw"] & other["_kw"]) >= 2:
                corrob.add(other["source"])
        e["corroborators"] = sorted(corrob)
        e["score"], e["reasons"], e["tier"] = _score(e)

    for e in entries:
        e.pop("_kw", None)
    return entries


# --------------------------------------------------------------------------- #
# 헤드라인(꼭 읽어야 할 글) 선별
# --------------------------------------------------------------------------- #
# 제목에 등장하면 '중요/시급'으로 보는 고위험 키워드(소문자 부분일치)
_IMPACT_TERMS = (
    "zero-day", "0-day", "zeroday", "actively exploited", "exploited", "exploit",
    "rce", "remote code", "ransomware", "breach", "backdoor", "supply chain",
    "supply-chain", "emergency", "critical", "data leak", "leak", "hacked",
    "malware", "botnet", "spyware", "wormable", "patch now", "심각", "긴급", "제로데이",
)

# 카테고리별 '꼭 읽어야 함' 가중치
_CAT_WEIGHT = {"security": 12, "security_kr": 12, "vuln": 12, "ai": 6, "tech": 3, "research": 0}


def _impact(entry):
    """기사 중요도 점수(높을수록 헤드라인 후보)."""
    s = float(entry.get("score", 0)) * 0.4                       # 신뢰도/교차검증 기반 점수
    s += min(30, len(entry.get("corroborators", [])) * 10)        # 여러 매체 보도 = 큰 사건
    title = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
    hits = sum(1 for t in _IMPACT_TERMS if t in title)
    s += min(36, hits * 12)                                       # 고위험 키워드
    s += _CAT_WEIGHT.get(entry.get("category"), 0)                # 카테고리 가중치
    if entry.get("category") == "vuln":                           # 치명적 취약점은 필독
        rank = entry.get("rank") or 0
        if rank >= 9.0:
            s += 40
        elif rank >= 7.5:
            s += 22
    return s


def pick_headlines(entries, k=6):
    """중요도 상위 k건을 선별(같은 사건 중복은 제외)하여 반환."""
    ranked = sorted(entries, key=lambda e: -_impact(e))
    chosen, chosen_kw = [], []
    for e in ranked:
        kw = _keywords(e.get("title", ""))
        if any(len(kw & ck) >= 3 for ck in chosen_kw):  # 이미 뽑은 헤드라인과 같은 사건이면 건너뜀
            continue
        e["impact"] = round(_impact(e))
        e["is_headline"] = True
        chosen.append(e)
        chosen_kw.append(kw)
        if len(chosen) >= k:
            break
    return chosen
