dev:
    uv run fastapi dev

infra state="up -d":
    docker-compose -f docker-compose.yml {{state}}

seed-db:
    uv run scripts/seed_db.py
