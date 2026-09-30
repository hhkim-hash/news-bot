---
name: news-bot-setup
description: 이 레포(AX 뉴스봇)를 클론한 사용자가 "내 계정에서 매일 자동으로 Slack에 뉴스가 오는 상태"가 될 때까지 대화형으로 설정을 끝까지 진행한다. 사용자가 "뉴스봇 설정", "셋업 시작", "설정 도와줘", "다음 단계", "자동 모니터링 설정", "클론 다 했어"라고 하거나, 클론 직후 무엇을 해야 하는지 물을 때 사용한다.
---

# AX 뉴스봇 설정 가이드 (Claude용 진행 대본)

## 목표

클론만으로는 자동 발송이 되지 않는다. 사용자 **본인 GitHub 계정의 레포**에 코드가 있고, 그 레포에 **키(Secrets)** 가 등록되어 있어야 GitHub 서버가 매일 정해진 시간에 실행한다.
이 스킬이 끝나면 다음이 모두 참이어야 한다:

1. 사용자 계정에 이 코드가 담긴 레포가 있다
2. `keywords.yml` 맨 위 "내 브랜드"가 사용자 브랜드로 바뀌어 있다
3. 레포 Secrets에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SLACK_WEBHOOK_URL`이 있다
4. 원하는 시간(KST)으로 스케줄이 설정되어 있다
5. 수동 실행 1회가 성공했고, 사용자가 Slack에서 메시지를 확인했다

## 진행 원칙

- 사용자는 비개발자다. 전문 용어는 한 줄로 풀어 설명하고, 한 번에 한 가지만 묻는다.
- 각 단계 시작 시 "지금 N/7 단계: ○○" 형태로 위치를 알려준다.
- 명령은 가능한 한 직접 실행한다. 사용자가 직접 해야 하는 것(웹사이트 가입, 로그인, 키 발급)만 요청한다.
- **키 값은 채팅에 붙여넣게 하지 않는다.** `.env` 파일에 사용자가 직접 입력하게 하고, 스크립트가 파일에서 읽어 GitHub에 올린다. 사용자가 이미 채팅에 붙여넣었다면 그 값을 `.env`에 써 주되, 이후 답변에 값을 다시 출력하지 않는다.
- 운영체제를 먼저 확인한다 (Windows는 PowerShell 명령, Mac은 zsh 명령).
- 이미 끝난 단계가 있으면 확인 후 건너뛴다 (예: 이미 본인 레포면 1단계 생략).

---

## 0/7 · 환경 점검

다음을 실행해 결과를 확인한다.

```
git --version
gh --version
python --version     (Mac은 python3 --version)
gh auth status
```

- `gh`가 없으면 설치를 안내하고 대신 설치한다.
  - Windows: `winget install --id GitHub.cli -e`
  - Mac: `brew install gh`
  - 설치 후 PATH 반영을 위해 새 터미널이 필요할 수 있음을 알린다.
- `python`이 없으면: Windows `winget install -e --id Python.Python.3.12`, Mac `brew install python`
- `gh auth status`가 로그인 안 됨이면, 사용자에게 **직접** 실행하도록 안내한다 (브라우저 인증이 필요해 Claude가 대신 끝낼 수 없음):
  > 입력창에 `! gh auth login` 을 입력하고 Enter → GitHub.com → HTTPS → Login with a web browser → 표시된 코드를 브라우저에 입력
  완료 후 `gh auth status`로 다시 확인한다.

## 1/7 · 내 레포 만들기

현재 폴더의 `origin`이 원본(`sycha-maker/ax-news-bot`)을 가리키는지 확인한다: `git remote -v`

원본을 가리키면 사용자에게 두 가지만 묻는다:
- 레포 이름 (기본값 `news-bot` 제안)
- 공개 범위 → **비공개(private) 추천**. 이유: 내 브랜드·경쟁사 키워드가 외부에 보이지 않음. 키는 어느 쪽이든 안전함.

실행:
```
git remote rename origin upstream
gh repo create <이름> --private --source=. --remote=origin --push
```
`gh repo view --web` 은 실행하지 말고, 만들어진 레포 URL을 알려준다.

## 2/7 · 내 브랜드로 바꾸기

한 번에 하나씩 묻는다.

1. "매일 확인하고 싶은 브랜드(또는 회사·대표 이름)는 무엇인가요? 여러 개면 쉼표로 적어주세요."
2. 브랜드마다: "기사에서 이 브랜드는 어떻게 불리나요? (한글명, 영문명, 회사명+브랜드명 등)"
   - 흔한 단어·사람 이름과 겹치면 두 단어로 묶자고 제안한다 (예: `브랜든` → `부스터스 브랜든`, `브랜든 압축 파우치`).
3. "경쟁사나 업계 트렌드도 같이 받을까요?"
   - 아니오 → `keywords.yml`에서 `my_brand_*` 외 카테고리를 모두 삭제
   - 예 → 경쟁사 브랜드명과 업계 키워드를 받아 예시 카테고리를 교체. 해외(영어) 기사도 원하면 `lang: en` 카테고리를 만든다. 경쟁사 카테고리에는 `competitor: true`
4. `keywords.yml`의 `my_brand_1~3`을 사용자 브랜드로 교체한다 (개수에 맞게 추가·삭제). 각 카테고리는 `always_show: true`.
5. 바뀐 브랜드 부분을 보여주고 확인받는다.

`boosters_news_briefing.py`의 `EXCLUDE_KEYWORDS`에 있는 `정관장`, `레드부스터스`, `LG유플러스`, `LG U+`, `유플러스`, `크리에이터 육성`은 원 제작사 전용 필터다. 사용자 업계와 무관하면 지워도 된다고 알려주고, 원하면 지운다.

## 3/7 · 네이버 키 발급

사용자에게 안내한다 (직접 해야 함):
1. https://developers.naver.com/apps/#/register 접속 → 네이버 로그인
2. 애플리케이션 이름: 아무거나 (예: 뉴스봇)
3. 사용 API: **검색** 선택
4. 비로그인 오픈 API 서비스 환경: **WEB 설정**, URL: `http://localhost`
5. 등록 → `Client ID`, `Client Secret` 확인

그다음 `.env` 파일을 만든다: `.env.example`을 `.env`로 복사한다 (이미 있으면 유지).
사용자에게: "`.env` 파일을 열어 `NAVER_CLIENT_ID=` 뒤에 Client ID, `NAVER_CLIENT_SECRET=` 뒤에 Secret을 붙여넣고 저장해주세요. 채팅에는 붙여넣지 않으셔도 됩니다."
- Windows: `notepad .env` / Mac: `open -e .env` 로 열어준다.

저장했다고 하면 **로컬 미리보기**를 1회 실행해 키가 맞는지 확인한다: `python boosters_news_briefing.py`
- 출력 마지막에 `----- 미리보기 -----`와 브랜드별 목록이 나오면 성공
- `[뉴스 수집 오류] ... 401` 이면 키 오타 → 다시 확인 요청
- 내 브랜드가 "오늘 감지된 기사 없음"이어도 정상임을 알린다 (최근 24시간 기사만 봄)

## 4/7 · Slack 웹훅 발급

사용자에게 안내한다:
1. https://api.slack.com/apps → **Create New App** → **From scratch** → 앱 이름(예: 뉴스봇), 워크스페이스 선택
2. 왼쪽 **Incoming Webhooks** → 오른쪽 위 스위치 **On**
3. 맨 아래 **Add New Webhook to Workspace** → 받을 채널 선택 → 허용
4. 생긴 `https://hooks.slack.com/services/...` URL 복사 → `.env`의 `SLACK_WEBHOOK_URL=` 뒤에 붙여넣고 저장

막히는 경우:
- "본인의 팀이 소유한 채널을 선택하세요" → 외부 회사가 만든 공유 채널이라 불가. 우리 워크스페이스에 새 채널을 만들어 선택
- 앱 설치 권한이 없다고 나오면 → 워크스페이스 관리자 승인이 필요. 관리자에게 요청하도록 안내

두 번째 채널도 원하면 같은 방법으로 웹훅을 하나 더 만들어 `SLACK_WEBHOOK_URL_2`에 넣는다.

## 5/7 · 키를 GitHub에 등록

`.env`에서 **값이 있는 줄만** 골라 GitHub Secrets로 올린다. 값을 화면에 출력하지 않는다.

Mac/Linux:
```
grep -E '^[A-Z0-9_]+=.+' .env > .env.upload && gh secret set -f .env.upload && rm .env.upload
```
Windows PowerShell:
```
Get-Content .env | Where-Object { $_ -match '^[A-Z0-9_]+=.+' } | Set-Content -Encoding utf8 .env.upload; gh secret set -f .env.upload; Remove-Item .env.upload
```
확인: `gh secret list` → 최소 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SLACK_WEBHOOK_URL` 3개가 보여야 한다.

`.env`는 `.gitignore`에 있어 GitHub에 올라가지 않는다고 안심시킨다.

## 6/7 · 받는 시간 정하기

묻는다: "매일 몇 시에 받을까요? (예: 오전 9시, 평일 오전 8시 30분)"

한국 시간을 UTC로 바꿔 `.github/workflows/briefing.yml`의 `cron`을 수정한다. **UTC = KST − 9시간** (날짜가 전날로 넘어갈 수 있음에 주의).

| KST | cron |
|---|---|
| 매일 07:00 | `0 22 * * *` |
| 매일 08:30 | `30 23 * * *` |
| 매일 09:00 | `0 0 * * *` |
| 평일 09:00 | `0 0 * * 1-5` |
| 평일 08:00 (요일도 전날로 이동) | `0 23 * * 0-4` |

그리고 한 문장으로 알린다: "GitHub 기본 스케줄은 서버가 붐비면 30분~3시간 늦을 수 있어요. 정각이 꼭 필요하면 README의 '정각에 꼭 받아야 한다면'(cron-job.org) 방식을 이어서 설정해 드릴게요."
사용자가 원하면 README의 해당 절차를 함께 진행한다. 이 경우 토큰 발급과 cron-job.org 가입은 사용자가 직접 하고, `schedule:` 두 줄 삭제는 Claude가 한다.

변경을 커밋하고 올린다:
```
git add keywords.yml .github/workflows/briefing.yml boosters_news_briefing.py
git commit -m "내 브랜드·발송 시간 설정"
git push
```

## 7/7 · 첫 발송 테스트

```
gh workflow run briefing.yml
```
몇 초 뒤 실행 ID를 확인하고 끝날 때까지 지켜본다:
```
gh run list --workflow=briefing.yml --limit 1
gh run watch <실행ID> --exit-status
```
- 성공이면: "Slack 채널에 브리핑이 왔는지 확인해 주세요." → 사용자가 확인하면 완료
- 실패면: `gh run view <실행ID> --log-failed` 로 마지막 오류 줄을 읽고 README의 "자주 만나는 오류" 표를 참고해 고친 뒤 다시 실행

## 완료 안내

아래를 짧게 정리해 알려준다:
- 레포 주소
- 매일 받는 시간 (KST)
- 이제 컴퓨터를 꺼도 GitHub 서버가 매일 실행한다는 점
- 키워드를 바꾸고 싶으면: GitHub 웹에서 `keywords.yml` 연필 아이콘으로 수정, 또는 이 폴더에서 Claude에게 "키워드 바꿔줘"
- 60일 넘게 레포에 변경이 없으면 GitHub가 스케줄을 멈출 수 있음 → Actions 탭에서 다시 Enable (외부 알람 방식은 해당 없음)
