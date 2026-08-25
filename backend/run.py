"""Render 배포용 엔트리포인트.
Render는 PORT 환경변수를 주입하므로 이를 바인딩합니다.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
