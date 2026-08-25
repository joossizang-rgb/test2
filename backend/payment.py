"""비회원 1회 결제 (포트원 테스트 연동).
플로우:
1. 프론트: /api/order로 merchant_uid 발급
2. 프론트: IMP.request_pay()로 결제창 호출
3. 콜백 받으면 /api/verify에 imp_uid 전송 → 서버가 포트원 REST로 실결제 확인
4. 검증 성공 → 프론트가 localStorage에 unlock 저장 (기기 내 평생)
"""
import os
import time
import secrets

import httpx

PORTONE_IMP_KEY = os.environ.get("PORTONE_IMP_KEY", "")       # 공개 클라이언트 키 (테스트)
PORTONE_API_SECRET = os.environ.get("PORTONE_API_SECRET", "") # REST 검증용 시크릿
PRICE = 900  # 건당


def new_order_id() -> str:
    """고유 주문번호 생성."""
    return f"smtk_{int(time.time())}_{secrets.token_hex(4)}"


def get_access_token() -> str | None:
    """포트원 REST API 토큰 발급."""
    if not PORTONE_API_SECRET:
        return None
    try:
        r = httpx.post(
            "https://api.iamport.kr/users/getToken",
            json={"imp_key": PORTONE_IMP_KEY, "imp_secret": PORTONE_API_SECRET},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()["response"]["access_token"]
    except Exception:
        pass
    return None


def verify_payment(imp_uid: str) -> dict:
    """포트원에서 결제내역 조회해 900원 결제 완료 여부 확인.

    시크릿 키 미설정(테스트) 시 데모 모드로 통과 처리.
    """
    if not PORTONE_API_SECRET:
        return {"verified": True, "demo": True, "amount": PRICE,
                "message": "데모 모드 — PG 키 설정 후 실검증 활성화"}

    token = get_access_token()
    if not token:
        return {"verified": False, "message": "인증 실패"}
    try:
        r = httpx.get(
            f"https://api.iamport.kr/payments/{imp_uid}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        data = r.json().get("response", {})
        amount = data.get("amount", 0)
        status = data.get("status")
        if status == "paid" and amount >= PRICE:
            return {"verified": True, "amount": amount}
        return {"verified": False, "status": status, "amount": amount}
    except Exception as e:
        return {"verified": False, "message": str(e)}
