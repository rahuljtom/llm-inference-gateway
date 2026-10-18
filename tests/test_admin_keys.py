from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.security import hash_api_key
import app.routes.admin as admin
from app.models.db import APIKey, Team
from app.routes.admin import APIKeyCreate, TeamBudgetUpdate


def test_api_key_payload_trims_name_and_team():
    payload = APIKeyCreate(name="  reporting job ", team="  Analytics ")

    assert payload.name == "reporting job"
    assert payload.team == "Analytics"
    assert payload.rpm_limit == 60
    assert payload.tpm_limit == 100000


@pytest.mark.parametrize("field", ["name", "team"])
def test_api_key_payload_rejects_blank_names(field):
    values = {"name": "Client", "team": "Analytics"}
    values[field] = "  "

    with pytest.raises(ValidationError):
        APIKeyCreate(**values)


def test_gateway_key_hash_does_not_contain_raw_secret():
    secret = "gw_private-test-key"

    digest = hash_api_key(secret)

    assert digest != secret
    assert len(digest) == 64
    assert secret not in digest


def test_team_budget_payload_accepts_disable_and_validates_precision():
    assert TeamBudgetUpdate(budget_monthly_usd=None).budget_monthly_usd is None
    assert TeamBudgetUpdate(budget_monthly_usd="12.345678").budget_monthly_usd == Decimal("12.345678")
    for value in ("-1", "1000000", "1.0000001"):
        with pytest.raises(ValidationError):
            TeamBudgetUpdate(budget_monthly_usd=value)


class FakeResult:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def all(self):
        return self.value


class FakeSession:
    def __init__(self, _engine):
        self.items = []
        self.result = None
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def exec(self, _query):
        return FakeResult(self.result)

    def add(self, item):
        self.items.append(item)

    async def flush(self):
        for item in self.items:
            if isinstance(item, Team):
                item.id = 12
            elif isinstance(item, APIKey):
                item.id = 34

    async def commit(self):
        self.commits += 1
        for item in self.items:
            if getattr(item, "expire_name_on_commit", False):
                item.expired = True

    async def refresh(self, _item):
        return None


@pytest.mark.anyio
async def test_create_key_returns_secret_once_and_persists_only_hash(monkeypatch):
    session = FakeSession(None)
    monkeypatch.setattr(admin, "AsyncSession", lambda _engine: session)

    result = await admin.create_api_key(APIKeyCreate(name="batch job", team="Analytics"))

    key = next(item for item in session.items if isinstance(item, APIKey))
    team = next(item for item in session.items if isinstance(item, Team))
    assert result["key"].startswith("gw_")
    assert key.key_hash == hash_api_key(result["key"])
    assert result["key"] != key.key_hash
    assert key.team_id == team.id == 12
    assert result["team"] == "analytics"


@pytest.mark.anyio
async def test_create_key_captures_team_name_before_commit_expiration(monkeypatch):
    class ExpiringTeam:
        expire_name_on_commit = True

        def __init__(self, name):
            self._name = name
            self.id = 12
            self.expired = False

        @property
        def name(self):
            if self.expired:
                raise RuntimeError("team name expired after commit")
            return self._name

    session = FakeSession(None)
    monkeypatch.setattr(admin, "Team", ExpiringTeam)
    monkeypatch.setattr(admin, "AsyncSession", lambda _engine: session)
    monkeypatch.setattr(admin, "select", lambda *_args: FakeQuery())

    result = await admin.create_api_key(APIKeyCreate(name="batch job", team="Analytics"))

    assert result["team"] == "analytics"


class FakeQuery:
    def where(self, *_args):
        return self


@pytest.mark.anyio
async def test_revoke_key_keeps_record_and_sets_revoked_timestamp(monkeypatch):
    key = APIKey(id=34, key_hash=hash_api_key("gw_example"), name="batch", revoked_at=None)
    session = FakeSession(None)
    session.result = key
    monkeypatch.setattr(admin, "AsyncSession", lambda _engine: session)

    response = await admin.revoke_api_key(34)

    assert response.status_code == 204
    assert key.revoked_at is not None
    assert session.commits == 1


@pytest.mark.anyio
async def test_team_budget_update_stores_limit_under_team_lock(monkeypatch):
    team = Team(id=12, name="analytics")
    session = FakeSession(None)
    session.result = team
    monkeypatch.setattr(admin, "AsyncSession", lambda _engine: session)

    result = await admin.set_team_budget(
        "Analytics", TeamBudgetUpdate(budget_monthly_usd="25.00")
    )

    assert team.budget_monthly_usd == Decimal("25.00")
    assert result["team"] == "analytics"
    assert result["monthlyBudgetUsd"] == "25.00"
    assert session.commits == 1
