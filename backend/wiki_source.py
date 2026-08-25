"""위키백과 '알찬 글' 기반 '신기한 사실' 생성.

알찬 글(Featured Articles)은 위키백과가 자체 선정한 최고 품질 문서로,
일반 무작위 문서보다 요약의 밀도·완성도가 확실히 높습니다.
- 라이선스: CC BY-SA (상업 이용 + 출처 표기 조건 충족)
- 목록: featured_articles.txt (148개, 주기적 갱신 가능)
"""
import random
import re
from pathlib import Path

import httpx

WIKI = "https://ko.wikipedia.org"
UA = {"User-Agent": "SmalltalkSaaS/0.4 (conversation topic generator; contact: local)"}

FEATURED_LIST = Path(__file__).resolve().parent / "featured_articles.txt"

# 대화에 부적절하거나 무거운 주제 배제
SENSITIVE = [
    "성교", "성관계", "자살", "시체", "살인", "음란", "포르노",
    "고문", "학살", "마약", "생식기", "성매매", "대지진", "테러",
    "전쟁", "처형", "독립유공자", "순교", "재판", "강간",
]


def _load_featured() -> list[str]:
    if FEATURED_LIST.exists():
        return [l.strip() for l in FEATURED_LIST.read_text(encoding="utf-8").splitlines() if l.strip()]
    return []


def _summary_many(titles: list[str]) -> dict[str, dict]:
    """여러 문서를 한 번의 요청으로 일괄 요약."""
    r = httpx.get(
        f"{WIKI}/w/api.php",
        params={
            "action": "query", "titles": "|".join(titles),
            "prop": "extracts", "exintro": True, "explaintext": True,
            "format": "json", "redirects": 1,
        },
        headers=UA, timeout=10,
    )
    pages = r.json()["query"]["pages"]
    out = {}
    for pid, page in pages.items():
        if "missing" in page or "extract" not in page:
            continue
        title = page["title"]
        out[title] = {
            "title": title,
            "summary": page["extract"].strip(),
            "url": f"{WIKI}/wiki/{title.replace(' ', '_')}",
        }
    return out


def _make_hook(summary: str) -> str:
    """요약에서 괄호·발음·각주 제거 후 첫 문장만 추출."""
    s = summary.strip()
    s = re.sub(r"\([^)]*\)", "", s)          # (한자/영어/발음)
    s = re.sub(r"\[\*\]|\[\d+\]", "", s)     # 각주
    s = re.sub(r"\s+", " ", s).strip()
    m = re.search(r"^(.*?[다요음임함].?)\s", s + " ")
    first = (m.group(1) if m else s)[:150]
    return first.strip()


def _is_suitable(summary: str, title: str) -> bool:
    """대화 소재 적합성 검사."""
    combined = title + " " + summary
    if any(k in combined for k in SENSITIVE):
        return False
    # 너무 짧거나 불완전한 요약 배제
    s = summary.strip()
    if len(s) < 40:
        return False
    return True


def fetch_featured(n: int = 5, max_attempts: int = 4) -> list[dict]:
    """알찬 글 목록에서 무작위 n개의 화제 카드 생성."""
    pool = _load_featured()
    if not pool:
        return []

    seen = set()
    out = []
    attempts = 0
    while len(out) < n and attempts < max_attempts:
        attempts += 1
        candidates = [t for t in random.sample(pool, k=min(15, len(pool))) if t not in seen]
        if not candidates:
            continue
        summaries = _summary_many(candidates)
        for title, data in summaries.items():
            if len(out) >= n:
                break
            if title in seen or not _is_suitable(data["summary"], title):
                continue
            hook = _make_hook(data["summary"])
            # 후크가 너무 짧으면 (제목 반복만 하는 등) 배제
            if len(hook) < 25 or hook.replace(" ", "").startswith(title.replace(" ", "")):
                continue
            seen.add(title)
            data["hook"] = hook
            data["category"] = "알찬 글"
            out.append(data)
    return out


# 하위호환: 기존 함수명 유지 (main.py 등에서 호출)
def fetch_interesting(n: int = 5, **kwargs) -> list[dict]:
    return fetch_featured(n=n)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    items = fetch_featured(n=6)
    print(f"알찬 글 기반 {len(items)}개:")
    for it in items:
        print(f"• [{it['category']}] {it['title']}")
        print(f"  {it['hook'][:90]}")
