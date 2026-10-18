from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from starlette.requests import Request

import app.core.budgets as budgets
import app.services.inference as inference
from app.models.chat import ChatMessage, GatewayChatRequest
from app.models.db import BudgetReservation, Team, TeamBudgetUsage


def request(model="gpt-4o", max_tokens=None):
    return GatewayChatRequest(
        provider="openai",
        api_key=SecretStr("provider-key"),
        model=model,
        messages=[ChatMessage(role="user", content="Hi")],
        max_tokens=max_tokens,
    )


def test_estimated_reservation_caps_unspecified_completion_size():
    gateway_request = request()

    amount = budgets.estimate_reservation_usd(gateway_request)

    assert gateway_request.max_tokens == budgets.DEFAULT_BUDGET_COMPLETION_LIMIT
    assert amount == Decimal("0.01028500")


class FakeResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class FakeSession:
    def __init__(self, _engine, *, spent=Decimal("0"), reserved=Decimal("0")):
        self.responses = [
            FakeResult(Team(id=11, name="analytics", budget_monthly_usd=Decimal("1.00"))),
            FakeResult(None),
            FakeResult(TeamBudgetUsage(
                team_id=11, period_start=date(2026, 10, 1), spent_usd=spent
            )),
            FakeResult(reserved),
        ]
        self.items = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def begin(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def exec(self, _query):
        return self.responses.pop(0)

    def add(self, item):
        self.items.append(item)

    async def flush(self):
        return None

    async def delete(self, item):
        self.items.append(("deleted", item))


@pytest.mark.anyio
async def test_reservation_tracks_team_and_uses_upper_bound(monkeypatch):
    session = FakeSession(None)
    monkeypatch.setattr(budgets, "AsyncSession", lambda _engine: session)

    request_id, amount = await budgets.reserve_team_budget(
        api_key_id=3, team_id=11, gateway_request=request()
    )

    reservations = [item for item in session.items if isinstance(item, BudgetReservation)]
    assert request_id is not None
    assert amount == Decimal("0.01028500")
    assert len(reservations) == 1
    assert reservations[0].request_id == request_id
    assert reservations[0].api_key_id == 3
    assert reservations[0].team_id == 11


@pytest.mark.anyio
async def test_reservation_rejects_request_that_would_exceed_month_budget(monkeypatch):
    session = FakeSession(None, spent=Decimal("0.99"))
    monkeypatch.setattr(budgets, "AsyncSession", lambda _engine: session)

    with pytest.raises(budgets.BudgetExceeded):
        await budgets.reserve_team_budget(
            api_key_id=3, team_id=11, gateway_request=request()
        )

    assert not any(isinstance(item, BudgetReservation) for item in session.items)


@pytest.mark.anyio
async def test_finalize_moves_actual_estimate_to_month_usage_and_releases_hold():
    reservation = BudgetReservation(
        request_id="request-id", team_id=11, period_start=date(2026, 10, 1),
        reserved_usd=Decimal("0.05"),
    )
    usage = TeamBudgetUsage(
        team_id=11, period_start=date(2026, 10, 1), spent_usd=Decimal("0.10")
    )

    class Session(FakeSession):
        def __init__(self):
            self.responses = [
                FakeResult(Team(id=11, name="analytics")),
                FakeResult(reservation),
                FakeResult(usage),
            ]
            self.items = []

    session = Session()

    await budgets.finalize_budget_reservation(session, "request-id", 11, 0.02)

    assert usage.spent_usd == Decimal("0.12")
    assert session.items == [("deleted", reservation)]


@pytest.mark.anyio
async def test_over_budget_request_returns_retryable_429(monkeypatch):
    async def reject(**_kwargs):
        raise budgets.BudgetExceeded(
            limit=Decimal("1.00"), spent=Decimal("0.99"),
            reserved=Decimal("0"), requested=Decimal("0.02"),
        )

    monkeypatch.setattr(inference, "reserve_team_budget", reject)
    request_scope = {"type": "http", "headers": [], "state": {}}
    gateway_request = request()
    request_context = Request(request_scope)
    request_context.state.api_key = SimpleNamespace(id=3, team_id=11)

    with pytest.raises(HTTPException) as error:
        await inference._reserve_budget(request_context, gateway_request, None)

    assert error.value.status_code == 429
    assert error.value.detail["code"] == "monthly_budget_exceeded"
    assert int(error.value.headers["Retry-After"]) > 0
