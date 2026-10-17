msg-main-menu = Main menu, { $user_name }!
msg-window-gone = This screen is no longer available.
msg-paysupport = To request a refund, contact support.
msg-menu-devices = Your devices ({ $devices_current }/{ $devices_max })
msg-menu-devices-confirm-delete = Delete this device?
msg-menu-devices-confirm-delete-all = Delete every device? Each one has to be connected again.
msg-menu-devices-confirm-reissue = Reissue the connection link? The old link will stop working.

btn-menu =
    .connect = Connect
    .connect-not-available = Connection unavailable
    .trial = Try for free
    .trial-paid = Trial — { $trial_price }
    .devices = Devices
    .devices-icon = 📱
    .support = Support
    .support-icon = 🆘
    .web-cabinet = Web cabinet
    .web-cabinet-icon = 🌐
    .subscriptions = My subscriptions
    .purchase = Buy a subscription
    .promocode = Promocode
    .referrals = Referrals

btn-devices =
    .item = { $platform_icon } { $platform } ({ $device_model }) — { $created_at }
    .empty = No connected devices
    .delete-all = Delete all devices
    .reissue = Reissue link
    .confirm-delete = Yes, delete
    .confirm-reissue = Yes, reissue
    .cancel-reissue = Cancel

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
    Invite friends and get rewards.

    Level 1: { $referrals_level_1 }
    Level 2: { $referrals_level_2 }
    Points: { $points }
    Bonus days: { $bonus_days }

    { $referral_url }

btn-subscriptions =
    .purchase = Buy a subscription

btn-subscription =
    .renew = Renew
    .change = Change plan

msg-referrals-withdraw = You have { $points } points. Enter how many to withdraw:
msg-referrals-redeem-target = Choose which subscription gets your { $bonus_days } bonus days:

btn-referrals =
    .copy = Copy link
    .share = Share link
    .withdraw = Withdraw points
    .redeem = Redeem bonus days

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
    .payments-restored = Payments are available again — you can complete your purchase.

ntf-common =
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
    .done = Done! Your subscription will appear shortly.

msg-purchase-plan = Choose a plan:
msg-purchase-duration = { $plan_name }: choose a period:
msg-purchase-method = Choose a payment method:
msg-purchase-confirm = { $plan_name } · { $duration_days } d · { $price } { $currency_symbol } · { $method }
msg-purchase-pay = Your order is ready. Tap the button below to pay.
msg-purchase-link-choice = You already have a { $plan_name } subscription. Renew it or buy another one?

btn-purchase =
    .duration = { $days } d — { $price } { $currency_symbol }
    .method = { $gateway } — { $price } { $currency_symbol }
    .pay = Pay
    .go-to-payment = Go to payment
    .menu = Main menu
    .link-renew = Renew: { $subscription }
    .link-new = Buy a new one

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
    .invalid-amount = Enter a positive number of points.
    .too-many-attempts = Too many requests. Try again in an hour.
    .withdraw-failed = Can't withdraw that amount.
    .withdraw-requested = Withdrawal requested. We'll get in touch with you.
    .no-subscription = You have no active subscription to add the days to.
    .days-redeemed = { $days } bonus days added to your subscription.
    .redeem-failed = Bonus days can't be added to this subscription.

ntf-promocode =
    .not-found = Promocode not found.
    .expired = This promocode has expired.
    .already-activated = You've already activated this promocode.
    .not-available = This promocode isn't available to you.
    .no-target-subscription = You have no active subscription to apply this promocode to.
    .activated = Promocode activated!
    .activation-failed = Failed to activate the promocode. Please try again later.
    .too-many-attempts = Too many attempts. Try again in a minute.

msg-promocode-input = Enter your promocode:
msg-promocode-target = Choose which subscription to apply the promocode to:
msg-promocode-confirm = Code: { $promo_code }
    Reward: { $promo_reward_type } { $promo_reward }
msg-promocode-confirm-will-replace = ⚠️ This will replace your current subscription.

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
    .unsubscribe = Unsubscribe from offers
    .resubscribe = Get offers again

ntf-broadcast =
    .unsubscribed = You won't receive offers anymore. Service messages will still arrive.
    .resubscribed = You'll receive offers again.
    .promo-gone = This offer is no longer available.
    .start-required = Press /start to continue.

ntf-requirements =
    .rules = Please read and accept the rules to continue.
    .channel = Subscribe to our channel to continue.
    .channel-not-found = We can't see your subscription yet. Subscribe and try again.

btn-requirements =
    .rules = Read the rules
    .accept = I accept
    .subscribe = Subscribe
    .check = I've subscribed

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
