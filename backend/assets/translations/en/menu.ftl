msg-main-menu =
    <b>👤 Profile</b>:
    <blockquote>• <b>ID</b>: <code>{ $user_id }</code>
    • <b>Name</b>: { $user_name }
    • <b>Discount</b>: { $user_discount }%</blockquote>

    { $subscription_block }
frg-menu-subscription =
    { $is_trial ->
        [1] <b>🎁 Trial subscription</b>:
       *[0] <b>💳 Subscription</b>:
    }
    { $status ->
        [ACTIVE]
            <blockquote>• <b>Traffic limit</b>: { $traffic_limit }
            • <b>Device limit</b>: { $device_limit }
            • <b>Expires</b>: { $expire_at }</blockquote>
        [EXPIRED]
            <blockquote>• Your subscription has expired.

            <i>{ $is_trial ->
                [0] Renew it to keep using the service!
               *[1] Your free trial has ended. Buy a subscription to keep using the service!
            }</i></blockquote>
        [LIMITED]
            <blockquote>• Your traffic is used up.

            <i>{ $is_trial ->
                [0] { $traffic_strategy ->
                    [NO_RESET] Renew your subscription to reset the traffic and keep using the service!
                   *[RESET] Traffic is restored at the start of the next period. You can also renew your subscription to reset it now.
                }
               *[1] { $traffic_strategy ->
                    [NO_RESET] Buy a subscription to keep using the service!
                   *[RESET] Traffic is restored at the start of the next period. You can also buy a subscription to use the service without limits.
                }
            }</i></blockquote>
       *[DISABLED]
            <blockquote>• Your subscription is disabled.

            <i>Contact support to find out why.</i></blockquote>
    }

    More subscriptions: { $extra_count } — see “My subscriptions”.
frg-menu-no-subscription =
    <blockquote>You have no subscription.

    <i>{ $trial_available ->
        [1] 🎁 A free trial is available to you — tap the button below to get it.
       *[0] ↘️ To get access, tap “Buy a subscription”.
    }</i></blockquote>
frg-subscription-status = { $status ->
        [ACTIVE] Active
        [LIMITED] Traffic limit reached
        [EXPIRED] Expired
        [DISABLED] Disabled
        [DELETED] Deleted
       *[other] { $status }
    }
frg-subscription-unlimited = Unlimited
frg-subscription-traffic-limit = { $traffic_limit } GB
msg-window-gone = This screen is no longer available.
msg-paysupport = To request a refund, contact support.
msg-menu-devices = Your devices ({ $devices_current }/{ $devices_max })
msg-menu-devices-confirm-delete = Delete this device?
msg-menu-devices-confirm-delete-all = Delete every device? Each one has to be connected again.
msg-menu-devices-confirm-reissue = Reissue the connection link? The old link will stop working.

btn-menu =
    .connect = Connect
    .connect-icon = 🚀
    .connect-not-available = Connection unavailable
    .connect-not-available-icon = ⚠️
    .trial = Try for free
    .trial-icon = 🎁
    .trial-paid = Trial — { $trial_price }
    .trial-paid-icon = 🚀
    .devices = Devices
    .devices-icon = 📱
    .support = Support
    .support-icon = 🆘
    .web-cabinet = Web cabinet
    .web-cabinet-icon = 🌐
    .subscription = Subscription
    .subscription-icon = 💳
    .subscriptions = My subscriptions
    .subscriptions-icon = 💳
    .purchase = Buy a subscription
    .purchase-icon = 💸
    .promocode = Promocode
    .promocode-icon = 🎟
    .referrals = Referrals
    .referrals-icon = 👥
    .legal = Documents

btn-legal =
    .OFFER = Public offer
    .USER_AGREEMENT = User agreement
    .PRIVACY_POLICY = Privacy policy

msg-legal-list = Legal documents. Pick one to read it.
msg-legal-empty = No documents have been published yet.
msg-legal-gate =
    <b>Before you start</b>
    To use the bot, read the documents below and accept them.
msg-legal-gate-update =
    <b>We’ve updated our documents</b>
    Review the new version and accept it to continue.

btn-legal-gate =
    .accept = ✅ I accept

btn-devices =
    .item = { $platform_icon } { $platform } ({ $device_model }) — { $created_at }
    .empty = No connected devices
    .delete-all = Delete all devices
    .delete-all-icon = 🗑
    .reissue = Reissue link
    .reissue-icon = 🔄
    .confirm-delete = Yes, delete
    .confirm-delete-icon = ✅
    .confirm-reissue = Yes, reissue
    .confirm-reissue-icon = ✅
    .cancel-reissue = Cancel
    .cancel-reissue-icon = ❌

msg-subscriptions-list = Your subscriptions. Pick one to see its details.
msg-subscription-card =
    Plan: { $plan_name }
    Status: { $status ->
        [ACTIVE] Active
        [LIMITED] Traffic limit reached
        [EXPIRED] Expired
        [DISABLED] Disabled
        [DELETED] Deleted
       *[other] { $status }
    }
    Expires: { $expire_at }
    Traffic: { $traffic_limit ->
        [0] Unlimited
       *[other] { $traffic_limit } GB
    }
    Devices: { $device_limit ->
        [0] Unlimited
       *[other] { $device_limit }
    }
msg-referrals =
    <b>👥 Invite friends</b>

    Share your unique link and get rewards!

    <b>📊 Statistics</b>:
    <blockquote>• <b>Invited by you</b>: { $referrals_level_1 }
    • <b>Invited by your friends</b>: { $referrals_level_2 }
    • <b>Points</b>: { $points }
    • <b>Bonus days</b>: { $bonus_days }</blockquote>

btn-subscriptions =
    .purchase = Buy a subscription
    .purchase-icon = 💸

btn-subscription =
    .renew = Renew
    .renew-icon = 🔄
    .change = Change plan
    .change-icon = 🔃

msg-referrals-about =
    <b>❓ How does it work?</b>

    <b>1️⃣ Share your link</b>
    <blockquote>Send it to a friend or show the QR code.</blockquote>

    <b>2️⃣ Your friend signs up with it</b>
    <blockquote>{ $invitee_reward_amount ->
        [0] And becomes your referral.
       *[other] And gets +{ $invitee_reward_amount } { $invitee_reward_type ->
            [POINTS] { $invitee_reward_amount ->
                [one] point
               *[other] points
            }
           *[EXTRA_DAYS] { $invitee_reward_amount ->
                [one] bonus day
               *[other] bonus days
            }
        } right away.
    }</blockquote>

    <b>3️⃣ Your friend pays for a subscription</b>
    <blockquote>You get { $reward_terms }. { $accrual_strategy ->
        [EVERY_PAYMENT] For each of their payments: a purchase, a renewal and a plan change.
       *[FIRST_PAYMENT] For their first payment only.
    }
    { $reward_levels }</blockquote>

    { $reward_type ->
        [POINTS] <b>4️⃣ Exchange your points</b>
        <blockquote>Tap “Withdraw points” and message support — an administrator will make the exchange.</blockquote>
       *[EXTRA_DAYS] <b>4️⃣ Apply your bonus days</b>
        <blockquote>Add them to any of your subscriptions.</blockquote>
    }

    <i>You can only invite someone who doesn't use the service yet. Trial subscriptions and ones from a promo code earn no reward. If a payment is refunded, its reward is cancelled.</i>
frg-referral-terms = { $reward_strategy ->
        [PERCENT] { $reward_type ->
            [POINTS] { $amount }% of a friend's payment as points
           *[EXTRA_DAYS] { $amount }% of the days your friend buys, as bonus days
        }
       *[AMOUNT] { $reward_type ->
            [POINTS] +{ $amount } { $amount ->
                [one] point
               *[other] points
            } for a friend's payment
           *[EXTRA_DAYS] +{ $amount } { $amount ->
                [one] day
               *[other] days
            } for a friend's payment
        }
    }
frg-referral-levels = Friends of your friends earn you a reward too:
frg-referral-level = Level { $level } — { $terms }
msg-referrals-redeem-target = Choose which subscription gets your { $bonus_days } bonus days:

btn-referrals =
    .about = How does it work?
    .about-icon = ❓
    .copy = Copy link
    .copy-icon = 📋
    .share = Share link
    .share-icon = 📩
    .withdraw = Withdraw points
    .withdraw-icon = 💎
    .redeem = Redeem bonus days
    .qr = QR code
    .qr-icon = 🧾
    .reset-code = New referral link
    .reset-code-icon = 🔄

btn-back =
    .general = Back
    .general-icon = ⬅️

ntf-subscription =
    .gone = This subscription is no longer available.

ntf-devices =
    .deleted = Device deleted.
    .all-deleted = All devices deleted.
    .reissued = Connection link reissued.
    .reset-disabled = This action is turned off right now.
    .failed = Something went wrong. Please try again later.

ntf-access =
    .restricted = The service is temporarily closed for maintenance. Please come back later.
    .registration-disabled = Sign-ups are closed right now.
    .invite-only = Sign-up is by invitation only. Ask a friend for their referral link.
    .payments-disabled = Payments are temporarily unavailable. We'll message you when they're back.

ntf-common =
    .lost-context = The menu was refreshed, carry on from here.
    .unknown-error = Something went wrong. Please try again.
    .cooldown-active = You can repeat this action after { $available_at }.
    .trial-unavailable = Trial is not available.
    .connect-not-available = Connection is not available.
    .access-restricted = Access is restricted.

ntf-purchase =
    .stars-rejected = This order can't be paid any more. Please start the purchase again.
    .payments-disabled = Payments are temporarily unavailable.
    .plan-unavailable = This plan is no longer available — please pick another one.
    .limit-reached = You've reached the subscription limit.
    .method-unavailable = This payment method is unavailable right now.
    .retry = Please try again.
    .failed = Couldn't create the payment. Please try again later.
    .no-plans = No plans are available.
    .no-methods = No payment methods are available.

msg-purchase-plan = Choose a plan:
msg-purchase-duration = { $plan_name }: choose a period:
msg-purchase-method = Choose a payment method:
msg-purchase-confirm =
    { $plan_name } · { $duration_days } d · { $price } { $currency_symbol } · { $method }
    { $terms_notice }
frg-purchase-terms-notice = By paying you accept the terms — /terms
msg-purchase-pay = Your order is ready. Tap the button below to pay.
msg-purchase-link-choice = You already have a { $plan_name } subscription. Renew it or buy another one?

btn-purchase =
    .duration = { $days } d — { $price } { $currency_symbol }
    .method = { $gateway } — { $price } { $currency_symbol }
    .pay = Pay
    .pay-icon = 💳
    .go-to-payment = Go to payment
    .go-to-payment-icon = 💳
    .menu = Main menu
    .menu-icon = ↩️
    .link-renew = Renew: { $subscription }
    .link-new = Buy a new one
    .link-new-icon = 💸

msg-payment-result-success =
    <b>✅ Payment successful!</b>

    { $purchase_type ->
    [RENEW] Subscription { $plan_name } renewed.
    [CHANGE] Plan changed to { $plan_name }.
    *[NEW] Subscription { $plan_name } activated.
    }
msg-payment-result-failed =
    <b>❌ Something went wrong!</b>

    Don't worry, support has already been notified and will contact you shortly. We apologize for the inconvenience.
msg-payment-result-canceled = <b>Payment canceled.</b> The order is no longer valid — you can place it again.

btn-payment-result =
    .subscription = My subscription
    .subscription-icon = 💳
    .retry = Try again
    .menu = Main menu
    .menu-icon = ↩️

gateway-name =
    .TELEGRAM_STARS = Telegram Stars
    .YOOKASSA = YooKassa
    .YOOMONEY = YooMoney
    .VALUTIX = Valutix
    .CRYPTOMUS = Cryptomus
    .HELEKET = Heleket
    .CRYPTOPAY = CryptoPay
    .FREEKASSA = FreeKassa
    .MULENPAY = MulenPay
    .PAYMASTER = PayMaster
    .PLATEGA = Platega
    .ROBOKASSA = RoboKassa
    .URLPAY = UrlPay
    .WATA = Wata
    .ROLLYPAY = RollyPay
    .ANTILOPAY = Antilopay
    .PAYPALYCH = Paypalych
    .RIOPAY = RioPay
    .AURAPAY = AuraPay
    .SEVERPAY = SeverPay
    .LAVA = Lava
    .CLOUDPAYMENTS = CloudPayments
    .PAYPEAR = PayPear

ntf-referrals =
    .no-subscription = You have no active subscription to add the days to.
    .days-redeemed = { $days } bonus days added to your subscription.
    .redeem-failed = Bonus days can't be added to this subscription.
    .code-reset = Your referral link has been replaced. The old one no longer works.
    .reset-disabled = Changing the referral link is turned off.

ntf-promocode =
    .not-found = Promocode not found.
    .expired = This promocode has expired.
    .already-activated = You've already activated this promocode.
    .discount-not-better = You already have an equal or bigger discount, so the promocode was not applied.
    .not-available = This promocode isn't available to you.
    .no-target-subscription = You have no active subscription to apply this promocode to.
    .activated = Promocode activated!
    .activation-failed = Failed to activate the promocode. Please try again later.
    .too-many-attempts = Too many attempts. Try again in a minute.

msg-promocode-input =
    <b>🎟 Promo code</b>

    Send your promo code as a message.
msg-promocode-target =
    <b>🎟 Promo code</b>

    Choose which subscription to apply the promo code to.
msg-promocode-confirm =
    <b>🎟 Promo code <code>{ $promo_code }</code></b>

    🎁 You'll get: { $promo_reward_type ->
        [DURATION] <b>+{ $promo_reward } { $promo_reward ->
            [one] day
           *[other] days
        }</b> on your subscription.
        [TRAFFIC] <b>+{ $promo_reward } GB</b> of traffic.
        [DEVICES] <b>+{ $promo_reward } { $promo_reward ->
            [one] device
           *[other] devices
        }</b> on your device limit.
        [SUBSCRIPTION] the <b>{ $promo_plan_name }</b> subscription for <b>{ $promo_reward } { $promo_reward ->
            [one] day
           *[other] days
        }</b>.
        [PERSONAL_DISCOUNT] a permanent <b>{ $promo_reward }% discount</b> on every purchase.
        [PURCHASE_DISCOUNT] a <b>{ $promo_reward }% discount</b> on your next purchase.
       *[other] a reward on your account.
    }

    { $promo_reward_type ->
        [TRAFFIC] ⚠️ <i>The bonus stays when you renew but is lost when you change plans.</i>
        [DEVICES] ⚠️ <i>The bonus stays when you renew but is lost when you change plans.</i>
       *[other] { "" }
    }

    Tap “Apply” to activate it.
msg-promocode-confirm-will-replace = ⚠️ <i>The promo code will replace your current subscription.</i>

btn-promocode =
    .confirm = Apply
    .confirm-icon = ✅
    .cancel = Cancel
    .cancel-icon = ❌

platform-icon =
    .ios = 📱
    .android = 🤖
    .windows = 🖥
    .macos = 💻
    .linux = 🐧
    .default = ❓

btn-broadcast =
    .unsubscribe = Unsubscribe from these emails
    .resubscribe = Get offers again

ntf-broadcast =
    .unsubscribed = You won't receive offers anymore. Service messages will still arrive.
    .resubscribed = You'll receive offers again.
    .promo-gone = This offer is no longer available.
    .start-required = Press /start to continue.

ntf-requirements =
    .channel = Subscribe to our channel to continue.
    .channel-not-found = We can't see your subscription yet. Subscribe and try again.
    .trial-paused = You left our channel, so your trial is paused. Subscribe again to continue.
    .trial-resumed = You're back in our channel, so your trial is running again.

btn-requirements =
    .subscribe = Subscribe
    .subscribe-icon = ❤️
    .check = I've subscribed
    .check-icon = ✅

ntf-cabinet-login =
    .link = Tap the button to sign in to the web cabinet. The link works once and expires in 5 minutes.
    .expired = This sign-in link has expired. Request a new one in the cabinet.

btn-cabinet-login =
    .open = Sign in to the cabinet

ntf-cabinet-link =
    .link = Tap the button to link this Telegram to your web cabinet account. The link is single-use and valid for 5 minutes.
    .expired = The linking link has expired. Request a new one in the cabinet.

btn-cabinet-link =
    .open = Link to cabinet
