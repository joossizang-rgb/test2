"""매일 새벽 배치로 '오늘의 화제'·'신기한 사실'을 미리 생성해 캐싱.
사용자 요청 시에는 만들어진 캐시를 즉시 제공 (LLM 비용 0, 응답 빠름).

사용:
    python daily_batch.py            # 지금 실행
    crontab: 0 4 * * * cd /path && python daily_batch.py
"""
import json
import os
import sys
from datetime import date
from pathlib import Path

# LLM 키 로드 (.env 또는 환경변수)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _llm_env():
    """환경변수에서 키·모델 로드 (없으면 .env 참조)."""
    key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("SMALLTALK_MODEL", "stealth/ox-alpha")
    if not model:
        model = "stealth/ox-alpha"
        os.environ["SMALLTALK_MODEL"] = model
    if not key:
        # .env 직접 파싱
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"')
    return key, model


def build_daily_cache():
    from news_source import fetch_news
    from wiki_source import fetch_interesting
    from generator import generate as gen_scenario

    api_key, model = _llm_env()
    if api_key and model:
        os.environ["OPENROUTER_API_KEY"] = api_key
        os.environ["SMALLTALK_MODEL"] = model

    today = date.today().isoformat()

    print(f"[{today}] 배치 시작")

    # 1) 오늘의 화제 (뉴스)
    print(" - 뉴스 화제 수집 중...")
    try:
        news_items = fetch_news(n=8)
    except Exception as e:
        print("   뉴스 실패:", e)
        news_items = []

    news_topics = [
        {
            "title": it["title"],
            "opener": "이거 봤어요? 요즘 다들 얘기하던데.",
            "hook": it.get("hook", ""),
            "summary": it.get("hook", ""),
            "url": it.get("url", ""),
            "source_name": it.get("source", ""),
            "locked": False,
        }
        for it in news_items
    ]
    news_payload = {
        "source": "news",
        "date": today,
        "free_count": len(news_topics),
        "premium_count": 0,
        "topics": news_topics,
        "tips": ["'이거 봤어요?' 뒤에 상대 의견 물어보면 대화가 길어져요"],
    }
    (CACHE_DIR / f"news_{today}.json").write_text(
        json.dumps(news_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   ✓ 뉴스 {len(news_topics)}개 저장")

    # 2) 신기한 사실 (위키백과)
    print(" - 위키백과 화제 수집 중...")
    try:
        wiki_items = fetch_interesting(n=8)
    except Exception as e:
        print("   위키백과 실패:", e)
        wiki_items = []

    wiki_topics = [
        {
            "title": it["title"],
            "opener": f"혹시 '{it['title']}'에 대해 들어본 적 있어요? 아는 분 드물어요.",
            "hook": it.get("hook", ""),
            "summary": it["summary"][:220],
            "url": it["url"],
            "locked": False,
        }
        for it in wiki_items
    ]
    facts_payload = {
        "source": "wikipedia",
        "date": today,
        "free_count": len(wiki_topics),
        "premium_count": 0,
        "topics": wiki_topics,
        "tips": ["출처: 위키백과 (CC BY-SA)", "모르는 주제라면 '처음 들었어요, 뭔가요?'라고 물어보며 대화를 시작해 보세요"],
    }
    (CACHE_DIR / f"facts_{today}.json").write_text(
        json.dumps(facts_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   ✓ 위키백과 {len(wiki_topics)}개 저장")

    # 3) 최신 캐시 심볼릭 링크 갱신 (latest.json)
    latest = {
        "date": today,
        "news_file": f"news_{today}.json",
        "facts_file": f"facts_{today}.json",
    }
    (CACHE_DIR / "latest.json").write_text(
        json.dumps(latest, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[{today}] 배치 완료")


if __name__ == "__main__":
    build_daily_cache()
