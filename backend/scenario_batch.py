"""상황별 대화 주제 '풀'을 미리 생성해 저장하는 배치.
시간 민감성이 없는 콘텐츠라 한 번에 대량 생성 → 사용자 요청 시 무작위 추출.
품질은 실시간 생성과 동일 (같은 LLM·프롬프트), 비용은 사전 1회.

실행:
    python scenario_batch.py          # 전체 콤보 생성
    python scenario_batch.py hoesik   # 특정 상황만 재생성
"""
import json
import os
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from prompts import SITUATIONS

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

TOPICS_PER_COMBO = 15  # 콤보당 생성 개수 (풀 크기)


def _slug(text: str) -> str:
    """파일명용 슬러그 (한글 유지, 특수문자 제거)."""
    return re.sub(r"[^\w가-힣]+", "", text)[:20]


def _combo_key(situation: str, counterpart: str) -> str:
    return f"{situation}_{_slug(counterpart)}"


def _llm_call(prompt: str) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("SMALLTALK_MODEL", "stealth/ox-alpha")
    if not api_key or not model:
        return ""
    try:
        r = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,
            },
            timeout=60,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
    except Exception:
        pass
    return ""


def _build_pool_prompt(situation: str, counterpart: str, n: int) -> str:
    s = SITUATIONS[situation]
    avoid_line = ""
    if situation == "hoesik":
        avoid_line = "\n- 연봉·정치·종교·결혼 압박 같은 금지 화제는 절대 포함하지 말 것."
    return f"""당신은 한국 직장인·일반인의 스몰토크 전문가입니다.
상황: {s['label']} — {s['desc']}
상대: {counterpart}
{avoid_line}

요구사항:
- 서로 다른 방향의 대화 주제 정확히 {n}개를 만들어 주세요.
- 각 주제는 아래 JSON 구조로:
  {{"title": "주제 제목", "opener": "이렇게 꺼내보세요: ~", "followups": ["후속질문1", "후속질문2"]}}
- opener는 실제 입에 담을 자연스러운 존댓말 한 문장.
- followups는 대화를 이어갈 후속 질문 2개.
- 단답형 예/아니오 질문 금지 — 상대가 이야기를 펼칠 수 있는 열린 주제.
- 출력은 JSON 배열 [ ... ] 만. 설명·코드블록 없이."""


def _parse_topics(content: str) -> list[dict]:
    """LLM 응답에서 JSON 배열 파싱."""
    # 코드블록 제거
    content = re.sub(r"```(?:json)?|```", "", content).strip()
    m = re.search(r"\[.*\]", content, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for t in arr:
        if isinstance(t, dict) and t.get("title"):
            out.append({
                "title": t["title"].strip(),
                "opener": t.get("opener", "").strip(),
                "followups": [f.strip() for f in t.get("followups", [])][:3],
            })
    return out


def build_scenario_pools(only_situation: str | None = None):
    """모든 상황×상대 콤보의 주제 풀 생성."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    model = os.environ.get("SMALLTALK_MODEL", "stealth/ox-alpha")
    print(f"LLM: {'활성 (' + model + ')' if api_key and model else '비활성 — 폴백 풀 사용'}")

    total_generated = 0
    for sit_key, sit_info in SITUATIONS.items():
        if only_situation and sit_key != only_situation:
            continue
        for counterpart in sit_info["counterparts"]:
            key = _combo_key(sit_key, counterpart)
            out_path = CACHE_DIR / f"scenario_{key}.json"
            if out_path.exists():
                print(f"  ⏭️  {key} 이미 있음 (스킵)")
                continue

            prompt = _build_pool_prompt(sit_key, counterpart, TOPICS_PER_COMBO)
            content = _llm_call(prompt) if api_key else ""
            topics = _parse_topics(content) if content else []

            if len(topics) < TOPICS_PER_COMBO // 2:
                print(f"  ⚠️  {key}: LLM 응답 부족({len(topics)}개) — 재시도 1회")
                content = _llm_call(prompt)
                topics = _parse_topics(content) if content else topics

            payload = {
                "source": "llm_pool" if topics else "fallback",
                "situation": sit_key,
                "counterpart": counterpart,
                "pool_size": len(topics),
                "topics": topics,
            }
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                encoding="utf-8")
            total_generated += len(topics)
            print(f"  ✓ {key}: {len(topics)}개 저장")

    print(f"\n완료 — 총 {total_generated}개 주제")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    build_scenario_pools(target)
