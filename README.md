# AI Workspace Assistant

AI Workspace Assistant is an internal AI assistant for engineers, designed to support everyday development tasks and streamline engineering workflows. It helps answer questions about the codebase and documentation, use internal tools, and connect with external services through MCP tools.

## What it can do

- Answer questions about the codebase and documentation
- Invoke internal tools
- Integrate with different services through MCP tools
- Use a vector database for knowledge retrieval (RAG)
- Work through WebSocket for real-time chat

## Quick start

### Prerequisites

- Install [`uv`](https://docs.astral.sh/uv/)
- Install Docker and Docker Compose

### Setup

1. Create a virtual environment:
   ```bash
   uv venv .venv
   ```
2. Sync dependencies:
   ```bash
   uv sync
   ```
   To include development dependencies, run:
   ```bash
   uv sync --dev
   ```
3. Start infrastructure:
   ```bash
   docker-compose up -d
   ```
   Or use the Just command:
   ```bash
   just infra
   ```
4. Run the development app:
   ```bash
   uv run fastapi dev
   ```
   Or use:
   ```bash
   just dev
   ```

### Stopping infrastructure

To stop infrastructure:

```bash
just infra down
```

## Developer experience notes

- `just infra` starts required local services
- `just dev` runs the app in development mode
- `uv sync --dev` installs developer dependencies

## Goal

The project aims to provide a practical internal AI assistant that supports engineering workflows with retrieval, tool usage, and real-time interaction.
