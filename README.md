# 스몰토크 SaaS MVP
스몰토크 대화주제 생성 웹앱 — 일반인·직장인 대상

## 구조
```
backend/         FastAPI 백엔드
  main.py        앱 진입점 + /api/generate
  generator.py   LLM 호출 + 로컬 폴백 생성기
  prompts.py     상황별 프롬프트 템플릿
  requirements.txt
frontend/        정적 프론트 (HTML/CSS/JS) — backend가 서빙
  index.html
  app.js
  style.css
tests/           smoke test
```

## 실행
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export OPENROUTER_API_KEY=...(선택, 없으면 로컬 폴백)
uvicorn main:app --reload --port 8000
```
브라우저: http://localhost:8000
