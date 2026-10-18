import pytest
from pydantic import ValidationError

from app.core.security import hash_api_key
import app.routes.admin as admin
from app.models.db import APIKey, Team
from app.routes.admin import APIKeyCreate


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
async def test_revoke_key_keeps_record_and_sets_revoked_timestamp(monkeypatch):
    key = APIKey(id=34, key_hash=hash_api_key("gw_example"), name="batch", revoked_at=None)
    session = FakeSession(None)
    session.result = key
    monkeypatch.setattr(admin, "AsyncSession", lambda _engine: session)

    response = await admin.revoke_api_key(34)

    assert response.status_code == 204
    assert key.revoked_at is not None
    assert session.commits == 1
