# AX 뉴스봇 실습 키트

내가 정한 시간에, 내 브랜드와 경쟁사 뉴스를 모아 Slack으로 보내주는 봇입니다.
**GitHub 서버에서 돌기 때문에 내 컴퓨터가 꺼져 있어도, Claude를 켜지 않아도 매일 알아서 옵니다.**

부스터스 커머스 PR팀이 Claude Code와 함께 만든 실제 운영 코드를 누구나 따라 만들 수 있게 정리했습니다.

- 서버·비용 0원 (GitHub Actions 무료 실행)
- 네이버 뉴스 + Google News(한국/미국) + 전문지 RSS 수집
- 24시간 이내 기사만, 제외어·차단 사이트 필터, 비슷한 기사 중복 제거
- Slack 채널 2곳 동시 발송
- (선택) AI가 경쟁사 기사를 "우리에게 유리/불리"로 라벨링

📖 **강의 가이드(그림·실제 오류 사례)**: [`docs/index.html`](docs/index.html)

```
.github/workflows/briefing.yml   언제 실행할지 (기본: 매일 09:00 KST)
keywords.yml                     내 브랜드·경쟁사 키워드  ← 여기만 고치면 됩니다
boosters_news_briefing.py        수집 → 필터 → 중복 제거 → (AI 판단) → Slack
jev_news_judge.py                AI 판단 모듈 (선택)
```

## 어떻게 동작하나

```
매일 09:00 (GitHub 서버의 알람)
   └→ GitHub가 빈 컴퓨터를 하나 빌려 코드 실행
        └→ 뉴스 수집 · 필터 · 중복 제거
             └→ Slack 채널로 발송 → 컴퓨터 반납
```

내 PC는 처음 설정할 때만 필요합니다. 설정이 끝나면 웹 브라우저로만 관리합니다.

---

## 1단계 · 레포 가져오기

GitHub에 로그인한 뒤 이 페이지 오른쪽 위 **Fork** 버튼을 누릅니다. 내 계정에 복사본이 생깁니다.
(비공개로 쓰고 싶으면 **Use this template** 또는 새 비공개 레포를 만들어 파일을 올려도 됩니다.)

## 2단계 · 키 3개 준비

| 키 | 어디서 | 걸리는 시간 |
|---|---|---|
| 네이버 `Client ID`·`Client Secret` | [네이버 개발자센터](https://developers.naver.com/apps/#/register) → 애플리케이션 등록 → 사용 API **검색** | 3분 |
| Slack Webhook URL | [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From scratch → **Incoming Webhooks** 켜기 → **Add New Webhook** → 채널 선택 → URL 복사 | 5분 |

> 외부 회사가 만든 Slack Connect 채널에는 우리 웹훅을 붙일 수 없습니다. 우리 워크스페이스에 채널을 새로 만들고 외부 담당자를 초대하세요.

## 3단계 · 키 등록 (GitHub Secrets)

내 레포 **Settings → Secrets and variables → Actions → New repository secret** 에서 이름을 **그대로** 입력합니다.

| 이름 | 값 | 필수 |
|---|---|---|
| `NAVER_CLIENT_ID` | 네이버 Client ID | ✅ |
| `NAVER_CLIENT_SECRET` | 네이버 Client Secret | ✅ |
| `SLACK_WEBHOOK_URL` | Slack Webhook URL | ✅ |
| `SLACK_WEBHOOK_URL_2` | 두 번째 채널 Webhook | 선택 |
| `TYPESAFE_API_KEY` | AI 판단 키 | 선택 |

키는 코드나 `keywords.yml`에 절대 적지 마세요. 퍼블릭 레포면 누구나 볼 수 있습니다.

## 4단계 · 내 브랜드로 바꾸기

`keywords.yml`을 GitHub 웹에서 연필(✏️) 아이콘으로 열고, 맨 위 **✏️ 내 브랜드** 부분을 바꿉니다.

```yaml
  my_brand_1:
    display: "⭐ 이퀄베리"        # Slack에 보이는 이름
    always_show: true            # 0건이어도 "오늘 감지된 기사 없음" 표시
    keywords:
      - "이퀄베리"
      - "Eqqualberry"
```

- 브랜드마다 `my_brand_1`, `my_brand_2` … 로 하나씩. 개수는 자유입니다.
- **흔한 이름은 두 단어로 묶기.** `브랜든`만 쓰면 배우·동명이인 기사가 섞입니다 → `부스터스 브랜든`, `브랜드명 + 대표 제품`
- 아래쪽 경쟁사·트렌드 카테고리는 K-뷰티 예시입니다. 필요 없으면 지우고, 필요하면 내 업계 키워드로 바꾸세요.

## 5단계 · 첫 발송 테스트

**Actions** 탭 → (Fork한 경우 초록 버튼 *I understand my workflows, go ahead and enable them* 클릭) → 왼쪽 **뉴스 브리핑** → **Run workflow**.

1~2분 뒤 Slack에 브리핑이 오면 끝입니다. 이제부터 매일 자동으로 옵니다.

---

## ⏰ 받는 시간 바꾸기

`.github/workflows/briefing.yml` 의 `cron` 한 줄을 바꿉니다. **cron은 한국 시간이 아니라 UTC(한국 −9시간)** 입니다.

```yaml
  schedule:
    - cron: '0 0 * * *'    # 분 시 일 월 요일
```

| 받고 싶은 시간 (KST) | cron |
|---|---|
| 매일 오전 7:00 | `'0 22 * * *'` (전날 22시 UTC) |
| 매일 오전 8:30 | `'30 23 * * *'` |
| 매일 오전 9:00 | `'0 0 * * *'` |
| 평일 오전 9:00 | `'0 0 * * 1-5'` |
| 오전 9시 + 오후 6시 | `'0 0 * * *'` 와 `'0 9 * * *'` 두 줄 |

### 정각에 꼭 받아야 한다면 (외부 알람 방식)

GitHub 자체 스케줄은 서버가 붐비면 **30분~3시간 늦게** 돌 수 있습니다 (실제로 9시 설정이 11시 49분에 온 적이 있습니다).
정각이 중요하면 외부 알람 서비스가 정각에 GitHub를 "깨우는" 방식으로 바꿉니다. 무료이고, 이것도 내 컴퓨터는 필요 없습니다.

1. **GitHub 토큰 만들기** — 프로필 사진 → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate
   - Repository access: *Only select repositories* → 이 레포
   - Permissions → **Actions: Read and write**
   - 만든 토큰(`github_pat_...`)을 복사
2. **[cron-job.org](https://cron-job.org) 가입 → CREATE CRONJOB**
   - URL: `https://api.github.com/repos/내계정/내레포/actions/workflows/briefing.yml/dispatches`
   - Schedule: 원하는 시간, **Time zone: Asia/Seoul** (여기선 한국 시간 그대로)
   - Advanced → Request method **POST**
   - Headers:
     ```
     Authorization: Bearer github_pat_...
     Accept: application/vnd.github+json
     ```
   - Request body: `{"ref":"main"}`
3. **`briefing.yml`에서 `schedule:` 두 줄 삭제** — 안 지우면 하루에 두 번 옵니다.
4. cron-job.org에서 **TEST RUN** → GitHub Actions에 실행이 생기면 성공 (응답 코드 `204`가 정상)

---

## (선택) 내 컴퓨터에서 미리 돌려보기

Slack·GitHub 설정 전에 키워드가 잘 잡히는지만 빠르게 보고 싶을 때 씁니다. **매일 자동 발송과는 무관합니다.**
Slack 웹훅을 비워두면 결과를 터미널에 출력합니다.

```bash
git clone https://github.com/sycha-maker/ax-news-bot.git
cd ax-news-bot
pip install -r requirements.txt
cp .env.example .env          # .env 에 네이버 키 입력
set -a; source .env; set +a
python boosters_news_briefing.py
```

## (선택) AI 판단 붙이기

`competitor: true` 카테고리의 기사에 라벨을 붙입니다: `🔴 불리·검토 필요` · `🟠 불리·참고` · `🟢 기회` · `⚪ 중립` · `❔ 판단 보류`. 심층·기획·칼럼 기사는 빠집니다.

- `TYPESAFE_API_KEY`가 없으면 이 단계는 자동으로 건너뜁니다.
- AI 호출이 실패해도 뉴스는 그대로 발송됩니다.
- "우리 회사" 설명은 `jev_news_judge.py`의 `OUR_CONTEXT`와 질문 문구에서 바꿉니다.
- 켜기 전에 지난 기사 30~50건으로 정확도를 확인하세요: `python jev_news_judge.py articles.json results.csv`

## 엉뚱한 기사가 올 때

`boosters_news_briefing.py` 위쪽 두 목록에 추가합니다.

- `EXCLUDE_KEYWORDS` — 제목·요약에 이 단어가 있으면 제외 (예: `주가`, `종목`)
- `EXCLUDE_DOMAINS` — 이 사이트 기사는 통째로 제외 (예: 종목 포털)

어느 키워드가 끌어온 기사인지 모르겠으면 기사 링크를 AI에게 주고 "왜 이게 잡혔는지 찾아줘"라고 하세요.

## 자주 만나는 오류

| 증상 | 원인 · 해결 |
|---|---|
| Slack에 아무것도 안 옴 | Actions 탭에서 실행 기록 확인. 기록이 없으면 Fork 후 워크플로 활성화 안 함 |
| 9시 설정인데 11시쯤 옴 | GitHub 스케줄 지연 → "정각에 꼭 받아야 한다면" 참고 |
| 하루에 두 번 옴 | `schedule`과 외부 알람이 둘 다 켜져 있음 → 하나만 남기기 |
| 60일쯤 뒤 갑자기 멈춤 | GitHub는 활동 없는 레포의 스케줄을 끕니다 → Actions 탭에서 다시 Enable (외부 알람 방식은 해당 없음) |
| `FileNotFoundError: 'keywords.yml'` | 파일이 다른 이름(`keywords (1).yml`)으로 올라감 |
| `404 ... .github/workflows/briefing.yml` | 워크플로 파일이 루트에 있음. **Add file → Create new file**에 경로째 입력 |
| `SyntaxError: invalid character '"'` | 코드를 복사·붙여넣기하다 따옴표가 바뀜 → 파일째 업로드 |
| `Slack 400 Bad Request` | 웹훅 URL 오타·만료 → 새로 발급해서 시크릿 덮어쓰기 |

오류가 나면 **Actions → 실패한 실행 → 빨간 X 단계**를 펼쳐 마지막 몇 줄을 캡처해서 AI에게 보여주세요.

---

만든 곳: 부스터스 커머스 PR팀 · 2026
