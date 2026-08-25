"""스몰토크 주제 생성 로직.
무료 주제는 앞에서부터 공개, 나머지는 잠금(premium) 처리.
OpenRouter LLM 호출, 실패 시 로컬 폴백.
"""
import os
import random

import httpx

from prompts import FALLBACK_TOPICS, SAFE_SUGGESTIONS, build_prompt

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("SMALLTALK_MODEL", "stealth/ox-alpha")


def _system_prompt() -> str:
    return (
        "당신은 한국 직장인·일반인이 실제 대화에 바로 쓸 수 있는 스몰토크를 만드는 전문가입니다. "
        "요청된 HTML 구조 그대로만 출력하세요."
    )


def generate_locally(situation: str, counterpart: str, avoid: list | None, total: int = 10):
    """LLM 없이도 동작하는 폴백 생성기."""
    pool = list(FALLBACK_TOPICS)
    random.shuffle(pool)
    topics = pool[:total]
    tips = SAFE_SUGGESTIONS[:]
    random.shuffle(tips)
    return {"source": "local", "topics": topics, "tips": tips[:2]}


def _parse_topics(text: str) -> list | None:
    """LLM HTML 응답에서 .topic 블록 추출. 실패 시 None."""
    import re
    blocks = re.findall(
        r"<div class=\"topic\">(.*?)</div>", text, re.S,
    )
    if not blocks:
        # 대안 파싱: h3 기반
        blocks_alt = re.findall(r"<h3>(.*?)</h3>(.*?)(?=<h3>|$)", text, re.S)
        if not blocks_alt:
            return None
        out = []
        for title, body in blocks_alt:
            opener = re.search(r"<p[^>]*>(.*?)</p>", body, re.S)
            followups = re.findall(r"<li>(.*?)</li>", body, re.S)
            out.append({
                "title": title.strip(),
                "opener": opener.group(1).strip() if opener else "",
                "followups": [f.strip() for f in followups],
            })
        return out or None

    out = []
    for b in blocks:
        title = re.search(r"<h3>(.*?)</h3>", b, re.S)
        opener = re.search(r"class=\"opener\">(.*?)</p>", b, re.S)
        followups = re.findall(r"<li>(.*?)</li>", b, re.S)
        out.append({
            "title": title.group(1).strip() if title else "",
            "opener": opener.group(1).strip() if opener else "",
            "followups": [f.strip() for f in followups],
        })
    return [t for t in out if t["title"]] or None


def generate(situation: str, counterpart: str = "", avoid: list | None = None, total: int = 10):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    result = None

    if api_key and MODEL:
        try:
            resp = httpx.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": _system_prompt()},
                        {"role": "user", "content": build_prompt(situation, counterpart, avoid, count=total)},
                    ],
                    "temperature": 0.85,
                },
                timeout=45,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                topics = _parse_topics(content)
                if topics:
                    result = {"source": "llm", "topics": topics, "tips": SAFE_SUGGESTIONS[:2]}
        except Exception:
            pass

    if result is None:
        result = generate_locally(situation, counterpart, avoid, total=total)

    # 무료/프리미엄 분리
    from prompts import FREE_TOPIC_COUNT
    free_n = min(FREE_TOPIC_COUNT, len(result["topics"]))
    topics = [
        {**t, "locked": i >= free_n}
        for i, t in enumerate(result["topics"])
    ]
    return {**result, "free_count": free_n, "premium_count": max(len(topics) - free_n, 0), "topics": topics}
