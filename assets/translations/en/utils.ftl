space = {" "}
empty = { "!empty!" }
btn-test = Button
msg-test = Message
development = In development!
test-payment = Test payment
unknown = —

development-promocode = Promocodes are not implemented yet, to motivate and speed up development you can drop a coin.

payment-invoice-description = { $purchase-type } subscription { $name } for { $duration }

inline-invite =
    .title = Invite a friend
    .description = Click to send an invitation link!
    .message =
        🚀 Hello! Want a stable and fast VPN?

        { $bot_name } - will help you with this!

        ↘️ CLICK THE BUTTON AND TRY FOR FREE!
    .start = 🚀 Join

message =
    .withdraw-points = Hello! I would like to request a points exchange.
    .paysupport = Hello! I would like to request a refund.
    .help = Hello! I need help.

command =
    .start = Restart bot
    .paysupport = Refund
    .rules = Terms of use
    .help = Help

hdr-user = <b>👤 User:</b>
hdr-user-profile = <b>👤 Profile:</b>
hdr-payment = <b>💰 Payment:</b>
hdr-error = <b>⚠️ Error:</b>
hdr-node = <b>🖥 Node:</b>
hdr-hwid = <b>📱 Device:</b>

hdr-subscription = { $is_trial ->
    [1] <b>🎁 Trial subscription:</b>
    *[0] <b>💳 Subscription:</b>
}

hdr-plan = { $is_trial_plan ->
    [1] <b>🎁 Trial plan:</b>
    *[0] <b>📦 Plan:</b>
}

frg-user =
    <blockquote>
    • <b>ID</b>: <code>{ NUMBER($telegram_id, useGrouping: 0) }</code>
    • <b>Name</b>: { $name }
    { $show_personal_discount ->
    [1] • <b>Personal discount</b>: { $personal_discount }%
    *[0] { empty }
    }
    { $show_purchase_discount ->
    [1] • <b>Purchase discount</b>: { $purchase_discount }%
    *[0] { empty }
    }
    </blockquote>

frg-user-info =
    <blockquote>
    • <b>ID</b>: <code>{ NUMBER($telegram_id, useGrouping: 0) }</code> 
    • <b>Name</b>: { $name } { $username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $telegram_id }">@{ $username }</a>)
    }
    </blockquote>

frg-user-details =
    <blockquote>
    • <b>ID</b>: <code>{ NUMBER($telegram_id, useGrouping: 0) }</code>
    • <b>Name</b>: { $name } { $username -> 
        [0] { space }
        *[HAS] (<a href="tg://user?id={ $telegram_id }">@{ $username }</a>)
    }
    • <b>Role</b>: { role }
    • <b>Language</b>: { language }
    • <b>Bot blocked</b>: { $is_bot_blocked ->
        [1] Yes
        *[0] No
    }
    { $show_points ->
    [1] • <b>Points</b>: { $points }
    *[0] { empty }
    }
    </blockquote>

frg-user-discounts-details =
    <blockquote>
    • <b>Personal</b>: { $personal_discount }%
    • <b>Next purchase</b>: { $purchase_discount }%
    </blockquote>

frg-subscription =
    <blockquote>
    • <b>Traffic limit</b>: { $traffic_limit }
    • <b>Device limit</b>: { $device_limit }
    • <b>Expires in</b>: { $expire_time }
    </blockquote>

frg-subscription-details =
    <blockquote>
    • <b>ID</b>: <code>{ $subscription_id }</code>
    • <b>Status</b>: { subscription-status }
    • <b>Traffic</b>: { $traffic_used } / { $traffic_limit }
    • <b>Device limit</b>: { $device_limit }
    • <b>Expires in</b>: { $expire_time }
    </blockquote>

frg-payment-info =
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Payment method</b>: { gateway-type }
    • <b>Amount</b>: { frg-payment-amount }
    </blockquote>

frg-payment-amount = { $final_amount }{ $currency } { $discount_percent -> 
    [0] { space }
    *[more] { space } <strike>{ $original_amount }{ $currency }</strike> (-{ $discount_percent }%)
    }

frg-plan-snapshot =
    <blockquote>
    • <b>Plan</b>: <code>{ $plan_name }</code>
    • <b>Type</b>: { plan-type } 
    • <b>Traffic limit</b>: { $plan_traffic_limit }
    • <b>Device limit</b>: { $plan_device_limit }
    • <b>Duration</b>: { $plan_duration }
    </blockquote>

frg-plan-snapshot-comparison =
    <blockquote>
    • <b>Plan</b>: <code>{ $previous_plan_name }</code> -> <code>{ $plan_name }</code>
    • <b>Type</b>: { $previous_plan_type } -> { plan-type }
    • <b>Traffic limit</b>: { $previous_plan_traffic_limit } -> { $plan_traffic_limit }
    • <b>Device limit</b>: { $previous_plan_device_limit } -> { $plan_device_limit }
    • <b>Duration</b>: { $previous_plan_duration } -> { $plan_duration }
    </blockquote>

frg-node-info =
    <blockquote>
    • <b>Name</b>: { $country } { $name }
    • <b>Address</b>: <code>{ $address }{ $port ->
        [0] { space }
        *[HAS] :{ $port }</code>
    }
    • <b>Traffic</b>: { $traffic_used } / { $traffic_limit }
    { $last_status_message -> 
    [0] { empty }
    *[HAS] • <b>Last status</b>: { $last_status_message }
    }
    { $last_status_change -> 
    [0] { empty }
    *[HAS] • <b>Status changed</b>: { $last_status_change }
    }
    </blockquote>

frg-user-hwid =
    <blockquote>
    • <b>HWID</b>: <code>{ $hwid }</code>
    { $platform ->
    [0] { space }
    *[HAS] • <b>Platform</b>: { $platform }
    }
    { $device_model ->
    [0] { space }
    *[HAS] • <b>Model</b>: { $device_model }
    }
    { $os_version ->
    [0] { space }
    *[HAS] • <b>Version</b>: { $os_version }
    }
    { $user_agent ->
    [0] { space }
    *[HAS] • <b>Agent</b>: { $user_agent }
    }
    </blockquote>

frg-build-info =
    { $has_build ->
    [0] { space }
    *[HAS]
    <b>🏗️ Build info:</b>
    <blockquote>
    Build time: { $time }
    Branch: { $branch } ({ $tag })
    Commit: <a href="{ $commit_url }">{ $commit }</a>
    </blockquote>
    }

role-owner = Owner
role-dev = Developer
role-admin = Admin
role-preview = Preview
role-user = User
role = 
    { $role ->
    [5] { role-owner }
    [4] { role-dev }
    [3] { role-admin }
    [2] { role-preview }
    *[1] { role-user }
}

unlimited = ∞

unit-unlimited = { $value ->
    [0] { unlimited }
    *[other] { $value }
}

unit-device = { $value -> 
    [0] { unlimited }
    *[other] { $value } 
} { $value ->
    [0] { space }
    [one] device
    [few] devices
    *[other] devices
}

unit-byte = { $value } B
unit-kilobyte = { $value } KB
unit-megabyte = { $value } MB
unit-gigabyte = { $value } GB
unit-terabyte = { $value } TB

unit-second = { $value } { $value ->
    [one] second
    [few] seconds
    *[other] seconds
}

unit-minute = { $value } { $value ->
    [one] minute
    [few] minutes
    *[other] minutes
}

unit-hour = { $value } { $value ->
    [one] hour
    [few] hours
    *[other] hours
}

unit-day = { $value } { $value ->
    [one] day
    [few] days
    *[other] days
}

unit-month = { $value } { $value ->
    [one] month
    [few] months
    *[other] months
}

unit-year = { $value } { $value ->
    [one] year
    [few] years
    *[other] years
}


plan-type = { $plan_type -> 
    [TRAFFIC] Traffic
    [DEVICES] Devices
    [BOTH] Traffic + Devices
    [UNLIMITED] Unlimited
    *[OTHER] { $plan_type }
}

promocode-type = { $promocode_type -> 
    [DURATION] Duration
    [TRAFFIC] Traffic
    [DEVICES] Devices
    [SUBSCRIPTION] Subscription
    [PERSONAL_DISCOUNT] Personal Discount
    [PURCHASE_DISCOUNT] Purchase Discount
    *[OTHER] { $promocode_type }
}

availability-type = { $availability_type -> 
    [ALL] For everyone
    [NEW] For new users
    [EXISTING] For existing
    [INVITED] For invited
    [ALLOWED] For allowed
    [LINK] By link
    *[OTHER] { $availability_type }
}

gateway-type = { $gateway_type ->
    [TELEGRAM_STARS] Telegram Stars
    [YOOKASSA] YooKassa
    [YOOMONEY] YooMoney
    [CRYPTOMUS] Cryptomus
    [HELEKET] Heleket
    [CRYPTOPAY] CryptoPay
    [FREEKASSA] FreeKassa
    [MULENPAY] MulenPay
    [PAYMASTER] PayMaster
    [PLATEGA] Platega
    [ROBOKASSA] RoboKassa
    [URLPAY] UrlPay
    [WATA] WATA
    [MANUAL_TRANSFER] Bank Transfer
    *[OTHER] { $gateway_type }
}

access-mode = { $access_mode ->
    [PUBLIC] 🟢 Allowed for all
    [INVITED] 🟡 Allowed for invited
    [RESTRICTED] 🔴 Restricted for all
    *[OTHER] { $access_mode }
}

audience-type = { $audience_type ->
    [ALL] Everyone
    [PLAN] By plan
    [SUBSCRIBED] With subscription
    [UNSUBSCRIBED] Without subscription
    [EXPIRED] Expired
    [TRIAL] With trial
    *[OTHER] { $audience_type }
}

broadcast-status = { $broadcast_status ->
    [PROCESSING] In progress
    [COMPLETED] Completed
    [CANCELED] Canceled
    [DELETED] Deleted
    [ERROR] Error
    *[OTHER] { $broadcast_status }
}

transaction-status = { $transaction_status ->
    [PENDING] Pending
    [COMPLETED] Completed
    [CANCELED] Canceled
    [REFUNDED] Refunded
    [FAILED] Failed
    *[OTHER] { $transaction_status }
}

subscription-status = { $subscription_status ->
    [ACTIVE] Active
    [DISABLED] Disabled
    [LIMITED] Traffic exhausted
    [EXPIRED] Expired
    [DELETED] Deleted
    *[OTHER] { $subscription_status }
}

purchase-type = { $purchase_type ->
    [NEW] Purchase
    [RENEW] Renewal
    [CHANGE] Change
    *[OTHER] { $purchase_type }
}

traffic-strategy = { $strategy_type -> 
    [NO_RESET] Upon payment
    [DAY] Every day
    [WEEK] Every week
    [MONTH] Every month
    [MONTH_ROLLING] Every month (by creation date)
    *[OTHER] { $strategy_type }
    }

reward-type = { $reward_type -> 
    [POINTS] Points
    [EXTRA_DAYS] Days
    *[OTHER] { $reward_type }
    }

accrual-strategy = { $accrual_strategy_type -> 
    [ON_FIRST_PAYMENT] First payment
    [ON_EACH_PAYMENT] Each payment
    *[OTHER] { $accrual_strategy_type }
    }

reward-strategy = { $reward_strategy_type -> 
    [AMOUNT] Fixed
    [PERCENT] Percentage
    *[OTHER] { $reward_strategy_type }
    }

button-type = { $button_type ->
    [URL] Open link
    [COPY] Copy text
    [WEB_APP] Open web app
    *[OTHER] { $button_type }
}

language = { $language ->
    [ar] Arabic
    [az] Azerbaijani
    [be] Belarusian
    [cs] Czech
    [de] German
    [en] English
    [es] Spanish
    [fa] Persian
    [fr] French
    [he] Hebrew
    [hi] Hindi
    [id] Indonesian
    [it] Italian
    [ja] Japanese
    [kk] Kazakh
    [ko] Korean
    [ms] Malay
    [nl] Dutch
    [pl] Polish
    [pt] Portuguese
    [ro] Romanian
    [ru] Russian
    [sr] Serbian
    [tr] Turkish
    [uk] Ukrainian
    [uz] Uzbek
    [vi] Vietnamese
    *[OTHER] { $language }
}