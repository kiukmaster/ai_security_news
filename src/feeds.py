"""수집 대상 RSS/Atom 피드 목록과 출처 신뢰도 정의.

새 소스를 추가하려면 DEFAULT_FEEDS 리스트에 dict 한 줄을 추가하면 됩니다.
  - name     : 보고서에 표시될 출처 이름
  - url      : RSS 또는 Atom 피드 주소
  - category : "security" | "ai" | "research"
  - trust    : 0.0 ~ 1.0 (출처 신뢰도, 팩트체크 점수에 반영)

피드가 일시적으로 죽어도 프로그램은 해당 소스만 건너뛰고 계속 동작합니다.
"""

DEFAULT_FEEDS = [
    # ---------------- 보안 (Security) ----------------
    {"name": "The Hacker News",       "url": "https://feeds.feedburner.com/TheHackersNews",                         "category": "security", "trust": 0.85},
    {"name": "BleepingComputer",      "url": "https://www.bleepingcomputer.com/feed/",                              "category": "security", "trust": 0.90},
    {"name": "Krebs on Security",     "url": "https://krebsonsecurity.com/feed/",                                   "category": "security", "trust": 0.95},
    {"name": "Dark Reading",          "url": "https://www.darkreading.com/rss.xml",                                 "category": "security", "trust": 0.85},
    {"name": "SecurityWeek",          "url": "https://www.securityweek.com/feed/",                                  "category": "security", "trust": 0.85},
    {"name": "The Register · Security","url": "https://www.theregister.com/security/headlines.atom",                "category": "security", "trust": 0.80},
    {"name": "Schneier on Security",  "url": "https://www.schneier.com/feed/atom/",                                 "category": "security", "trust": 0.90},
    {"name": "CISA Advisories",       "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",               "category": "security", "trust": 1.00},

    # ---------------- 보안 · 국내(Korea) ----------------
    {"name": "보안뉴스",              "url": "https://www.boannews.com/media/news_rss.xml",                          "category": "security_kr", "trust": 0.85},
    {"name": "데일리시큐",            "url": "https://www.dailysecu.com/rss/allArticle.xml",                         "category": "security_kr", "trust": 0.80},
    {"name": "안랩 ASEC",             "url": "https://asec.ahnlab.com/ko/feed/",                                     "category": "security_kr", "trust": 0.90},
    {"name": "이스트시큐리티 알약",   "url": "https://blog.alyac.co.kr/rss",                                         "category": "security_kr", "trust": 0.80},

    # ---------------- 취약점(CVE) ----------------
    # cvedetails.com은 자동 접근이 차단(HTTP 403)되어, 동일 원본인 NVD에서 '어제 발행' CVE를
    # 가져오고 각 항목 링크는 cvedetails.com 페이지로 연결합니다. (kind="nvd" 전용 핸들러)
    {"name": "CVE (NVD→cvedetails)",  "url": "https://services.nvd.nist.gov/rest/json/cves/2.0",                     "category": "vuln",     "trust": 0.95, "kind": "nvd", "max_new": 80},

    # ---------------- AI ----------------
    {"name": "OpenAI News",           "url": "https://openai.com/news/rss.xml",                                     "category": "ai",       "trust": 0.90},
    {"name": "Google DeepMind",       "url": "https://deepmind.google/blog/rss.xml",                                "category": "ai",       "trust": 0.90},
    {"name": "Hugging Face Blog",     "url": "https://huggingface.co/blog/feed.xml",                                "category": "ai",       "trust": 0.80},
    {"name": "MIT Tech Review · AI",  "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed/","category": "ai",      "trust": 0.85},

    # ---------------- 신기술 (Trending Tech / GitHub) ----------------
    # 최근 생성된 오픈소스 기술을 GitHub Star(인기) 순으로 수집. (kind="github" 전용 핸들러)
    # dated=False → 날짜 창 대신 '처음 보는 항목'만 누적(인기순 소스라 14일 생성 창 사용).
    {"name": "GitHub 신기술",         "url": "https://api.github.com/search/repositories",                           "category": "tech",     "trust": 0.85, "kind": "github", "dated": False, "max_new": 25},

    # ---------------- 연구 (Research / arXiv) ----------------
    {"name": "arXiv cs.CR (보안)",     "url": "http://export.arxiv.org/rss/cs.CR",                                   "category": "research", "trust": 0.75},
    {"name": "arXiv cs.AI (인공지능)", "url": "http://export.arxiv.org/rss/cs.AI",                                   "category": "research", "trust": 0.75},
]

# 보고서/요약에서 카테고리를 표시할 때 쓰는 라벨과 정렬 순서
CATEGORY_ORDER = ["security", "security_kr", "vuln", "ai", "tech", "research"]
CATEGORY_LABELS = {
    "security": "🛡️ 보안(해외)",
    "security_kr": "🇰🇷 보안(국내)",
    "vuln": "🐞 취약점(CVE)",
    "ai": "🤖 AI",
    "tech": "🚀 신기술(Trending)",
    "research": "📄 연구(arXiv)",
}
