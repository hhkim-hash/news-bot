import os
import re
import time
import requests
import yaml
import feedparser
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from html import unescape
from email.utils import parsedate_to_datetime
from urllib.parse import quote


def _load_dotenv(path: str = ".env") -> None:
    """로컬 실행용: .env 파일이 있으면 읽어 환경변수로 설정 (Windows/Mac 공통).
    GitHub Actions에서는 .env가 없으므로 아무 일도 하지 않는다. 이미 설정된 값은 덮어쓰지 않는다."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# ============================================================
# 환경변수
# ============================================================
NAVER_CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
SLACK_WEBHOOK_URL   = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL_2 = os.environ.get("SLACK_WEBHOOK_URL_2", "")  # 두 번째 채널 (선택)

KST = ZoneInfo("Asia/Seoul")

# Jev 판단 모듈 — 파일이 없거나 로드에 실패해도 브리핑은 계속 진행
try:
    from jev_news_judge import judge as jev_judge, Verdict
except Exception as e:  # noqa: BLE001
    jev_judge = None
    print(f"[Jev] 모듈 로드 실패 — 판단 단계 건너뜀: {e}")

# 연속으로 이 횟수만큼 실패하면 나머지 기사는 Jev 호출을 중단 (API 장애 시 시간 초과 방지)
JEV_MAX_CONSECUTIVE_ERRORS = 3

# ============================================================
# 제외 키워드 (수집 단계에서 필터링)
# ============================================================
EXCLUDE_KEYWORDS = [
    "정관장", "레드부스터스", "LG유플러스", "LG U+", "유플러스", "크리에이터 육성",
    "주가", "주식", "상장", "공모", "IPO", "코스피", "코스닥", "증권",
    "주주", "배당", "시가총액", "펀드", "ETF", "투자자", "매수", "매도",
    "프로야구", "야구", "농구", "축구", "스포츠", "팬덤", "연예인",
    # 종목 추천 · 시황 기사
    "종목", "밸류에이션", "목표주가", "증권사", "가치투자", "[리스트]", "상위 20선",
    "52주 신고가", "신저가", "상한가", "하한가", "외국인 순매수", "기관 순매수",
]

# 종목/시황 전문 포털 — 도메인 단위로 제외
EXCLUDE_DOMAINS = [
    "itooza.com", "thinkpool.com", "paxnet.co.kr", "infostockdaily.co.kr",
    "stockplus.com", "finance.naver.com", "fnguide.com",
]


def is_excluded_domain(link: str) -> bool:
    return any(d in (link or "") for d in EXCLUDE_DOMAINS)

# ============================================================
# 키워드 설정 로드
# ============================================================
def load_keywords(path: str = "keywords.yml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================
# 유틸리티
# ============================================================
def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def extract_source(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        host = re.sub(r"^www\.", "", host)
        source_map = {
            "hankyung.com": "한국경제", "mk.co.kr": "매일경제",
            "chosun.com": "조선일보", "biz.chosun.com": "조선비즈",
            "joongang.co.kr": "중앙일보", "donga.com": "동아일보",
            "hani.co.kr": "한겨레", "khan.co.kr": "경향신문",
            "yonhapnews.co.kr": "연합뉴스", "yna.co.kr": "연합뉴스",
            "newsis.com": "뉴시스", "news1.kr": "뉴스1",
            "edaily.co.kr": "이데일리", "etnews.com": "전자신문",
            "zdnet.co.kr": "지디넷", "mt.co.kr": "머니투데이",
            "thebell.co.kr": "더벨", "sedaily.com": "서울경제",
            "fnnews.com": "파이낸셜뉴스", "newspim.com": "뉴스핌",
            "inews24.com": "아이뉴스24", "startupn.kr": "스타트업N",
            "platum.kr": "플래텀", "venturesquare.net": "벤처스퀘어",
            "bridgeeconomy.co.kr": "브릿지경제",
            "beautyhankook.com": "뷰티한국", "cosmorning.com": "코스모닝",
            "csnews.co.kr": "CS유통뉴스",
        }
        for domain, name in source_map.items():
            if domain in host:
                return name
        return host.split(".")[0]
    except Exception:
        return "기타"


def is_within_24h(pub_date_str: str) -> bool:
    try:
        pub_dt = parsedate_to_datetime(pub_date_str)
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - pub_dt).total_seconds() <= 86400
    except Exception:
        return True


def is_excluded(title: str, description: str) -> bool:
    text = title + " " + description
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


# ============================================================
# 네이버 뉴스 수집
# ============================================================
def fetch_news(keyword: str, display: int = 5) -> list[dict]:
    # 선택 기능: 네이버 키가 없으면 건너뛰고 Google News(한국)로만 수집한다
    if not (NAVER_CLIENT_ID and NAVER_CLIENT_SECRET):
        return []
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": display, "sort": "date"}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        res.raise_for_status()
        items = res.json().get("items", [])
        result = []
        for item in items:
            title = strip_html(item["title"])
            description = strip_html(item["description"])

            if not is_within_24h(item["pubDate"]):
                print(f"[오래된 기사 제외] {title[:30]}")
                continue

            if is_excluded(title, description):
                print(f"[제외 키워드] {title[:30]}")
                continue

            result.append({
                "keyword": keyword,
                "title": title,
                "description": description,
                "link": item.get("originallink") or item.get("link"),
                "pubDate": item["pubDate"],
                "source": extract_source(item.get("originallink") or item.get("link", "")),
            })
        return result
    except Exception as e:
        print(f"[뉴스 수집 오류] {keyword}: {e}")
        return []


# ============================================================
# Google News RSS 수집
# ============================================================
def fetch_news_rss(keyword: str, display: int = 5, lang: str = "ko") -> list[dict]:
    # lang="en" → 미국 영어 뉴스 검색 (영미권 PR 모니터링용)
    if lang == "en":
        locale = "hl=en-US&gl=US&ceid=US:en"
    else:
        locale = "hl=ko&gl=KR&ceid=KR:ko"
    url = f"https://news.google.com/rss/search?q={quote(keyword)}&{locale}"
    try:
        feed = feedparser.parse(url)
        result = []
        for entry in feed.entries[:display]:
            title = strip_html(entry.get("title", ""))
            description = strip_html(entry.get("summary", ""))
            pub_date = entry.get("published", "")

            if not is_within_24h(pub_date):
                print(f"[RSS 오래된 기사 제외] {title[:30]}")
                continue

            if is_excluded(title, description):
                print(f"[RSS 제외 키워드] {title[:30]}")
                continue

            link = entry.get("link", "")
            try:
                source = entry.source.title
            except AttributeError:
                source = extract_source(link)

            result.append({
                "keyword": keyword,
                "title": title,
                "description": description,
                "link": link,
                "pubDate": pub_date,
                "source": source,
            })
        return result
    except Exception as e:
        print(f"[RSS 수집 오류] {keyword}: {e}")
        return []


# ============================================================
# 전문 매체 RSS 수집 (키워드 필터링)
# ============================================================
def fetch_media_rss_source(source_name: str, rss_url: str, filter_keywords: list[str]) -> list[dict]:
    try:
        feed = feedparser.parse(rss_url)
        result = []
        for entry in feed.entries:
            title       = strip_html(entry.get("title", ""))
            description = strip_html(entry.get("summary", ""))
            pub_date    = entry.get("published", "")

            if not is_within_24h(pub_date):
                continue
            if is_excluded(title, description):
                continue

            text = title + " " + description
            matched = next((kw for kw in filter_keywords if kw in text), None)
            if not matched:
                continue

            link = entry.get("link", "")
            result.append({
                "keyword": matched,
                "title": title,
                "description": description,
                "link": link,
                "pubDate": pub_date,
                "source": source_name,
            })
        print(f"[전문 매체 RSS] {source_name}: {len(result)}건")
        return result
    except Exception as e:
        print(f"[전문 매체 RSS 오류] {source_name}: {e}")
        return []


# ============================================================
# 중복 제거
# ============================================================
DEDUP_THRESHOLD = 0.27

MEDIA_TIER: dict[str, int] = {
    "한국경제": 1, "매일경제": 1, "조선일보": 1, "조선비즈": 1,
    "중앙일보": 1, "동아일보": 1, "연합뉴스": 1, "한겨레": 1, "경향신문": 1,
    "이데일리": 2, "전자신문": 2, "뉴시스": 2, "뉴스1": 2,
    "머니투데이": 2, "서울경제": 2, "파이낸셜뉴스": 2, "뉴스핌": 2,
    "지디넷": 3, "아이뉴스24": 3, "더벨": 3, "브릿지경제": 3,
    "뷰티한국": 3, "코스모닝": 3, "CS유통뉴스": 3,
    "뷰티경제": 3, "화장품신문(뷰티누리)": 3,
}


def get_media_tier(source: str) -> int:
    return MEDIA_TIER.get(source, 4)


def title_similarity(t1: str, t2: str) -> float:
    def bigrams(s: str) -> set[str]:
        s = re.sub(r"[^\w가-힣]", "", s.lower())
        return {s[i:i+2] for i in range(len(s) - 1)}

    bg1, bg2 = bigrams(t1), bigrams(t2)
    if not bg1 or not bg2:
        return 0.0
    return len(bg1 & bg2) / len(bg1 | bg2)


def find_similar_idx(title: str, seen: list[dict]) -> int:
    for i, a in enumerate(seen):
        if title_similarity(title, a["title"]) >= DEDUP_THRESHOLD:
            return i
    return -1


def _add_or_replace(article: dict, global_seen: list[dict], cat_articles: list[dict], dedup: bool) -> bool:
    if is_excluded_domain(article["link"]):
        print(f"[제외 도메인] {article['title'][:30]}")
        return False

    if not dedup:
        global_seen.append(article)
        cat_articles.append(article)
        return True

    idx = find_similar_idx(article["title"], global_seen)
    if idx < 0:
        global_seen.append(article)
        cat_articles.append(article)
        return True

    existing = global_seen[idx]
    if get_media_tier(article["source"]) < get_media_tier(existing["source"]):
        print(f"[티어 교체] {existing['source']}→{article['source']}: {article['title'][:28]}")
        global_seen[idx] = article
        for j, a in enumerate(cat_articles):
            if a["title"] == existing["title"]:
                cat_articles[j] = article
                break
        return True

    print(f"[중복 제거] {article['title'][:30]}")
    return False


def collect_by_category(config: dict) -> dict[str, list[dict]]:
    display = config["settings"]["display_per_keyword"]
    use_naver = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)
    # 네이버를 안 쓰면 Google News(한국)에서 2배로 가져와 빈자리를 채운다
    kr_rss_display = display if use_naver else display * 2
    print(f"[수집 경로] 한국어: {'네이버 + ' if use_naver else ''}Google News KR · 영어: Google News US")
    dedup   = config["settings"]["dedup_enabled"]
    result  = {}
    global_seen: list[dict] = []

    for cat_key, cat in config["categories"].items():
        articles: list[dict] = []
        lang = cat.get("lang", "ko")

        for keyword in cat.get("keywords", []):
            if lang == "en":
                # 영어 카테고리: 네이버 제외, Google News(US)만
                fetched = fetch_news_rss(keyword, display, lang="en")
            else:
                fetched = fetch_news(keyword, display) + fetch_news_rss(keyword, kr_rss_display)
            for article in fetched:
                _add_or_replace(article, global_seen, articles, dedup)
            time.sleep(0.2)

        for feed_info in cat.get("media_sources", {}).get("feeds", []):
            filter_kws = cat["media_sources"]["filter_keywords"]
            for article in fetch_media_rss_source(feed_info["name"], feed_info["url"], filter_kws):
                _add_or_replace(article, global_seen, articles, dedup)
            time.sleep(0.2)

        result[cat_key] = articles
        print(f"[수집] {cat['display']}: {len(articles)}건")

    return result


# ============================================================
# Jev 판단 (경쟁사 기사 유리/불리 라벨 + 심층·기획·칼럼 제외)
# ============================================================
def apply_jev(categorized: dict, config: dict) -> dict:
    """keywords.yml에서 competitor: true 인 카테고리의 기사만 Jev로 판단한다.

    - 경쟁사 여부는 기사를 수집한 검색 키워드(article["keyword"])로 코드에서 결정
    - skip=True(심층·기획·칼럼)인 기사는 목록에서 제거
    - 라벨은 article["jev_label"]에 저장 → Slack 제목 앞에 붙는다
    - 어떤 경우에도 예외를 밖으로 던지지 않는다
    """
    if jev_judge is None:
        return categorized
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("[Jev] TYPESAFE_API_KEY 없음 — 판단 단계 건너뜀")
        return categorized

    judged = skipped = errors = 0
    consecutive_errors = 0
    tripped = False

    for cat_key, articles in categorized.items():
        cat = config["categories"][cat_key]
        if not cat.get("competitor"):
            continue
        exclude = set(cat.get("competitor_exclude") or [])

        kept = []
        for a in articles:
            if a["keyword"] in exclude:
                kept.append(a)
                continue
            if tripped:
                a["jev_label"] = "❔ 판단 불가"
                kept.append(a)
                continue

            try:
                v = jev_judge({
                    "title": a["title"],
                    "description": a.get("description", ""),
                    "competitor": a["keyword"],
                })
            except Exception as e:  # noqa: BLE001  (응답 형식 불일치 등)
                v = Verdict(label="❔ 판단 불가", error=str(e))

            if v.error:
                errors += 1
                consecutive_errors += 1
                print(f"[Jev 오류] {a['title'][:30]} — {v.error}")
                if consecutive_errors >= JEV_MAX_CONSECUTIVE_ERRORS:
                    tripped = True
                    print(f"[Jev] 연속 {consecutive_errors}회 실패 — 나머지 기사는 Jev 호출 중단")
            else:
                consecutive_errors = 0

            if v.skip:
                skipped += 1
                print(f"[Jev 제외] 심층·기획·칼럼 — {a['title'][:30]}")
                continue

            if not v.error:
                judged += 1
            a["jev_label"] = v.label
            kept.append(a)

        categorized[cat_key] = kept

    print(f"[Jev] 판단 {judged}건 · 제외 {skipped}건 · 오류 {errors}건")
    return categorized


# ============================================================
# Slack 메시지 포맷 (Block Kit)
# ============================================================
def build_slack_blocks(categorized: dict, config: dict) -> list:
    now = datetime.now(KST).strftime("%Y년 %m월 %d일 %H:%M")
    max_per_cat = config["settings"]["max_articles_per_category"]

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📰 Boosters 뉴스 브리핑  |  {now}"},
        },
        {"type": "divider"},
    ]

    total = 0
    for cat_key, articles in categorized.items():
        cat_cfg = config["categories"][cat_key]
        # 카테고리별 max_articles 지정 시 우선 적용
        top = articles[:cat_cfg.get("max_articles", max_per_cat)]

        # always_show: 기사가 없어도 "없음"으로 표시 (핵심 키워드 일일 확인용)
        if not top and not cat_cfg.get("always_show"):
            continue

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{cat_cfg['display']}*"},
        })

        if not top:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "_오늘 감지된 기사 없음_"},
            })
            blocks.append({"type": "divider"})
            continue

        for a in top:
            pub = a.get("pubDate", "")[:16]
            label = f"{a['jev_label']} " if a.get("jev_label") else ""
            text = f"• {label}*<{a['link']}|{a['title']}>*\n  {a.get('source', '')}  ·  {pub}"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
            total += 1

        blocks.append({"type": "divider"})

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"총 {total}건  ·  Boosters News Bot"}],
    })
    return blocks


# ============================================================
# Slack 전송 (블록 수 초과 시 분할)
# ============================================================
def print_preview(blocks: list) -> None:
    """Slack 대신 터미널에 결과를 출력 (웹훅 미설정 시 · 실습용)."""
    print("\n----- 미리보기 (SLACK_WEBHOOK_URL 미설정 → 전송 대신 출력) -----")
    for b in blocks:
        if b["type"] == "header":
            print(b["text"]["text"])
        elif b["type"] == "section":
            print(re.sub(r"<([^|>]+)\|([^>]+)>", r"\2", b["text"]["text"]).replace("*", ""))
        elif b["type"] == "context":
            print(b["elements"][0]["text"])
    print("-" * 60)


def send_to_slack(blocks: list, webhook_url: str, label: str = "채널1") -> bool:
    if not webhook_url:
        print_preview(blocks)
        return True
    # Slack Block Kit 최대 50블록 제한 → 초과 시 분할 전송
    CHUNK = 48
    chunks = [blocks[i:i+CHUNK] for i in range(0, len(blocks), CHUNK)]
    success = True
    for idx, chunk in enumerate(chunks):
        payload = {"blocks": chunk, "unfurl_links": False, "unfurl_media": False}
        try:
            res = requests.post(webhook_url, json=payload, timeout=10)
            res.raise_for_status()
            print(f"[Slack 전송 완료] {label} 파트{idx+1} {res.status_code}")
        except Exception as e:
            print(f"[Slack 전송 오류] {label} 파트{idx+1}: {e}")
            success = False
    return success


# ============================================================
# 메인
# ============================================================
def main():
    print(f"=== Boosters 뉴스 브리핑 시작: {datetime.now(KST)} ===")

    config = load_keywords("keywords.yml")

    # 카테고리별 뉴스 수집 (중복 제거 포함)
    categorized = collect_by_category(config)

    # 경쟁사 기사 Jev 판단 (라벨링 + 심층·기획·칼럼 제외)
    categorized = apply_jev(categorized, config)

    # Slack 전송 — 채널1 (#pr_research)
    blocks = build_slack_blocks(categorized, config)
    send_to_slack(blocks, SLACK_WEBHOOK_URL, "채널1")

    # Slack 전송 — 채널2 (선택). settings.channel2_categories 지정 시 해당 카테고리만 전송
    if SLACK_WEBHOOK_URL_2:
        only = config["settings"].get("channel2_categories") or []
        subset = {k: v for k, v in categorized.items() if k in only} if only else categorized
        blocks2 = build_slack_blocks(subset, config)
        send_to_slack(blocks2, SLACK_WEBHOOK_URL_2, "채널2")

    print("=== 완료 ===")


if __name__ == "__main__":
    main()
