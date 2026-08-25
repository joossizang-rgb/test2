"""스몰토크 SaaS — FastAPI 메인 앱 (클릭형 + 무료/프리미엄 + 일일 캐시)."""
import json
import os
import random
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from generator import generate
from news_source import fetch_news
from payment import PRICE, new_order_id, verify_payment
from prompts import ALLERGIES, FREE_TOPIC_COUNT, SITUATIONS
from wiki_source import fetch_interesting

# 서버 기동 후 백그라운드로 일일 캐시 생성 (포트 바인딩을 막지 않음)
from batch_worker import start_background_batch

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / ".." / "frontend"

app = FastAPI(title="스몰토크 SaaS MVP", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    # 로컬 개발 + Cloudflare Pages 도메인 (배포 후 실제 주소로 교체/추가)
    allow_origin_regex=r"https://.*\.(pages\.dev|localhost)$|^http://localhost(:\d+)?$",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """기동 직후 백그라운드에서 일일 캐시 생성 (포트는 즉시 열림)."""
    start_background_batch()


@app.get("/api/meta")
def meta():
    """클릭형 UI에 필요한 모든 선택지를 한 번에 제공."""
    return {
        "situations": SITUATIONS,
        "allergies": ALLERGIES,
        "free_count": FREE_TOPIC_COUNT,
    }


@app.get("/api/generate")
def api_generate(
    situation: str = "hoesik",
    counterpart: str = "",
    avoid: str = "",  # 쉼표 구분: "politics,money"
):
    """상황별 주제 — 사전 생성 풀(cache/scenario_*.json)에서 무작위 추출.
    풀이 없으면 실시간 폴백.
    """
    avoid_list = [a for a in avoid.split(",") if a]

    # 1) 캐시된 풀 조회
    cache_dir = BASE_DIR / "cache"
    slug = re.sub(r"[^\w가-힣]+", "", counterpart)[:20]
    pool_file = cache_dir / f"scenario_{situation}_{slug}.json"
    if pool_file.exists():
        try:
            data = json.loads(pool_file.read_text(encoding="utf-8"))
            topics = data.get("topics", [])
            if len(topics) >= 5:
                picked = random.sample(topics, k=min(10, len(topics)))
                free_n = min(FREE_TOPIC_COUNT, len(picked))
                marked = [
                    {**t, "locked": i >= free_n}
                    for i, t in enumerate(picked)
                ]
                return {
                    "source": data.get("source", "llm_pool"),
                    "free_count": free_n,
                    "premium_count": max(len(marked) - free_n, 0),
                    "topics": marked,
                }
        except Exception:
            pass

    # 2) 실시간 폴백 (풀 없을 때만)
    result = generate(situation, counterpart, avoid_list, total=10)
    return result


@app.post("/api/unlock")
def api_unlock():
    """결제 완료 후 프리미엄 해제 스텁.
    실제 결제 PG 연동 전까지는 항상 success 반환.
    """
    return {
        "success": True,
        "message": "프리미엄 주제가 해제되었습니다.",
    }


class VerifyRequest(BaseModel):
    imp_uid: str
    merchant_uid: str


@app.get("/api/config")
def api_config():
    """프론트에 필요한 공개 설정값 (포트원 공개 키 등)."""
    return {
        "portone_imp_key": os.environ.get("PORTONE_IMP_KEY", ""),
    }


@app.get("/api/order/new")
def api_order_new():
    """결제 직전 고유 주문번호 발급."""
    return {"merchant_uid": new_order_id(), "amount": PRICE}


@app.post("/api/verify")
def api_verify(req: VerifyRequest):
    """포트원 결제 검증 → 성공 시 프리미엄 해제 토큰 반환."""
    result = verify_payment(req.imp_uid)
    if result.get("verified"):
        # unlock_token: 기기 식별용 간단 토큰 (실서비스는 DB 저장 권장)
        unlock_token = f"unlocked_{req.merchant_uid}"
        return {
            "success": True,
            "unlock_token": unlock_token,
            "demo": result.get("demo", False),
            "message": "결제 확인 완료! 프리미엄이 해제되었습니다.",
        }
    return {"success": False, "message": result.get("message", "결제 검증 실패")}


@app.get("/api/news")
def api_news(n: int = 5):
    """'오늘의 화제' — 새벽 배치로 생성된 캐시를 즉시 제공 (LLM 비용 0)."""
    cache_dir = BASE_DIR / "cache"
    latest_path = cache_dir / "latest.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        news_file = cache_dir / latest["news_file"]
        if news_file.exists():
            data = json.loads(news_file.read_text(encoding="utf-8"))
            topics = data["topics"][:n]
            return {**data, "topics": topics, "free_count": min(n, len(topics))}

    # 캐시 없음 → 실시간 폴백
    try:
        items = fetch_news(n=n)
    except Exception:
        items = []

    if items:
        topics = [
            {
                "title": it["title"],
                "opener": "이거 봤어요? 요즘 다들 얘기하던데, 한번 보게 되더라고요.",
                "hook": it.get("hook", ""),
                "summary": it.get("hook", ""),
                "url": it.get("url", ""),
                "source_name": it.get("source", ""),
                "locked": False,
            }
            for it in items
        ]
        return {"source": "news", "free_count": len(topics), "premium_count": 0,
                "topics": topics,
                "tips": ["'이거 봤어요?' 같은 뉴스 핵심만 3줄로 요약해서 말하기",
                         "상대 의견 물어보면 대화가 길어지는 화제입니다"]}

    # 폴백
    result = generate("family", "친구", [], total=n)
    topics = [
        {**t, "url": None, "summary": "", "hook": "", "source_name": ""}
        for t in result["topics"]
    ]
    return {"source": "local_topic", "free_count": len(topics), "premium_count": 0,
            "topics": topics, "tips": ["뉴스 화제를 잠시 못 불러왔어요. 일상 주제로 대신 준비했어요."]}


@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/facts")
def api_facts(n: int = 5):
    """'신기한 사실' — 새벽 배치 캐시 제공 (LLM 비용 0).
    캐시 없으면 실시간 수집 후 폴백.
    """
    cache_dir = BASE_DIR / "cache"
    latest_path = cache_dir / "latest.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        facts_file = cache_dir / latest["facts_file"]
        if facts_file.exists():
            data = json.loads(facts_file.read_text(encoding="utf-8"))
            topics = data["topics"][:n]
            return {**data, "topics": topics, "free_count": min(n, len(topics))}

    # 캐시 없음 → 실시간 폴백
    try:
        items = fetch_interesting(n=n)
    except Exception as e:
        items = []
        print(f"[facts] 실시간 수집 예외: {e}", flush=True)

    if not items:
        print("[facts] 0개 — featured 목록 로드 또는 필터 문제 의심", flush=True)

    if items:
        topics = [
            {
                "title": it["title"],
                "opener": f"혹시 '{it['title']}'에 대해 들어본 적 있어요? 아는 분 드물어요.",
                "hook": it.get("hook", ""),
                "summary": it["summary"],
                "url": it["url"],
                "locked": False,
            }
            for it in items
        ]
        return {"source": "wikipedia", "free_count": len(topics), "premium_count": 0,
                "topics": topics,
                "tips": ["출처: 위키백과 (CC BY-SA, 링크 확인)",
                         "모르는 주제라면 '처음 들었어요, 뭔가요?'라고 물어보며 대화를 시작해 보세요"]}

    # 폴백: 일상 화제
    result = generate("family", "친구", [], total=n)
    topics = [
        {**t, "url": None, "summary": ""}
        for t in result["topics"]
    ]
    return {"source": "local_topic", "free_count": len(topics), "premium_count": 0,
            "topics": topics, "tips": ["위키백과 화제를 잠시 못 불러왔어요. 일상 주제로 대신 준비했어요."]}


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
