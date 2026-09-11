# AI Workspace Assistant

AI Workspace Assistant is an internal AI assistant for engineers that combines conversational support, retrieval-augmented knowledge access, and tool integrations to help with everyday development work. It is designed to answer questions about code and documentation, interact with internal systems, and connect to external services through MCP tools.

## Overview

This project provides a practical foundation for building an engineering assistant that can:

- answer questions about the codebase and documentation
- retrieve relevant knowledge with RAG
- invoke internal and external tools
- support real-time chat over WebSocket
- serve as a flexible base for extending assistant capabilities

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
