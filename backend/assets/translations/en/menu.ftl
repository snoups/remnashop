msg-main-menu =
    <b>👤 Profile</b>:
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Name</b>: { $user_name }
    • <b>Discount</b>: { $user_discount }%
    </blockquote>

    { $subscription_block }
frg-menu-subscription =
    { $is_trial ->
        [1] <b>🎁 Trial subscription</b>:
       *[0] <b>💳 Subscription</b>:
    }
    { $status ->
        [ACTIVE]
            <blockquote>
            • <b>Traffic limit</b>: { $traffic_limit }
            • <b>Device limit</b>: { $device_limit }
            • <b>Expires</b>: { $expire_at }
            </blockquote>
        [EXPIRED]
            <blockquote>
            • Your subscription has expired.

            <i>{ $is_trial ->
                [0] Renew it to keep using the service!
               *[1] Your free trial has ended. Buy a subscription to keep using the service!
            }</i>
            </blockquote>
        [LIMITED]
            <blockquote>
            • Your traffic is used up.

            <i>{ $is_trial ->
                [0] { $traffic_strategy ->
                    [NO_RESET] Renew your subscription to reset the traffic and keep using the service!
                   *[RESET] Traffic is restored at the start of the next period. You can also renew your subscription to reset it now.
                }
               *[1] { $traffic_strategy ->
                    [NO_RESET] Buy a subscription to keep using the service!
                   *[RESET] Traffic is restored at the start of the next period. You can also buy a subscription to use the service without limits.
                }
            }</i>
            </blockquote>
       *[DISABLED]
            <blockquote>
            • Your subscription is disabled.

            <i>Contact support to find out why.</i>
            </blockquote>
    }

    More subscriptions: { $extra_count } — see “My subscriptions”.
frg-menu-no-subscription =
    <blockquote>
    You have no subscription.

    <i>{ $trial_available ->
        [1] 🎁 A free trial is available to you — tap the button below to get it.
       *[0] { $trial_paid ->
            [1] 🚀 Try the service for { $trial_price } — tap the button below.
           *[0] ↘️ To get access, tap “Buy a subscription”.
        }
    }</i>
    </blockquote>
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
msg-menu-devices-confirm-delete-all = Delete every device? The connection link changes and every device loses access — each one has to be connected again with the new link.
msg-menu-devices-confirm-reissue = Reissue the connection link? The old link will stop working.

btn-menu =
    .connect = Connect
    .connect-icon = 🚀
    .connect-not-available = { $subscription_problem ->
        [LIMITED] TRAFFIC LIMIT REACHED
        [EXPIRED] SUBSCRIPTION EXPIRED
       *[other] YOUR SUBSCRIPTION IS NOT WORKING
    }
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
    .legal-icon = 📄

btn-legal =
    .OFFER = Public offer
    .USER_AGREEMENT = User agreement
    .PRIVACY_POLICY = Privacy policy

msg-legal-list = Legal documents. Pick one to read it.
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

msg-subscriptions-list =
    <b>💳 My subscriptions</b>

    <blockquote>
    Pick a subscription to connect, renew it or change its plan.
    </blockquote>
msg-subscription-card =
    { $is_trial ->
        [1] <b>🎁 Trial subscription · { $plan_name }</b>
       *[0] <b>💳 Subscription · { $plan_name }</b>
    }
    <blockquote>
    • <b>Status</b>: { $status ->
        [ACTIVE] 🟢 Active
        [LIMITED] 🟡 Traffic limit reached
        [EXPIRED] 🔴 Expired
        [DISABLED] ⚫ Disabled
        [DELETED] Deleted
       *[other] { $status }
    }
    • <b>Traffic limit</b>: { $traffic_limit ->
        [0] Unlimited
       *[other] { $traffic_limit } GB
    }
    • <b>Device limit</b>: { $device_limit ->
        [0] Unlimited
       *[other] { $device_limit }
    }
    • <b>Valid until</b>: { $expire_at }
    </blockquote>
msg-referrals =
    <b>👥 Invite friends</b>

    Share your unique link and get rewards!

    <b>📊 Statistics</b>:
    <blockquote>
    • <b>Invited by you</b>: { $referrals_level_1 }
    • <b>Invited by your friends</b>: { $referrals_level_2 }
    • <b>Points</b>: { $points }
    • <b>Bonus days</b>: { $bonus_days }
    </blockquote>

btn-subscriptions =
    .purchase = Buy a subscription
    .purchase-icon = 💸
    .item = { $status ->
        [ACTIVE] 🟢 { $plan_name } · until { $expire_at }
        [LIMITED] 🟡 { $plan_name } · traffic used up
        [EXPIRED] 🔴 { $plan_name } · expired { $expire_at }
        [DISABLED] ⚫ { $plan_name } · disabled
       *[other] { $plan_name } · { $expire_at }
    }

btn-subscription =
    .renew = Renew
    .renew-icon = 🔄
    .change = Change plan
    .change-icon = 🔃

msg-referrals-about =
    <b>❓ How does it work?</b>

    <b>1️⃣ Share your link</b>
    <blockquote>
    Send it to a friend or show the QR code.
    </blockquote>

    <b>2️⃣ Your friend signs up with it</b>
    <blockquote>
    { $invitee_reward_amount ->
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
    }
    </blockquote>

    <b>3️⃣ Your friend pays for a subscription</b>
    <blockquote>
    You get { $reward_terms }. { $accrual_strategy ->
        [EVERY_PAYMENT] For each of their payments: a purchase, a renewal and a plan change.
       *[FIRST_PAYMENT] For their first payment only.
    }
    { $reward_levels }
    </blockquote>

    { $reward_type ->
        [POINTS] <b>4️⃣ Exchange your points</b>
        <blockquote>
        Tap “Withdraw points” and message support — an administrator will make the exchange.
        </blockquote>
       *[EXTRA_DAYS] <b>4️⃣ Apply your bonus days</b>
        <blockquote>
        Add them to any of your subscriptions.
        </blockquote>
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
    .redeem-icon = 🎁
    .qr = QR code
    .qr-icon = 🧾
    .reset-code = New referral link
    .reset-code-icon = 🔄

btn-back =
    .general = Back
    .general-icon = ⬅️

ntf-subscription =
    .gone = ❌ This subscription is no longer available.

ntf-devices =
    .deleted = ✅ Device deleted.
    .all-deleted = ✅ All devices deleted.
    .reissued = ✅ Connection link reissued.
    .failed = ❌ Something went wrong. Please try again later.
    .delete-cooldown = ⏳ You can delete a device again in { $wait }.
    .delete-all-cooldown = ⏳ You can delete all devices again in { $wait }.
    .reissue-cooldown = ⏳ You can reissue the connection link again in { $wait }.

ntf-access =
    .restricted = 🚧 Maintenance in progress. Please try again later.
    .registration-disabled = ❌ The service isn't available to new users.
    .invite-only = ❌ The service is available by invitation only.
    .payments-disabled = 🚧 Payments are temporarily unavailable! You'll be notified once they're back.

ntf-common =
    .unknown-error = ❌ Something went wrong. Please try again.
    .trial-unavailable = ⚠️ Trial is not available.
    .trial-activated = ✅ Trial subscription activated.
    .connect-not-available = ⚠️ { $status ->
        [LIMITED] You've used up all your traffic. { $is_trial ->
            [1] { $reset_in ->
                [none] Get a subscription to keep using the service!
               *[other] It will be restored in { $reset_in }. You can also get a subscription to use the service without limits.
            }
           *[0] { $reset_in ->
                [none] Renew your subscription to reset the traffic and keep using the service!
               *[other] It will be restored in { $reset_in }. You can also renew your subscription to reset it now.
            }
        }
        [EXPIRED] { $is_trial ->
            [1] Your free trial has ended. Get a subscription to keep using the service.
           *[0] Your subscription has expired. Renew it or get a new one.
        }
       *[other] We couldn't check your subscription or it has been disabled. Please contact support.
    }
    .access-restricted = ❌ Access is restricted.

ntf-purchase =
    .stars-rejected = This order can't be paid any more. Please start the purchase again.
    .plan-unavailable = ❌ This plan is no longer available — please pick another one.
    .renew-plan-unavailable = ❌ Your current plan is outdated and can't be renewed.
    .limit-reached = ❌ You've reached the subscription limit.
    .method-unavailable = ❌ This payment method is unavailable right now.
    .discount-used = ⚠️ The discount has already been used — check the new price.
    .failed = ❌ Couldn't create the payment. Please try again later.
    .no-plans = ❌ No plans are available.
    .no-methods = ❌ No payment methods are available.
    .invalid-email = ❌ That doesn't look like an email address. Check it and send it again.

msg-purchase-plan = <b>💳 Choose a plan</b>
msg-purchase-duration =
    <b>⏳ Choose a duration</b>

    { $plan_details }

    { $discount_notice }

    { $plan_changed_notice }
msg-purchase-email =
    <b>📧 Enter your email</b>

    Send your email address as a message — the payment receipt will be sent there.
msg-purchase-method =
    <b>💳 Choose a payment method</b>

    { $plan_details }

    { $discount_notice }
frg-purchase-plan =
    <b>{ $plan_name }</b>:
    <blockquote>
    { $description }
    • <b>Traffic limit</b>: { $traffic_limit ->
        [0] Unlimited
       *[other] { $traffic_limit } GB
    }
    • <b>Device limit</b>: { $device_limit ->
        [0] Unlimited
       *[other] { $device_limit }
    }
    • <b>Duration</b>: { $period }
    </blockquote>
frg-purchase-discount = <i>Prices include your { $percent }% discount</i>
frg-purchase-plan-changed = <i>ℹ️ The plan's terms have changed since your purchase. After renewal your subscription moves to the new terms shown above.</i>
frg-purchase-type-notice = { $purchase_type ->
        [RENEW] <i>⚠️ Your current subscription will be <u>extended</u> by the chosen term.</i>
       *[other] <i>⚠️ Your current subscription will be <u>replaced</u> with the chosen plan. The unused part of your payment is added to the new term.</i>
    }
msg-purchase-confirm =
    <b>🛒 { $purchase_type ->
        [RENEW] Confirm renewal
        [CHANGE] Confirm plan change
       *[other] Confirm purchase
    }</b>

    <blockquote>
    • <b>Plan</b>: { $plan_name }
    • <b>Traffic limit</b>: { $traffic_limit ->
        [0] Unlimited
       *[other] { $traffic_limit } GB
    }
    • <b>Device limit</b>: { $device_limit ->
        [0] Unlimited
       *[other] { $device_limit }
    }
    • <b>Duration</b>: { $period }
    • <b>Payment method</b>: { $method }
    • <b>Without discount</b>: <s>{ $original_price } { $currency_symbol }</s>
    • <b>To pay</b>: { $price } { $currency_symbol }
    </blockquote>

    { $type_notice }

    { $plan_changed_notice }

    { $terms_notice }
frg-purchase-terms-notice = <i>By paying you accept the terms — /terms</i>
frg-subscription-recurring = <b>Auto-renewal enabled</b>: up to { $amount } { $currency } for every { $days } days. Use the button below to stop future charges.
frg-subscription-recurring-off = <b>Auto-renewal disabled</b>. Enabling it authorizes automatic charges of up to { $amount } { $currency } for every { $days } days before the subscription expires.
frg-subscription-recurring-paused = <b>Auto-renewal paused</b>: automatic charges are currently unavailable. Your preference is saved; use the button below to opt out.
btn-recurring =
    .consent-off = [ ] Auto-renewal
    .consent-on = [x] Auto-renewal
    .terms = Renewal terms
    .enable = I agree, enable auto-renewal
    .disable = Disable auto-renewal
ntf-recurring =
    .consent-required = Consent to auto-renewal to pay with YooKassa, or choose another payment method.
    .terms-changed = Payment or renewal terms changed. Select a duration and confirm your consent again.
    .enabled = Auto-renewal enabled.
    .disabled = Auto-renewal disabled. No new charges will be sent; a payment already submitted may still complete.
    .unavailable = Auto-renewal is unavailable. Pay for the subscription with YooKassa or contact support.
msg-purchase-pay = Your order is ready. Tap the button below to pay.
msg-purchase-link-choice = You already have a { $plan_name } subscription. Renew it or buy another one?

btn-purchase =
    .duration = { $period } — { $price } { $currency_symbol }
    .back-plans = Back to plans
    .back-plans-icon = ⬅️
    .back-duration = Change duration
    .back-duration-icon = ⬅️
    .back-method = Change payment method
    .back-method-icon = ⬅️
    .method = { $gateway } — { $price } { $currency_symbol }
    .pay = Pay
    .pay-icon = 💳
    .go-to-payment = Go to payment
    .go-to-payment-icon = 💳
    .menu = Main menu
    .menu-icon = ↩️
    .link-renew = Renew: { $subscription }
    .link-renew-icon = 🔄
    .link-new = Buy a new one
    .link-new-icon = 💸

msg-payment-result-success =
    <b>✅ Payment successful!</b>

    { $purchase_type ->
    [RENEW] Subscription { $plan_name } renewed.
    [CHANGE] Plan changed to { $plan_name }.
    *[NEW] Subscription { $plan_name } activated. To start using the service, tap “Connect” and follow the instructions!
    }
msg-payment-result-failed =
    <b>❌ Something went wrong!</b>

    Don't worry, support has already been notified and will contact you shortly. We apologize for the inconvenience.
msg-payment-result-canceled = <b>Payment canceled.</b> The order is no longer valid — you can place it again.

btn-payment-result =
    .subscription = My subscription
    .subscription-icon = 💳
    .retry = Try again
    .retry-icon = 🔄
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
    .no-subscription = ❌ You have no subscription the bonus days can be added to.
    .days-redeemed = ✅ Bonus days have been added to your subscription.
    .redeem-failed = ❌ Bonus days can't be added to this subscription.
    .code-reset = ✅ Your referral link has been updated. The old one will no longer work.
    .reset-cooldown = ⏳ You can update your referral link again in { $wait }.

ntf-promocode =
    .not-found = ❌ Promocode not found.
    .expired = ❌ This promocode has expired.
    .already-activated = ❌ You've already activated this promocode.
    .discount-not-better = ⚠️ The promocode wasn't applied: your current discount is the same or bigger.
    .not-available = ❌ This promocode isn't available to you.
    .no-target-subscription = ❌ You have no active subscription to apply this promocode to.
    .activated = ✅ Promocode activated!
    .activation-failed = ❌ Failed to activate the promocode. Please try again later.
    .too-many-attempts = ⏳ Too many attempts. Try again in a minute.

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
    .resubscribe-icon = 🔔

ntf-broadcast =
    .unsubscribed = You won't receive offers anymore. Service messages will still arrive.
    .resubscribed = ✅ You'll receive offers again.
    .promo-gone = ❌ This offer is no longer available.
    .start-required = Press /start to continue.

ntf-requirements =
    .channel = Subscribe to our channel to continue.
    .channel-not-found = ⚠️ We can't see your subscription yet. Subscribe and try again.
    .trial-paused = You left our channel, so your trial is paused. Subscribe again to continue.
    .trial-resumed = You're back in our channel, so your trial is running again.

btn-requirements =
    .subscribe = Subscribe
    .subscribe-icon = ❤️
    .check = I've subscribed
    .check-icon = ✅

ntf-cabinet-login =
    .link = Tap the button to sign in to the web cabinet. The link works once and expires in 5 minutes.
    .expired = ⚠️ This sign-in link has expired. Request a new one in the cabinet.
    .unavailable = ⚠️ Signing in to the cabinet with Telegram is unavailable right now. Try again later or use another sign-in method.

btn-cabinet-login =
    .open = Sign in to the cabinet
    .open-icon = 🌐

ntf-cabinet-link =
    .link = Tap the button to link this Telegram to your web cabinet account. The link is single-use and valid for 5 minutes.
    .expired = The linking link has expired. Request a new one in the cabinet.

btn-cabinet-link =
    .open = Link to cabinet
    .open-icon = 🔗

time-unit =
    .day = { $value ->
        [one] { $value } day
       *[other] { $value } days
    }
    .month = { $value ->
        [one] { $value } month
       *[other] { $value } months
    }
    .year = { $value ->
        [one] { $value } year
       *[other] { $value } years
    }
    .hour = { $value } h
    .minute = { $value } min

inline-invite =
    .title = Invite a friend
    .description = Tap to send your invitation link!
    .message =
        🚀 Hi! Looking for a fast and reliable VPN?

        { $bot_name } can help you with that!

        ↘️ TAP THE BUTTON AND TRY IT FOR FREE!
    .start = Join
    .start-icon = 🚀

frg-purchase-recurring-required = This payment method is available with auto-renewal only. Read the terms and give separate consent before paying.

frg-subscription-recurring-retrying = <b>Auto-renewal enabled, awaiting another payment attempt</b>: up to { $amount } { $currency } every { $days } days.
frg-subscription-recurring-pending = <b>Automatic payment is being processed</b>. Awaiting YooKassa confirmation. Disabling stops new charges; a submitted payment may still complete.
frg-subscription-recurring-reason = Reason: { $reason }.
frg-subscription-recurring-next-retry = Next payment attempt: { $when } UTC.
frg-subscription-recurring-next-check = Next payment check: { $when } UTC.

frg-purchase-recurring-preserved = A one-time payment does not cancel previously enabled auto-renewal. You can disable it in your subscription settings.
