# Amazon Prism Backend

## Setup

```bash
cd backend
python -m venv .venv
./.venv/Scripts/pip.exe install -r ../requirements.txt
cd ..
cp .env.example .env
docker compose up -d
cd backend
./.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Test Flow

1. Create a return case with `POST /return-cases`.
2. Upload PRECHECK media with `POST /return-cases/{id}/media`.
3. Submit PRECHECK AI output manually with `POST /return-cases/{id}/ai-assessment`.
4. Upload FINAL_CHECK media with `POST /return-cases/{id}/final-check` or `POST /return-cases/{id}/media` using `FINAL_CHECK`.
5. Submit FINAL_CHECK AI output manually with `POST /return-cases/{id}/ai-assessment`.
6. If the latest routing decision has vendor permission `PENDING`, submit `POST /return-cases/{id}/vendor-decision`.
7. Inspect outputs with:
   - `GET /return-cases`
   - `GET /return-cases/{id}`
   - `GET /return-cases/{id}/health-card`
   - `GET /return-cases/{id}/listing-preview`
