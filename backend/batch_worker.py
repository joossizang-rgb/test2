"""서버 기동 직후 백그라운드에서 일일 캐시를 생성하는 워커.
Render의 포트 스캔을 막지 않도록 uvicorn 기동 '이후'에 비동기 실행.

사용: main.py의 startup 이벤트에서 호출
"""
import json
import os
import sys
import threading
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _today_fresh() -> bool:
    """오늘자 캐시가 이미 있으면 스킵."""
    latest = CACHE_DIR / "latest.json"
    if latest.exists():
        try:
            info = json.loads(latest.read_text(encoding="utf-8"))
            return info.get("date") == date.today().isoformat()
        except Exception:
            pass
    return False


def _run_batch():
    try:
        # daily_batch를 모듈로 임포트해 함수 실행
        from daily_batch import build_daily_cache
        build_daily_cache()
    except Exception as e:
        print(f"[batch-worker] 배치 실패 (무시하고 계속): {e}", flush=True)


def start_background_batch():
    """캐시가 없을 때만 백그라운드 스레드로 배치 실행."""
    if _today_fresh():
        print("[batch-worker] 오늘자 캐시 존재 — 스킵", flush=True)
        return
    t = threading.Thread(target=_run_batch, daemon=True)
    t.start()
    print("[batch-worker] 백그라운드 배치 시작", flush=True)
