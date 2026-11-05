from typing import Sequence, Union

from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ReferralReward.referral_id: add ondelete CASCADE + index
    op.drop_constraint(
        "referral_rewards_referral_id_fkey",
        "referral_rewards",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "referral_rewards_referral_id_fkey",
        "referral_rewards",
        "referrals",
        ["referral_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_referral_rewards_referral_id",
        "referral_rewards",
        ["referral_id"],
    )

    # PlanDuration.plan_id: add index
    op.create_index(
        "ix_plan_durations_plan_id",
        "plan_durations",
        ["plan_id"],
    )

    # PlanPrice.plan_duration_id: add index
    op.create_index(
        "ix_plan_prices_plan_duration_id",
        "plan_prices",
        ["plan_duration_id"],
    )

    # User.current_subscription_id: add index
    op.create_index(
        "ix_users_current_subscription_id",
        "users",
        ["current_subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_users_current_subscription_id", table_name="users")
    op.drop_index("ix_plan_prices_plan_duration_id", table_name="plan_prices")
    op.drop_index("ix_plan_durations_plan_id", table_name="plan_durations")
    op.drop_index("ix_referral_rewards_referral_id", table_name="referral_rewards")

    op.drop_constraint(
        "referral_rewards_referral_id_fkey",
        "referral_rewards",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "referral_rewards_referral_id_fkey",
        "referral_rewards",
        "referrals",
        ["referral_id"],
        ["id"],
    )
