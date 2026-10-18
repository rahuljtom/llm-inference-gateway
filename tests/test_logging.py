from decimal import Decimal
from types import SimpleNamespace

import pytest
from starlette.responses import StreamingResponse
from starlette.requests import Request
from starlette.responses import Response

import app.middleware.logging as logging_middleware
from app.middleware.logging import LoggingMiddleware


class FakeSession:
    def __init__(self, _engine):
        self.items = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def add(self, item):
        self.items.append(item)

    async def commit(self):
        self.commits += 1


@pytest.mark.anyio
async def test_cached_response_is_not_charged_to_team_budget(monkeypatch):
    session = FakeSession(None)
    monkeypatch.setattr(logging_middleware, "AsyncSession", lambda _engine: session)
    finalized = []

    async def finalize(_session, request_id, team_id, cost):
        finalized.append((request_id, team_id, cost))

    monkeypatch.setattr(logging_middleware, "finalize_budget_reservation", finalize)
    request = Request({"type": "http", "headers": [], "state": {}})
    request.state.api_key = SimpleNamespace(id=3, team_id=11)
    request.state.provider = "groq"
    request.state.model = "llama-3.1-8b-instant"
    request.state.prompt_tokens = 20
    request.state.completion_tokens = 10
    request.state.total_tokens = 30
    request.state.cached = True
    request.state.cost_usd = 0.0

    await LoggingMiddleware(None)._persist_request(request, 0.0, Response(status_code=200))

    assert session.items[0].cost_usd == 0.0
    assert finalized == [(None, 11, 0.0)]
    assert session.commits == 1


@pytest.mark.anyio
async def test_success_without_usage_charges_reserved_estimate(monkeypatch):
    session = FakeSession(None)
    monkeypatch.setattr(logging_middleware, "AsyncSession", lambda _engine: session)
    finalized = []

    async def finalize(_session, request_id, team_id, cost):
        finalized.append((request_id, team_id, cost))

    monkeypatch.setattr(logging_middleware, "finalize_budget_reservation", finalize)
    request = Request({"type": "http", "headers": [], "state": {}})
    request.state.api_key = SimpleNamespace(id=3, team_id=11)
    request.state.provider = "openai"
    request.state.model = "gpt-4o"
    request.state.budget_reservation_id = "reservation"
    request.state.budget_reservation_amount = Decimal("0.04")
    request.state.cached = False

    await LoggingMiddleware(None)._persist_request(request, 0.0, Response(status_code=200))

    assert session.items[0].cost_usd == 0.04
    assert finalized == [("reservation", 11, 0.04)]


@pytest.mark.anyio
async def test_streaming_request_is_logged_after_body_finishes(monkeypatch):
    request = Request({
        "type": "http", "method": "POST", "path": "/v1/chat/completions",
        "headers": [], "state": {},
    })
    request.state.api_key = SimpleNamespace(id=3, team_id=11)
    persisted = []

    async def persist(_request, _start, _response):
        persisted.append(True)

    async def call_next(_request):
        async def body():
            yield b"data: chunk\n\n"
        return StreamingResponse(body(), media_type="text/event-stream")

    middleware = LoggingMiddleware(None)
    monkeypatch.setattr(middleware, "_persist_request", persist)

    response = await middleware.dispatch(request, call_next)
    assert persisted == []
    chunks = [chunk async for chunk in response.body_iterator]

    assert chunks == [b"data: chunk\n\n"]
    assert persisted == [True]
