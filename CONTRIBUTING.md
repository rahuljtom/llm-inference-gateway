# Contributing to LLM Inference Gateway

First off, thank you for considering contributing to the LLM Inference Gateway! We value your time and efforts. 

The following is a set of guidelines for contributing to this repository. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this document in a pull request.

## Project Architecture

The gateway is composed of:
- FastAPI async backend
- Redis caching/rate limiting
- PostgreSQL telemetry storage
- Provider abstraction layer
- OpenAI-compatible routing APIs

## Development Guidelines

- New providers should inherit from BaseProvider
- Avoid blocking IO inside async request paths
- All upstream provider calls should use httpx.AsyncClient
- Streaming responses should preserve SSE compatibility

## How Can I Contribute?

### Reporting Bugs
If you find a bug, please create an issue containing:
- A clear and descriptive title.
- Steps to reproduce the behavior.
- Expected vs. actual behavior.
- Any relevant logs or screenshots.

### Suggesting Enhancements
Enhancement suggestions are tracked as GitHub issues. When creating an enhancement issue, please provide:
- A clear and descriptive title.
- A detailed description of the proposed feature.
- Why this enhancement would be useful to most users.
- Any relevant examples or mockups.

### Pull Requests
1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes (run `pytest`).
5. Make sure your code adheres to standard Python formatting (`black` / `ruff`).

## Setting Up for Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/rahuljtom/llm-inference-gateway
   ```
2. **Install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Run the infrastructure:**
   ```bash
   docker compose up -d
   ```
4. **Run the application:**
   ```bash
   uvicorn app.main:app --reload
   ```

Thank you for contributing!
