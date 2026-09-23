install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload
	
test:
	pytest -q

eval:
	python -m app.evaluation.run_eval

up:
	docker compose up --build

down:
	docker compose down

ingest:
	python -m app.rag.ingestion


#Make test, make up, make down etc- shortcut for this