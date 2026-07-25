# AI Workspace Assistant
The idea was to create internal AI assistant which can:
- Answer questions regarding code-base / documentation
- Invoke internal tools
- Integrate with different services through MCP tools
- Use Vector DB for knowledge retrieval (RAG)
- Work through WebSocket for real-time chat

## Usage
1. Install `uv` package manager
2. Create virtual environment with `uv venv .venv`
3. Sync dependencies with `uv sync`; use `--dev` flag to sync development dependencies
4. Run infrastructure with `docker-compose up -d` or using `justfile` with `just infra`; run `just infra down` to stop
5. Run the dev app with `uv run fastapi dev` or with `just dev`
