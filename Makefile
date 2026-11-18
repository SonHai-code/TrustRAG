up:        ; docker compose up -d
down:      ; docker compose down
ingest:    ; python -m ingestion.cli ingest --input data/raw
sample:    ; python -m ingestion.cli ingest --input data/sample
search:    ; python -m ingestion.cli search "$(q)"
test:      ; pytest -q
api:       ; uvicorn api.main:app --reload --port 8000
baseline:  ; python -m scripts.baseline --label "$(or $(label),baseline)"
