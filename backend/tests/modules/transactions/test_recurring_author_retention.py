from copy import deepcopy

from sqlalchemy import delete

from app.core.db.models import RecurringConsent, User
from app.modules.account_merge.repository import AccountMergeRepository
from app.modules.users.dto import CreateUserDto
from tests.modules.transactions import test_recurring_payments as recurring_cases

case = recurring_cases.case


async def test_purging_merged_author_retains_current_owners_recurring_authorization(
    case, session, uow, user_repository, subscription_repository, transaction_repository
) -> None:
    original = await case.repository.get(case.subscription.id)
    consent = await session.get(RecurringConsent, original.consent_id)
    original_terms = deepcopy(consent.terms)
    original_telegram_id = consent.telegram_id
    original_accepted_at = consent.accepted_at

    async with uow:
        target = await user_repository.create(CreateUserDto(name="merged recurring owner"))
        await AccountMergeRepository(session).reassign(case.user.id, target.id, {})
        await session.execute(delete(User).where(User.id == case.user.id))

    await session.refresh(consent)
    assert await user_repository.find_by_id(case.user.id) is None
    assert consent.user_id is None
    assert consent.owner_user_id == target.id
    assert consent.terms == original_terms
    assert consent.terms["user_id"] == case.user.id
    assert consent.telegram_id == original_telegram_id
    assert consent.accepted_at == original_accepted_at
    assert consent.revoked_at is None
    assert (await case.repository.consent_terms(consent.id)).user_id == target.id

    mandate = await case.repository.get(case.subscription.id)
    assert mandate.enabled and mandate.consent_id == consent.id
    assert mandate.payment_method_id == original.payment_method_id
    assert (await subscription_repository.get_by_id(case.subscription.id)).user_id == target.id
    assert (await transaction_repository.get_by_id(case.source.id)).user_id == target.id

    await case.worker.system()
    assert len(case.provider.posts) == 1
    mandate = await case.repository.get(case.subscription.id)
    assert mandate.enabled and mandate.last_error is None
    order = await transaction_repository.get_by_id(mandate.pending_transaction_id)
    assert order.user_id == target.id
    assert order.recurring_consent_id == consent.id
