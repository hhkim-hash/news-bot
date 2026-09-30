# AX 뉴스봇 실습 키트

매일 아침 9시, 우리 브랜드와 경쟁사 뉴스를 모아 Slack으로 보내주는 봇입니다.
부스터스 커머스 PR팀이 Claude Code와 함께 만든 실제 운영 코드를, 누구나 따라 만들 수 있게 정리했습니다.

- 서버 없음, 비용 0원 (GitHub Actions 무료 실행)
- 네이버 뉴스 + Google News(한국/미국) + 뷰티 전문지 RSS 수집
- 24시간 이내 기사만, 제외어·차단 도메인 필터, 비슷한 기사 중복 제거
- Slack 채널 2곳 동시 발송
- (선택) AI가 경쟁사 기사를 "우리에게 유리/불리"로 라벨링

📖 **강의 가이드(그림·사례 포함)**: [`docs/index.html`](docs/index.html)
레포 Settings → Pages에서 `main` 브랜치 `/docs` 폴더를 켜면 웹페이지로 볼 수 있습니다.

```
.github/workflows/briefing.yml   언제·어떻게 실행할지 (매일 09:00 KST)
boosters_news_briefing.py        수집 → 필터 → 중복 제거 → (AI 판단) → Slack
keywords.yml                     키워드·카테고리 설정  ← 여기만 고치면 됩니다
jev_news_judge.py                AI 판단 모듈 (선택)
.env.example                     로컬 실습용 환경변수 양식
```

---

## 1단계 · 내 컴퓨터에서 먼저 돌려보기 (10분)

Slack 없이 시작합니다. 웹훅이 비어 있으면 결과를 터미널에 출력합니다.

```bash
git clone https://github.com/sycha-maker/ax-news-bot.git
cd ax-news-bot
pip install -r requirements.txt
cp .env.example .env
```

[네이버 개발자센터](https://developers.naver.com/apps/#/register)에서 애플리케이션을 등록하고(사용 API: **검색**), 받은 `Client ID`, `Client Secret`을 `.env`에 채웁니다.

```bash
set -a; source .env; set +a
python boosters_news_briefing.py
```

`----- 미리보기 -----` 아래로 카테고리별 기사 목록이 나오면 성공입니다.

## 2단계 · 키워드를 내 회사로 바꾸기

`keywords.yml`의 예시는 K-뷰티 브랜드 기준입니다. 카테고리 이름·키워드를 자기 업계로 바꾸세요.

| 설정 | 뜻 |
|---|---|
| `lang: en` | 미국 Google News(영어)만 검색 |
| `always_show: true` | 기사가 0건이어도 "오늘 감지된 기사 없음" 표시 (우리 브랜드용) |
| `max_articles` | 카테고리별 최대 전송 건수 |
| `competitor: true` | AI 판단 대상 카테고리 |

엉뚱한 기사가 섞이면 `boosters_news_briefing.py` 위쪽의 `EXCLUDE_KEYWORDS`(제외어), `EXCLUDE_DOMAINS`(차단 사이트)에 추가합니다.
흔한 단어와 겹치는 브랜드명은 따옴표와 맥락어를 붙입니다. 예: `"\"d'Alba\" skincare"`

## 3단계 · 매일 자동 실행 (GitHub Actions)

1. 이 레포를 **Fork** 하거나, 새 레포를 만들어 파일을 올립니다. 비공개 레포도 됩니다.
2. 레포 **Settings → Secrets and variables → Actions → New repository secret** 에 등록:

   | 이름 | 필수 |
   |---|---|
   | `NAVER_CLIENT_ID` | ✅ |
   | `NAVER_CLIENT_SECRET` | ✅ |
   | `SLACK_WEBHOOK_URL` | ✅ |
   | `SLACK_WEBHOOK_URL_2` | 선택 (두 번째 채널) |
   | `TYPESAFE_API_KEY` | 선택 (AI 판단) |

3. **Actions** 탭 → (Fork라면 워크플로 활성화 버튼 클릭) → **뉴스 브리핑 → Run workflow** 로 테스트.
4. 이후 매일 오전 9시(KST)에 자동 실행됩니다.

> ⚠️ `briefing.yml`은 반드시 `.github/workflows/` 안에 있어야 합니다. 웹에서 새로 만들 땐 **Add file → Create new file**에 경로째 `.github/workflows/briefing.yml`을 입력하세요.

## 4단계 · Slack 연결

1. [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → From scratch
2. **Incoming Webhooks** 켜기 → **Add New Webhook to Workspace** → 채널 선택 → URL 복사
3. URL을 `SLACK_WEBHOOK_URL` 시크릿에 저장 (로컬은 `.env`)

채널을 하나 더 쓰려면 웹훅을 하나 더 만들어 `SLACK_WEBHOOK_URL_2`에 넣습니다.
채널 2에 일부 카테고리만 보내려면 `keywords.yml`의 `channel2_categories`에 카테고리 키를 적습니다.

> 외부 회사가 만든 Slack Connect 채널에는 우리 웹훅을 붙일 수 없습니다. 우리 워크스페이스에 채널을 새로 만들고 외부 담당자를 초대하세요.

## 5단계 (선택) · AI 판단 붙이기

`competitor: true` 카테고리의 기사를 AI가 판단해 Slack 제목 앞에 라벨을 붙입니다.
`🔴 불리·검토 필요` · `🟠 불리·참고` · `🟢 기회` · `⚪ 중립` · `❔ 판단 보류`. 심층·기획·칼럼 기사는 빠집니다.

- `TYPESAFE_API_KEY`가 없으면 이 단계는 자동으로 건너뜁니다.
- AI 호출이 실패해도 뉴스는 그대로 발송됩니다. 3회 연속 실패하면 나머지는 호출하지 않습니다.
- 켜기 전에 지난 기사 30~50건으로 정확도를 확인하세요:
  ```bash
  python jev_news_judge.py articles.json results.csv
  ```

## 자주 만나는 오류

| 로그 | 원인 · 해결 |
|---|---|
| `FileNotFoundError: 'keywords.yml'` | 파일이 루트에 없음. 다른 이름(`keywords (1).yml`)으로 올라가지 않았는지 확인 |
| `404 ... .github/workflows/briefing.yml` | 워크플로 파일이 없거나 루트에 있음 → 3단계 경고 참고 |
| `SyntaxError: invalid character '"' (U+201C)` | 코드를 복사·붙여넣기하다 따옴표가 바뀜 → 파일째 업로드 |
| `'ascii' codec can't encode` | 워크플로 env에 `PYTHONUTF8: 1` 확인 |
| `Slack 400 Bad Request` | 웹훅 URL 오타 또는 만료 → 새로 발급 |
| 하루에 두 번 옴 | `schedule`과 외부 크론이 둘 다 돌고 있음 → 하나만 남기기 |
| 오전 9시가 아니라 11시쯤 옴 | GitHub 스케줄 지연. 정시가 필요하면 외부 크론 + `workflow_dispatch` |

오류가 나면 **Actions → 실패한 실행 → 빨간 X 단계**를 펼쳐 마지막 몇 줄을 캡처해서 AI(Claude 등)에게 보여주세요. 대부분 그걸로 원인이 나옵니다.

---

만든 곳: 부스터스 커머스 PR팀 · 2026
