# 🛰️ 보안 · AI 데일리 브리핑

매일 아침 최신 **보안 / AI** 소식을 RSS·공식 피드에서 자동 수집하고,
휴리스틱(규칙 기반) 팩트체크로 신뢰도를 추정한 뒤,
**모바일·PC 겸용 반응형 HTML 보고서**로 정리해 주는 프로그램입니다.

- 외부 패키지 설치가 **필요 없습니다** (Python 표준 라이브러리만 사용).
- 어제 본 지점을 `data/latest.md`에 기록 → 다음 실행 시 **그 이후의 새 정보만** 수집(증분).
- 작업 진행 상황을 가벼운 **Tkinter GUI**로 실시간 표시.

## 빠른 시작

```powershell
# 1) GUI로 실행 (권장)
python main.py
#   또는 탐색기에서 run.bat 더블클릭

# 2) 콘솔(자동 실행)로 실행
python main.py --no-gui --open

# 3) 웹 발행(모바일용 docs/ 생성) — 로컬 미리보기
python main.py --no-gui --publish docs
#   생성 후 docs/index.html 을 브라우저로 열어보면 됩니다.
```

## 📱 폰으로 보기 — 완전 클라우드 자동화 (PC 꺼져 있어도 됨)

GitHub의 무료 서버(Actions)가 **매일 아침 한국시간 06:30**에 자동 실행해 보고서를 만들고,
**GitHub Pages**(웹페이지)에 올립니다. 폰에서는 **그 주소를 북마크 한 번**만 해두면
아침에 일어나 대중교통에서 가볍게 확인할 수 있습니다. (내 PC는 꺼져 있어도 됩니다.)

**설정 (최초 1회, 약 5분):**

1. GitHub에 새 저장소를 만들고 이 폴더 전체를 푸시합니다.
   ```powershell
   git init
   git add .
   git commit -m "init: 보안·AI 데일리 브리핑"
   git branch -M main
   git remote add origin https://github.com/<내아이디>/<저장소이름>.git
   git push -u origin main
   ```
2. 저장소 **Settings → Pages → Build and deployment**
   - Source: **Deploy from a branch**
   - Branch: **main** / 폴더 **/docs** → Save
3. 저장소 **Settings → Actions → General → Workflow permissions**
   - **Read and write permissions** 선택 → Save (봇이 보고서를 커밋할 수 있도록)
4. **Actions** 탭 → "Daily Briefing" → **Run workflow**로 한 번 실행(첫 보고서 생성).
5. 잠시 후 **`https://<내아이디>.github.io/<저장소이름>/`** 접속 → 이 주소를 폰에 **북마크/홈 화면 추가**.

이후 매일 아침 자동으로 갱신됩니다. 직접 즉시 실행하고 싶을 땐 **GitHub 모바일 앱 → Actions → Run workflow**(딸깍)로도 가능합니다.

- 실행 시각 변경: [.github/workflows/daily.yml](.github/workflows/daily.yml)의 `cron`(UTC 기준)을 수정. 예) 07:00 KST = `0 22 * * *`.
- ⚠️ 공개 저장소의 Pages는 주소를 아는 사람이 볼 수 있습니다(내용은 모두 공개 보안뉴스/CVE라 민감정보 없음). 비공개로 받고 싶으면 텔레그램 봇·이메일 방식으로 바꿀 수 있습니다.

GUI에서 **▶ 오늘 보고서 생성**을 누르면 수집→팩트체크→보고서 생성이 진행되고,
완료되면 보고서가 자동으로 브라우저에 열립니다.

## 폴더 구조

```
new_data/
├─ main.py            진입점 (GUI / --no-gui / --publish)
├─ run.bat            Windows 실행 편의 스크립트
├─ .github/workflows/
│  └─ daily.yml       매일 아침 클라우드 자동 실행(GitHub Actions)
├─ src/
│  ├─ feeds.py        수집 소스 목록 + 출처 신뢰도  ← 소스 추가/수정은 여기
│  ├─ collector.py    RSS/Atom/RDF·NVD(CVE)·GitHub(신기술) 수집·파싱
│  ├─ factcheck.py    휴리스틱 팩트체크(교차출처·신뢰도) + 중복 제거
│  ├─ daterange.py    '대상일 하루' 시간창 계산
│  ├─ summarize.py    Gemini API 기사별 AI 요약(키 없으면 폴백)
│  ├─ report.py       반응형 HTML 생성
│  ├─ state.py        latest.md 증분 상태 관리
│  ├─ pipeline.py     전체 흐름 오케스트레이션
│  ├─ publish.py      docs/ 웹 발행 + 모바일 index 생성
│  └─ gui.py          Tkinter 진행 GUI
├─ docs/              (웹 발행물 — GitHub Pages가 서빙)
│  ├─ index.html      모바일용 랜딩(최신+지난 보고서)
│  └─ reports/        날짜별 보고서
└─ data/              (자동 생성)
   ├─ latest.md       마지막 수집 지점 기록(증분 상태, 저장소에 추적)
   └─ reports/        로컬 보고서(저장소에서는 무시)
```

## 🤖 AI 요약 (Gemini) + API 키 안전 보관

각 기사를 **Gemini API**(무료 티어)로 한국어 2~3문장 요약합니다. 보고서의 기사마다
**🤖 AI 요약 보기** 버튼을 누르면 요약을 볼 수 있습니다. API 한도 보호를 위해
**카테고리별 최대 20건**만 요약·게재합니다.

> 키가 없으면 요약을 건너뛰고 원문 발췌(📄)를 표시하므로, 키 없이도 정상 동작합니다.

**API 키는 코드에 하드코딩하지 않습니다.** 환경변수 `GEMINI_API_KEY`로만 읽습니다.

1. **키 발급**: [Google AI Studio](https://aistudio.google.com/apikey)에서 무료 API 키 생성.
2. **GitHub(클라우드)**: 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `GEMINI_API_KEY` / Secret: 발급받은 키 → Save
   - 워크플로가 `${{ secrets.GEMINI_API_KEY }}`로 안전하게 주입합니다(코드·로그에 노출 안 됨).
3. **로컬(선택)**: 키를 환경변수로 두거나 `.env` 파일(자동 `.gitignore`)에 저장.
   ```powershell
   $env:GEMINI_API_KEY = "발급키"      # 현재 세션만
   #  또는 프로젝트 루트에 .env 파일:  GEMINI_API_KEY=발급키
   ```

- 모델 변경: 환경변수 `GEMINI_MODEL`(기본 `gemini-2.5-flash-lite`).
- 무료 티어는 **분당 15요청** 한도라, 요약을 **15건 처리 → 70초 대기 → 다시 15건** 방식으로 돌립니다.
  새벽 자동 실행이라 신규 기사 수에 따라 수 분 걸려도 괜찮습니다(아침엔 이미 완성).
- `.env`, `*.key`, `secret*` 등은 `.gitignore`로 커밋이 차단됩니다.

## 팩트체크 방식 (휴리스틱)

각 항목 점수(0~100)는 다음 신호로 계산됩니다.

| 신호 | 배점 | 의미 |
| --- | ---: | --- |
| 출처 신뢰도 | 50 | 매체별 신뢰도(`feeds.py`의 `trust`) |
| 교차출처 보도 | 35 | 다른 매체가 같은 사건을 보도했는가 |
| 원문 링크 | 10 | 검증 가능한 원문 링크 존재 |
| 발행 시각 | 5 | 날짜 메타데이터 존재 |

점수에 따라 **높음(≥75) / 보통(≥55) / 주의(<55)** 등급을 표시합니다.
이는 *자동 검증*이 아니라 *교차검증을 돕는 보조 지표*이며,
보고서에 판단 근거를 함께 표기하므로 최종 확인 전 원문을 확인하세요.

## 매일 아침 자동 실행 (Windows 작업 스케줄러)

1. **작업 스케줄러** 실행 → *작업 만들기*
2. 트리거: *매일* / 원하는 시각(예: 오전 8시)
3. 동작: *프로그램 시작*
   - 프로그램: `python` (또는 `py`)
   - 인수: `"%USERPROFILE%\Desktop\new_data\main.py" --no-gui`
   - 시작 위치: `%USERPROFILE%\Desktop\new_data`
4. 저장. 매일 아침 새 보고서가 `data/reports/`에 쌓입니다.

> GUI로 보고 싶으면 인수에서 `--no-gui`를 빼면 됩니다.

## 소스 추가/변경

`src/feeds.py`의 `DEFAULT_FEEDS`에 한 줄 추가하면 됩니다.

```python
{"name": "표시이름", "url": "https://example.com/feed.xml",
 "category": "security", "trust": 0.8},
```

- `category`: `"security"` | `"ai"` | `"research"`
- `trust`: 0.0~1.0 (출처 신뢰도)
- 피드가 일시적으로 죽어도 해당 소스만 건너뛰고 전체는 정상 동작합니다.

## 수집 소스 구성

- **해외 보안**: The Hacker News, BleepingComputer, Krebs, Dark Reading, SecurityWeek,
  The Register, Schneier, CISA
- **국내 보안**: 보안뉴스, 데일리시큐, 안랩 ASEC, 이스트시큐리티 알약
- **취약점(CVE)**: 보고서에 별도 `🐞 취약점(CVE)` 카테고리로 분리(상단 칩 클릭 시 이동).
  **어제 발행된 CVE만** CVSS 심각도 높은 순으로 표시하며, 각 항목은 cvedetails.com 페이지로 연결됩니다.
- **AI / 연구**: OpenAI, DeepMind, Hugging Face, MIT Tech Review, arXiv(cs.CR/cs.AI)

> CVE 데이터는 **NVD(미국 국가취약점DB)** 에서 정확한 날짜로 수집합니다.
> cvedetails.com은 자동 접근을 차단(HTTP 403)하므로 직접 크롤링하지 않고,
> 동일 원본인 NVD에서 받아 **링크만 cvedetails.com**으로 연결하는 방식입니다.

## 참고

- 한국 매체(보안뉴스 등) 중 일부는 EUC-KR 인코딩 RSS라, 파서가 자동으로 인코딩을 감지해 처리합니다.
- X(트위터)/Threads는 공식 API 키·로그인이 필요하고 무단 크롤링은 차단·정지
  위험이 커서 기본 소스에서 제외했습니다. 필요 시 별도 API 연동으로 확장할 수 있습니다.
