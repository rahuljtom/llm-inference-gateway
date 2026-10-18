"""Atomic team monthly budget reservations based on the gateway's cost estimates."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from secrets import token_urlsafe
from typing import Iterable, Optional

from sqlalchemy import delete, func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.pricing import estimate_cost_usd
from app.db.session import engine
from app.models.chat import GatewayChatRequest
from app.models.db import BudgetReservation, Team, TeamBudgetUsage

DEFAULT_BUDGET_COMPLETION_LIMIT = 1024
RESERVATION_TTL = timedelta(minutes=15)


class BudgetExceeded(Exception):
    def __init__(self, *, limit: Decimal, spent: Decimal, reserved: Decimal, requested: Decimal):
        self.limit = limit
        self.spent = spent
        self.reserved = reserved
        self.requested = requested


def current_period_start(now: Optional[datetime] = None) -> date:
    now = now or datetime.now(timezone.utc)
    return date(now.year, now.month, 1)


def _prompt_token_upper_bound(gateway_request: GatewayChatRequest) -> int:
    # UTF-8 bytes plus per-message framing is a conservative estimate for ordinary tokenizers.
    return sum(len(message.content.encode("utf-8")) + 16 for message in gateway_request.messages)


def estimate_reservation_usd(
    gateway_request: GatewayChatRequest,
    fallback_models: Iterable[str] = (),
) -> Decimal:
    if gateway_request.max_tokens is None:
        gateway_request.max_tokens = DEFAULT_BUDGET_COMPLETION_LIMIT
    prompt_tokens = _prompt_token_upper_bound(gateway_request)
    possible_models = [gateway_request.model, *fallback_models]
    amount = max(
        estimate_cost_usd(model, prompt_tokens, gateway_request.max_tokens)
        for model in possible_models
    )
    return Decimal(f"{amount:.8f}")


async def reserve_team_budget(
    *,
    api_key_id: int,
    team_id: Optional[int],
    gateway_request: GatewayChatRequest,
    fallback_models: Iterable[str] = (),
) -> tuple[Optional[str], Optional[Decimal]]:
    """Reserve estimated worst-case request cost under a locked team row."""
    if team_id is None:
        return None, None
    request_id = token_urlsafe(24)
    now = datetime.now(timezone.utc)
    period_start = current_period_start(now)
    expires_before = now - RESERVATION_TTL
    async with AsyncSession(engine) as session:
        async with session.begin():
            team_result = await session.exec(
                select(Team).where(Team.id == team_id).with_for_update()
            )
            team = team_result.first()
            if team is None or team.budget_monthly_usd is None:
                return None, None

            # A crashed request must not hold budget forever. Normal requests are finalized
            # with their usage and reservation removed in one transaction by the logger.
            await session.exec(
                delete(BudgetReservation).where(
                    BudgetReservation.team_id == team_id,
                    BudgetReservation.created_at < expires_before,
                )
            )
            usage_result = await session.exec(
                select(TeamBudgetUsage).where(
                    TeamBudgetUsage.team_id == team_id,
                    TeamBudgetUsage.period_start == period_start,
                )
            )
            usage = usage_result.first()
            if usage is None:
                usage = TeamBudgetUsage(
                    team_id=team_id,
                    period_start=period_start,
                    spent_usd=Decimal("0"),
                )
                session.add(usage)
                await session.flush()

            reservation_result = await session.exec(
                select(func.coalesce(func.sum(BudgetReservation.reserved_usd), 0)).where(
                    BudgetReservation.team_id == team_id,
                    BudgetReservation.period_start == period_start,
                    BudgetReservation.created_at >= expires_before,
                )
            )
            reserved = Decimal(str(reservation_result.first() or 0))
            spent = Decimal(str(usage.spent_usd or 0))
            limit = Decimal(str(team.budget_monthly_usd))
            requested = estimate_reservation_usd(gateway_request, fallback_models)
            if spent + reserved + requested > limit:
                raise BudgetExceeded(
                    limit=limit, spent=spent, reserved=reserved, requested=requested
                )

            session.add(BudgetReservation(
                request_id=request_id,
                api_key_id=api_key_id,
                team_id=team_id,
                period_start=period_start,
                reserved_usd=requested,
                created_at=now,
            ))
    return request_id, requested


async def finalize_budget_reservation(
    session: AsyncSession,
    request_id: Optional[str],
    team_id: Optional[int],
    actual_cost_usd: float,
) -> None:
    """Commit estimated actual usage and release the reservation atomically."""
    if not request_id:
        return
    if team_id is None:
        return
    team_result = await session.exec(
        select(Team).where(Team.id == team_id).with_for_update()
    )
    if team_result.first() is None:
        return
    reservation_result = await session.exec(
        select(BudgetReservation)
        .where(BudgetReservation.request_id == request_id)
        .with_for_update()
    )
    reservation = reservation_result.first()
    if reservation is None:
        return
    usage_result = await session.exec(
        select(TeamBudgetUsage)
        .where(
            TeamBudgetUsage.team_id == reservation.team_id,
            TeamBudgetUsage.period_start == reservation.period_start,
        )
        .with_for_update()
    )
    usage = usage_result.first()
    if usage is not None:
        actual = Decimal(f"{max(0.0, actual_cost_usd):.8f}")
        usage.spent_usd = Decimal(str(usage.spent_usd or 0)) + actual
    await session.delete(reservation)
