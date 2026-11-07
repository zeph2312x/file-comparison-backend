# Backend Sub-repository — File Comparison Engine

FastAPI backend providing deterministic file comparison for CSV, JSON, and TXT files as specified in the MVP 1.0 PRD.

## Setup & Running

```bash
cd backend
python3 -m pip install -r requirements.txt
python3 -m uvicorn app.main:app --reload --port 8000
```

## Running Tests

```bash
PYTHONPATH=. pytest tests
```
