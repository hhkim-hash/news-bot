"""
jev_news_judge.py
경쟁사 기사에 대해 '우리(이퀄베리)에게 유리/불리한지'를 Jev로 판단하는 모듈.

파이프라인 위치: 수집 → 중복 제거 → [여기: judge()] → Haiku 요약 → Slack

- 경쟁사 기사만 Jev를 호출합니다 (비용 절감).
- 심층·기획·칼럼 기사는 건너뜁니다 (skip=True). 단, 유형 판단이 불확실하면 건너뛰지 않습니다.
- Jev 호출이 실패해도 파이프라인은 멈추지 않습니다 (label="❔ 판단 불가").

환경변수:
  TYPESAFE_API_KEY  (필수)
  TYPESAFE_MODEL    (선택, 기본 jev-latest)

사용:
  from jev_news_judge import judge
  v = judge({"title": "...", "description": "...", "competitor": "브랜드A"})
  if v.skip: continue
  slack_text = f"{v.label} {title}"

검증(직접 라벨링한 기사와 비교):
  python jev_news_judge.py articles.json results.csv
  articles.json = [{"title":..., "description":..., "competitor":...}, ...]
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any

import requests

# ------------------------------------------------------------------ 설정
API_URL = "https://api.typesafe.ai/v1/systemone"
MODEL = os.getenv("TYPESAFE_MODEL", "jev-latest")
TIMEOUT_SEC = 15
MAX_RETRIES = 2

CONF_MIN = 0.60      # 이 값 미만이면 해당 판단은 '보류'
RISK_MIN = 0.80      # is_risk가 이 값 이상이면 리스크 강조

# 외부 API로 전송되는 문구입니다. 브랜드명과 카테고리 정도만 넣고 대외비는 넣지 마세요.
OUR_CONTEXT = "우리 회사: 이퀄베리(K-뷰티 브랜드)."

# ------------------------------------------------------------------ 질문 정의
# ※ Choice/Score의 criteria 필드 형식은 TypeSafe API 레퍼런스와 다르면 이 블록만 고치면 됩니다.
QUESTIONS: dict[str, dict[str, Any]] = {
    "article_type": {
        "type": "choice",
        "instructions": "이 기사의 유형은 무엇인가? 제목과 요약 문장의 성격을 기준으로 판단한다.",
        "criteria": {
            "news": "단신·보도: 사건, 발표, 실적, 출시 등을 사실 위주로 전하는 기사",
            "deep": "심층·기획·칼럼: 분석, 해설, 기획 연재, 오피니언, 인터뷰 등 긴 호흡의 기사",
            "promo": "광고성·홍보: 보도자료성 홍보, 이벤트, 제품 소개",
            "other": "그 외",
        },
    },
    "direction": {
        "type": "score",
        "instructions": (
            "이 기사 내용이 이퀄베리의 시장 입지에 미치는 영향의 방향은? "
            "경쟁사에 좋은 소식(투자 유치, 매출 급성장, 대형 유통 입점)은 우리에게 불리하고, "
            "경쟁사에 나쁜 소식(리콜, 논란, 실적 부진)은 우리에게 유리할 수 있다. "
            "반드시 경쟁사가 아니라 이퀄베리 입장에서 판단한다."
        ),
        "criteria": [
            "불리: 경쟁사의 입지 강화 등으로 이퀄베리에 불리한 내용",
            "중립: 이퀄베리에 뚜렷한 유불리가 없는 내용",
            "유리: 경쟁사의 악재 등으로 이퀄베리에 유리하거나 기회가 되는 내용",
        ],
    },
    "impact": {
        "type": "score",
        "instructions": "이 기사가 이퀄베리에 미치는 영향의 크기는?",
        "criteria": [
            "거의 없음: 이퀄베리와 사실상 무관",
            "참고 수준: 알아두면 좋은 정도",
            "즉시 검토 필요: 전략이나 대응을 바로 검토해야 하는 수준",
        ],
    },
    "is_risk": {
        "type": "noul",
        "instructions": "이 기사는 이퀄베리 또는 K-뷰티 카테고리 전반의 평판 리스크가 될 수 있는 이슈인가?",
    },
}


# ------------------------------------------------------------------ 결과 구조
@dataclass
class Verdict:
    skip: bool = False          # True면 이후 단계(Haiku 등)에서 제외
    label: str = ""             # Slack에 붙일 라벨 (빈 문자열이면 라벨 없음)
    article_type: str = ""
    direction: int | None = None    # 0 불리 / 1 중립 / 2 유리
    impact: int | None = None       # 0 / 1 / 2
    risk: float | None = None
    direction_conf: float | None = None
    error: str = ""


# ------------------------------------------------------------------ Jev 호출
def _build_state(article: dict) -> str:
    title = (article.get("title") or "").strip()
    desc = (article.get("description") or "").strip()
    comp = (article.get("competitor") or "").strip()
    head = OUR_CONTEXT + (f" 관련 경쟁사: {comp}." if comp else "")
    return f"{head}\n\n[기사 제목] {title}\n[기사 요약] {desc}"


def _call_jev(state: str) -> dict:
    key = os.environ["TYPESAFE_API_KEY"]
    payload = {"state": state, "model": MODEL, "questions": QUESTIONS}
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=TIMEOUT_SEC)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r.json()["answers"]
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Jev 호출 실패: {last_err}")


# ------------------------------------------------------------------ 판단 로직
def _label(direction: int, impact: int, dir_conf: float, risk: float) -> str:
    if dir_conf < CONF_MIN:
        base = "❔ 판단 보류"
    elif impact == 0:
        base = ""
    elif direction == 0 and impact >= 2:
        base = "🔴 불리·검토 필요"
    elif direction == 0:
        base = "🟠 불리·참고"
    elif direction == 2 and impact >= 2:
        base = "🟢 기회"
    elif direction == 2:
        base = "🟢 유리·참고"
    else:
        base = "⚪ 중립"

    if risk >= RISK_MIN:
        base = (base + " ⚠️ 리스크 이슈").strip()
    return base


def judge(article: dict) -> Verdict:
    """경쟁사 기사 1건을 판단. 경쟁사 기사가 아니면 Jev를 호출하지 않는다."""
    if not article.get("competitor"):
        return Verdict()

    try:
        ans = _call_jev(_build_state(article))
    except Exception as e:  # 파이프라인은 계속 진행
        return Verdict(label="❔ 판단 불가", error=str(e))

    atype = ans["article_type"]
    type_choice = atype.get("choice", "")
    type_conf = float(atype.get("confidence", 0.0))

    # 심층 기사 제외. 유형이 불확실하면 놓치지 않도록 제외하지 않는다.
    if type_choice == "deep" and type_conf >= CONF_MIN:
        return Verdict(skip=True, article_type=type_choice)

    d = ans["direction"]
    direction = int(round(float(d["score"])))
    dir_conf = float(d.get("confidence", 0.0))
    impact = int(round(float(ans["impact"]["score"])))
    risk = float(ans["is_risk"].get("noul", 0.0))

    return Verdict(
        label=_label(direction, impact, dir_conf, risk),
        article_type=type_choice,
        direction=direction,
        impact=impact,
        risk=risk,
        direction_conf=dir_conf,
    )


# ------------------------------------------------------------------ 검증용 CLI
def _run_eval(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as f:
        articles = json.load(f)

    rows = []
    for a in articles:
        v = judge(a)
        rows.append({"title": a.get("title", ""), "competitor": a.get("competitor", ""), **asdict(v)})
        print(f"{v.label or '(라벨 없음)':<18} skip={v.skip!s:<5} {a.get('title', '')[:40]}")

    with open(dst, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n저장: {dst}  (직접 라벨링한 열과 비교해 보세요)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python jev_news_judge.py articles.json results.csv")
        sys.exit(1)
    _run_eval(sys.argv[1], sys.argv[2])
