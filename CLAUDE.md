# AX 뉴스봇 — Claude 작업 안내

이 레포는 "내가 정한 시간에 브랜드·경쟁사 뉴스를 Slack으로 보내주는 봇"의 실습 키트다.
사용자는 대부분 비개발자이며, 방금 이 레포를 클론한 상태일 가능성이 높다.

## 클론 직후라면

클론만으로는 자동 발송이 되지 않는다. 사용자 본인 GitHub 레포 + Secrets 등록 + 첫 실행까지 필요하다.
사용자가 무엇을 해야 하는지 묻거나 "설정", "다음 단계", "시작"을 말하면 **`news-bot-setup` 스킬을 따라 0~7단계를 끝까지 진행한다.**
사용자가 먼저 말하지 않아도, 이 폴더에서 처음 대화가 시작되면 "뉴스봇 자동 발송 설정을 시작할까요? (약 20분)"라고 먼저 제안한다.

## 파일 역할

- `keywords.yml` — 사용자가 주로 바꾸는 파일. 맨 위 `my_brand_*`가 내 브랜드, 나머지는 예시 카테고리
- `boosters_news_briefing.py` — 수집 → 필터 → 중복 제거 → (AI 판단) → Slack. `.env`가 있으면 자동으로 읽음
- `.github/workflows/briefing.yml` — GitHub 서버에서 매일 실행되는 스케줄 (cron은 UTC)
- `jev_news_judge.py` — 선택 기능 (AI로 경쟁사 기사 유리/불리 판단)

## 지킬 것

- 키(네이버, Slack 웹훅, API 키)를 코드·`keywords.yml`·커밋·답변에 쓰지 않는다. `.env`(로컬)와 GitHub Secrets에만 둔다.
- `.env`는 `.gitignore`에 있다. 절대 커밋하지 않는다.
- 원본 레포(`sycha-maker/ax-news-bot`)에 push하지 않는다. 사용자 본인 레포를 `origin`으로 만든 뒤 push한다.
