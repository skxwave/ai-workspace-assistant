dev:
    uv run fastapi dev

infra state="up -d":
    docker-compose -f docker-compose.yml {{state}} db qdrant redis

app state="up -d":
    docker-compose -f docker-compose.yml {{state}}

seed-db:
    uv run scripts/seed_db.py

makemigrations message="":
    uv run alembic revision --autogenerate -m "{{message}}"

migrate to="head":
    uv run alembic upgrade {{to}}
