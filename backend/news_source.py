"""뉴스(구글 뉴스 RSS) 기반 '오늘의 화제' 생성.
스몰토크에 맞는 가벼운 소재 키워드로 검색해
정치·선정적 뉴스를 배제한 대화 소재만 추립니다.
제목·매체 기반으로 LLM이 '이야깃거리 요약'(2문장)을 생성합니다.
"""
import re
import os
import random
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

import httpx

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
GOOGLE_NEWS_SEARCH = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = os.environ.get("SMALLTALK_MODEL", "stealth/ox-alpha")

# 스몰토크에 어울리는 가벼운 소재 키워드 (정치/추문/사건 배제)
LIGHT_QUERIES = [
    '"맛집 오픈"',
    '"새로운 맛"',
    '"여행지 추천"',
    '카페 오픈 인기',
    '신작 영화 개봉',
    '인기 OTT 드라마',
    'AI 기술 일상 생활',
    '추억의 드라마',
    '이색 직업 트렌드',
    '힐링 여행',
    '전시회 개최',
    '직장인 웰빙 루틴',
]

# 선정적·추문·사고성 제목 배제 키워드
BLOCK = [
    "성관계", "불륜", "사망", "자살", "살인", "구속", "체포", "검거",
    "폭력", "성폭행", "추문", "숨져", "사고", "참사", "피해", "중상",
    "재판", "고소", "고발", "청산", "사건", "조사받",
]


def _fetch(q: str, n: int = 8) -> list[dict]:
    url = GOOGLE_NEWS_SEARCH.format(q=quote_plus(q))
    r = httpx.get(url, headers=UA, timeout=10)
    root = ET.fromstring(r.content)
    out = []
    for it in root.findall(".//item")[:n]:
        title = (it.findtext("title") or "").strip()
        # "제목 - 매체" 형태에서 제목만
        clean_title = title.split(" - ")[0].strip() if " - " in title else title
        link = (it.findtext("link") or "").strip()
        src = (it.findtext("source") or "").strip()
        if clean_title and link:
            out.append({"title": clean_title, "url": link, "source": src})
    return out


def _clean(title: str) -> str:
    """괄호·매체 표기 제거."""
    t = re.sub(r"\[[^\]]*\]", "", title)  # [사진], [속보]
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _summarize_llm(title: str, source: str) -> str:
    """제목·매체로 2문장 '이야깃거리 요약' 생성. 실패 시 빈 문자열."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key or not LLM_MODEL:
        return ""
    prompt = (
        f"다음 뉴스 헤드라인을 회식 스몰토크로 꺼내기 좋은 2문장 요약으로 만들어줘. "
        f"정치·자극 단정은 피하고, '아, 그렇구나' 하는 흥미 위주 존댓말로.\n"
        f"헤드라인: {title}\n매체: {source}\n"
        f"2문장 이하로만." 
    )
    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=90,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"].strip()
            # LLM이 부가 설명·따옴표를 붙이는 경우 정리: 본문 문장만 추출
            import re as _re
            content = _re.sub(r"\*\*([^*]+)\*\*", r"\1", content)          # 마크다운 볼드 제거
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            body_lines = [
                l for l in lines
                if not l.startswith(("이렇게 하면", "필요하면", "참고로", "※", "-", "*"))
                and len(l) > 15
            ]
            content = " ".join(body_lines)[:200]
            return content
    except Exception:
        pass
    return ""


def _filter(t: str) -> bool:
    if len(t) < 8:
        return False
    low = t.lower()
    if any(b in t for b in BLOCK):
        return False
    return True


def _local_hook(title: str, source: str) -> str:
    """LLM 키가 없을 때 쓰는 로컬 요약 (제목 기반 대화 유도 문장)."""
    return f"[{source}] 관련 기사예요. 제목이 흥미로워서 얘기 꺼내기 좋은 화제더라고요."


def fetch_news(n: int = 5, category: str | None = None) -> list[dict]:
    """구글뉴스에서 가벼운 화제 n개 수집."""
    queries = LIGHT_QUERIES
    seen = set()
    out = []
    shuffled = list(queries)
    random.shuffle(shuffled)
    for q in shuffled:
        if len(out) >= n:
            break
        try:
            items = _fetch(q)
        except Exception:
            continue
        random.shuffle(items)
        for it in items:
            if len(out) >= n:
                break
            title = _clean(it["title"])
            if title in seen or not _filter(title):
                continue
            seen.add(title)
            it["title"] = title
            # 요약: LLM 있으면 그걸, 없으면 로컬 문구
            it["hook"] = _summarize_llm(title, it.get("source", "")) or _local_hook(title, it.get("source", ""))
            out.append(it)
    return out
