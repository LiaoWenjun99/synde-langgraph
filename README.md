# SynDe LangGraph

A clean, testable LangGraph implementation for protein engineering workflows.

## Overview

This project provides a standalone LangGraph-based workflow system for protein engineering tasks:
- **Prediction**: EC number, kcat, Tm, stability predictions
- **Generation**: ProGen2 and ZymCTRL sequence optimization
- **Structure**: ESMFold and AlphaFold structure prediction

## Features

- **Clean Architecture**: Separated from Django dependencies for easier testing
- **Mock GPU Mode**: Test workflows without GPU resources
- **CLI Tool**: Interactive testing and debugging
- **Comprehensive Tests**: Unit and integration test suites
- **Shared Infrastructure**: Uses same Redis/Celery setup as synde-minimal

## Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Quick Start

### Run with Mock GPU (Testing)

```bash
# Using CLI
synde run "Predict EC number for P00720" --mock

# Using script
python scripts/run_mock.py "Predict stability" --sequence "MKTVRQ..."
```

### Test Individual Nodes

```bash
synde test-node intent_router --query "Generate thermostable variants"
synde test-node input_parser --query "Predict kcat for P00720 with ATP"
```

### Run Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# All tests with coverage
pytest --cov=synde_graph --cov-report=html
```

## Project Structure

```
synde-langgraph/
├── synde_graph/           # Core LangGraph implementation
│   ├── config.py          # Configuration settings
│   ├── graph.py           # Main graph construction
│   ├── state/             # State schema and factory
│   ├── nodes/             # Node implementations
│   ├── subgraphs/         # Prediction and generation subgraphs
│   └── routing/           # Routing functions
├── synde_gpu/             # GPU task interface
│   ├── tasks.py           # Celery task proxies
│   ├── manager.py         # Async GPU manager
│   ├── locking.py         # Distributed locks
│   └── mocks.py           # Mock responses
├── synde_checkpointer/    # Checkpointing
│   ├── memory.py          # In-memory (testing)
│   └── sqlite.py          # SQLite (CLI)
├── synde_cli/             # CLI tool
│   ├── main.py            # Typer CLI
│   └── display.py         # Rich output
├── tests/                 # Test suites
│   ├── unit/
│   └── integration/
└── scripts/               # Utility scripts
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Redis (shared with synde-minimal)
REDIS_HOST=172.31.19.34
REDIS_PORT=6379

# Celery
CELERY_BROKER_URL=redis://172.31.19.34:6379/0
CELERY_RESULT_BACKEND=redis://172.31.19.34:6379/1

# LangGraph checkpoint DB (separate from synde-minimal)
LANGGRAPH_CHECKPOINT_DB=3

# Enable mock mode for testing
MOCK_GPU=false
```

## Key Fixes from synde-minimal

1. **Distributed Lock**: Prevents race conditions on `state["active_gpu_tasks"]` updates
2. **Async GPU Pattern**: Proper async polling instead of blocking `allow_join_result()`
3. **Task Cancellation**: Uses `terminate=True` to actually stop GPU computation
4. **Pre-Submission Checkpoint**: Checkpoints before GPU submission to prevent orphans

## CLI Commands

```bash
# Run workflow
synde run "Predict stability for P00720" --mock

# Test node
synde test-node intent_router --query "Generate mutants"

# List nodes
synde list-nodes

# Check environment
synde check

# Debug checkpoint
synde debug job-123 --checkpoint ./test.db
```

## Workflow Architecture

```
START
  │
  ▼
intent_router ────────────────────────────┐
  │                                       │
  ▼                                       │
input_parser                              │
  │                                       │
  ├─→ prediction_subgraph ───────────────┬┤
  │     ├─ check_structure               ││
  │     ├─ run_esmfold/alphafold         ││
  │     ├─ run_fpocket                   ││
  │     └─ run_predictions               ││
  │                                      ││
  ├─→ generation_subgraph ──────────────┬┤│
  │     ├─ prepare_wt_metrics           │││
  │     ├─ run_progen2                  │││
  │     ├─ validate_mutants             │││
  │     ├─ run_zymctrl                  │││
  │     └─ sort_mutants                 │││
  │                                     │││
  ├─→ fallback_response ────────────────┼┼┤
  │                                     │││
  └─→ theory_response ──────────────────┼┼┤
                                        │││
                                        ▼▼▼
                                  response_formatter
                                        │
                                        ▼
                                       END
```

## GPU Task Proxies

This project uses Celery task signatures to call GPU tasks defined in synde-minimal:

```python
from synde_gpu.tasks import call_esmfold, call_clean_ec

# In mock mode, returns mock response directly
result = call_esmfold("job-123", "MKTVRQ...")

# In real mode, returns AsyncResult
async_result = call_esmfold("job-123", "MKTVRQ...")
```

## Web UI (Phase 2)

SynDe includes a modern ChatGPT/Claude-style web interface built with Django.

### Features

- **Conversation Threads**: Organize chats into separate conversations
- **Project Folders**: Group related conversations by project
- **Real-time Updates**: SSE-based live workflow status
- **3D Protein Viewer**: Embedded 3Dmol.js visualization
- **Dark/Light Themes**: User preference theming
- **User Authentication**: Login, signup, profile management

### Running the Web UI

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create a superuser (optional)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Start the development server
python manage.py runserver

# In another terminal, start Celery worker
celery -A synde_web worker -l info
```

### Project Structure (Web)

```
synde_web/
├── models/             # Django models
│   ├── user.py         # Extended user with profile/quota
│   ├── project.py      # Project folders
│   ├── conversation.py # Chat threads
│   ├── message.py      # Individual messages
│   └── workflow.py     # Workflow checkpoints
├── views/              # Views
│   ├── main.py         # Main pages
│   ├── auth.py         # Authentication
│   ├── api.py          # REST API
│   └── sse.py          # Server-Sent Events
├── templates/          # HTML templates
│   └── synde_web/
│       ├── base.html
│       ├── index.html
│       ├── auth/
│       └── components/
├── static/             # Static assets
│   └── synde_web/
│       ├── css/
│       └── js/
├── tasks.py            # Celery tasks
└── celery.py           # Celery config
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/` | GET/POST | List/create projects |
| `/api/projects/<id>/` | GET/PUT/DELETE | Project CRUD |
| `/api/conversations/` | GET/POST | List/create conversations |
| `/api/conversations/<id>/` | GET/PUT/DELETE | Conversation CRUD |
| `/api/conversations/<id>/messages/` | POST | Send message |
| `/api/conversations/<id>/stream/<workflow_id>/` | GET | SSE stream |
| `/api/suggestions/` | GET | Get suggestion prompts |

## License

MIT
