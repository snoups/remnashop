ntf-test = Push notifications work on this device.
    .title = Test notification
ntf-session-theft-detected = A reused refresh token ended session #{ $session_id } of user #{ $user_id }. IP: { $ip }
    .title = Session theft detected!
    .emoji = ⚠️
ntf-login-failed = Wrong password for “{ $login }”. IP: { $ip }
    .title = Failed sign-in attempt!
    .emoji = ⚠️
ntf-passkey-login-failed = Passkey sign-in was rejected. IP: { $ip }
    .title = Failed sign-in attempt!
    .emoji = ⚠️
ntf-oauth-login-failed = { $provider } sign-in was rejected. IP: { $ip }
    .title = Failed sign-in attempt!
    .emoji = ⚠️
ntf-backup-failed = { $kind } backup failed: { $error }
    .title = Backup failed!
    .emoji = ⚠️
ntf-bonus-days-renewal-stuck = { $days } bonus days of user #{ $user_id } were not applied to subscription #{ $subscription_id }: { $error }. Apply them by hand.
    .title = Bonus days not applied!
    .emoji = ⚠️
ntf-subscription-purchased = { $user } bought a subscription ({ $purchase_type })
    .title = { $is_trial ->
        [yes] Trial subscription received!
       *[no] { $purchase_type ->
            [CHANGE] Subscription changed!
            [RENEW] Subscription renewed!
           *[other] Subscription purchased!
        }
    }
ntf-subscription-renewed = { $duration_days ->
        [0] { $user } renewed with no end date
       *[other] { $user } renewed for { $duration_days } days
    }
    .title = Subscription renewed!
ntf-transaction-refunded = Order #{ $order_id }: { $amount } { $currency } refunded via { $gateway_type }
    .title = Payment refunded!
    .emoji = ⚠️
ntf-transaction-partially-refunded = Order #{ $order_id }: partial refund { $amount } { $currency } via { $gateway_type }, check it manually
    .title = Payment refunded!
    .emoji = ⚠️
ntf-transaction-fulfilled-manually = { $actor } issued order #{ $order_id } for { $target } by hand
    .title = Subscription issued manually!
ntf-paid-order-not-fulfilled = Order #{ $order_id }: { $amount } { $currency } via { $gateway_type } is paid, but no subscription was issued yet. Retries continue; check it.
    .title = Payment processing error!
    .emoji = ⚠️
ntf-broadcast-completed = Broadcast #{ $broadcast_id } finished: { $sent } delivered, { $failed } failed, { $blocked } blocked the bot.
    .title = Broadcast finished!
ntf-broadcast-failed = Broadcast #{ $broadcast_id } stopped: { $error }
    .title = Broadcast failed!
    .emoji = ⚠️
ntf-suppressed = { $count } similar alerts since the previous one were not sent.
ntf-sources-merged = Alerts from several sources were merged; the source shown is the last one.
ntf-customer-open-cabinet = Open cabinet
ntf-customer-button-renew = 🔄 Renew subscription
ntf-customer-button-buy = 💳 Buy subscription
ntf-customer-button-close = ❌ Close
ntf-customer-button-connect = 🚀 Connect
ntf-customer-button-support = 📩 Contact support
ntf-customer-button-revoke-sessions = 🔒 End all sessions
ntf-customer-sessions-revoked = ✅ We've signed you out of every session in your account. If that sign-in wasn't you, contact support and we'll look into it.
ntf-customer-subscription-purchased = To start using the service, connect a device and follow the instructions — it takes a couple of minutes.
    .title = { $is_trial ->
        [yes] Trial activated
       *[no] { $paid ->
            [yes] Payment successful!
           *[no] Subscription activated
        }
    }
    .emoji = { $is_trial ->
        [yes] 🎁
       *[no] ✅
    }
ntf-customer-subscription-renewed = { $duration_days ->
        [0] Your subscription no longer expires.
       *[other] Your subscription was extended by { $duration_days ->
            [one] { $duration_days } day
           *[other] { $duration_days } days
        }.
    }
    .title = { $paid ->
        [yes] Payment successful!
       *[no] Subscription renewed
    }
    .emoji = ✅
ntf-customer-subscription-changed = Your subscription was changed. The connection stays the same, nothing to set up.
    .title = { $paid ->
        [yes] Payment successful!
       *[no] Plan changed
    }
    .emoji = ✅
ntf-customer-subscription-add-on-granted = { $addon_type ->
        [TRAFFIC] { $amount } GB of traffic was added to your subscription.
       *[DEVICES] { $amount ->
            [one] { $amount } device
           *[other] { $amount } devices
        } added to your subscription.
    }
    .title = Add-on activated
    .emoji = 🎁
ntf-customer-subscription-granted = Your { $has_plan_name ->
        [yes] “{ $plan_name }” subscription
       *[other] subscription
    } { $duration_days ->
        [0] has no end date.
       *[other] is valid for { $duration_days ->
            [one] { $duration_days } day
           *[other] { $duration_days } days
        }.
    } Connect a device to start using it.
    .title = Subscription granted
    .emoji = 🎁
ntf-customer-transaction-refunded = { $money } will go back the way you paid.
    .title = Payment refunded
    .emoji = 💸
ntf-customer-transaction-partially-refunded = Part of your payment, { $money }, will go back the way you paid.
    .title = Partial refund
    .emoji = 💸
ntf-customer-paid-order-not-fulfilled = We received your payment of { $money }, but the subscription is taking longer than usual. Don't worry: we're already on it. If it doesn't appear soon, contact support.
    .title = Delivery delayed
    .emoji = ⏳
ntf-customer-subscription-expiring = { $is_trial ->
        [yes] Your trial ends in { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    }. Get a subscription to keep your access.
       *[no] Your subscription ends in { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    }. Renew it in advance to keep your access.
    }
    .title = Subscription ending soon
    .emoji = ⚠️
ntf-customer-subscription-expired = { $is_trial ->
        [yes] Your trial has ended. Get a subscription to keep using the VPN.
       *[no] Your subscription has expired. Renew it to keep using the VPN.
    }
    .title = Access paused — the VPN isn't working
    .emoji = ⛔
ntf-customer-subscription-traffic-limited = You've used up your traffic. { $is_trial ->
        [yes] Get a subscription to keep using the service.
       *[no] { $traffic_strategy ->
            [DAY] It comes back tomorrow, or renew your subscription to reset it now.
            [WEEK] It comes back at the start of next week, or renew your subscription to reset it now.
            [MONTH] It comes back at the start of next month, or renew your subscription to reset it now.
            [MONTH_ROLLING] It comes back on your monthly reset day, or renew your subscription to reset it now.
           *[NO_RESET] Renew your subscription to reset your traffic and keep using the service.
        }
    }
    .title = Access paused — the VPN isn't working
    .emoji = ⛔
ntf-customer-subscription-traffic-threshold = { $is_trial ->
        [yes] Get a subscription to keep your access.
       *[no] Renew your subscription to keep your access.
    }
    .title = Traffic running low
    .emoji = ⚠️
ntf-customer-cabinet-new-device-sign-in = Someone signed in to your account from IP address { $ip } ({ $browser }). If it wasn't you, end the sessions on all devices and contact support.
    .title = Sign-in from a new device
    .emoji = 🔐
ntf-customer-accounts-merged = The other account's subscriptions, payments and sign-in methods are now here. If it wasn't you, contact support.
    .title = Accounts merged
    .emoji = 🔗
ntf-customer-referral-reward-issued = { $has_name ->
        [yes] { $name } made a payment —{" "}
       *[no] {""}
    }you've received { $amount } { $reward_type ->
        [EXTRA_DAYS] { $amount ->
            [one] bonus day
           *[other] bonus days
        }
        [POINTS] { $amount ->
            [one] point
           *[other] points
        }
       *[other] reward
    }. Thanks for inviting!
    .title = You've earned a reward!
    .emoji = 💰
ntf-customer-invitee-reward-issued = You got { $amount } { $reward_type ->
        [EXTRA_DAYS] { $amount ->
            [one] bonus day
           *[other] bonus days
        }
        [POINTS] { $amount ->
            [one] point
           *[other] points
        }
       *[other] reward
    } for joining by invitation.
    .title = Welcome bonus
    .emoji = 🎁
ntf-panel-login-failed = Failed Remnawave panel sign-in as “{ $username }”. IP: { $ip }
    .title = Failed Remnawave panel sign-in!
    .emoji = ⚠️
ntf-panel-login-succeeded = Remnawave panel sign-in as “{ $username }”. IP: { $ip }
    .title = Remnawave panel sign-in!
ntf-rescue-cli-used = { $action ->
        [reset_owner_access] The owner’s access was reset: new password, IP allowlist cleared, sessions, passkeys and linked accounts removed.
        [enable_password_login] Password sign-in was turned on.
        [reset_encrypted_secrets] Every secret stored in the database was erased: enter the bot token, gateway, OAuth, SMTP and captcha credentials again.
       *[restore_backup] The database was restored from a backup.
    }
    .title = Rescue console used!
    .emoji = ⚠️
ntf-required-channel-check-failed = The bot can't check membership in channel { $channel_id }: { $error }. Customers are let through until it's fixed.
    .title = Channel/group membership check failed!
    .emoji = ⚠️
    .hint = Customers are let through until it's fixed.
ntf-telegram-webhook-failed = Telegram webhook error: { $error }
    .title = Webhook error detected!
ntf-node-connection-lost = Connection to node “{ $node_name }” lost.
    .title = Node connection lost!
ntf-node-connection-restored = Connection to node “{ $node_name }” restored.
    .title = Node connection restored!
ntf-node-traffic-reached = Node “{ $node_name }” reached its traffic limit.
    .title = Node reached its traffic limit threshold!
ntf-node-billing-due = Payment for node “{ $node_name }” at { $provider } is due { $next_billing_at }.
    .title = Node payment is coming up!
ntf-remnawave-unavailable = Connection to Remnawave lost ({ $error }).
    .title = Remnawave connection error!
ntf-remnawave-restored = Connection to Remnawave restored.
    .title = Remnawave connection restored!
ntf-system-health-degraded = { $kind ->
        [process_down] The { $subject } process is not responding.
        [host_disk_full] The server disk is { $value }% full.
        [host_memory_high] Server memory is { $value }% used.
       *[event_loop_lag] The { $subject } process is responding slowly: event loop p99 is { $value } ms.
    }
    .title = Critical system state!
ntf-system-health-restored = { $kind ->
        [process_down] The { $subject } process is running again.
        [host_disk_full] Server disk usage is back to normal.
        [host_memory_high] Server memory usage is back to normal.
       *[event_loop_lag] The { $subject } process delay is back to normal.
    }
    .title = System state restored!
ntf-remnawave-version-mismatch = Remnawave { $version } is outside the supported range { $supported }.
    .title = Possible Remnawave incompatibility!
    .emoji = ⚠️
ntf-panel-started = Remnawave panel restarted.
    .title = Remnawave panel started!
ntf-bot-started = Bot @{ $username } started.
    .title = Bot started!
ntf-bot-stopped = Bot stopped.
    .title = Bot stopped!
ntf-telegram-user-registered = New customer { $user } joined via the bot.
    .title = New user!
ntf-cabinet-user-registered = New customer { $user } joined via the web cabinet ({ $method }).
    .title = New user!
ntf-telegram-registration-blocked = Registration of { $user } via the bot was blocked.
    .title = Registration blocked!
ntf-cabinet-registration-blocked = Registration of { $user } via the web cabinet was blocked.
    .title = Registration blocked!
ntf-subscription-first-connected = { $user } connected to the VPN for the first time.
    .title = User's first connection!
ntf-torrent-blocker-report = Torrent traffic from { $user } blocked on “{ $node_name }” ({ $destination }).
    .title = BitTorrent traffic detected!
    .emoji = ⚠️
ntf-subscription-expired = { $user }'s subscription expired.
    .title = Subscription expired!
ntf-subscription-traffic-limited = { $user } ran out of traffic.
    .title = Traffic exhausted!
ntf-subscription-revoked = { $user }'s subscription link was reissued.
    .title = User reissued their subscription!
ntf-subscription-not-connected = { $user } hasn't connected { $hours } h after subscribing.
    .title = User hasn't connected!
ntf-customer-subscription-not-connected = You subscribed { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    } ago but haven't used it yet. If setting it up was tricky, contact support — we'll sort it out together.
    .title = Couldn't connect?
    .emoji = 🔌
ntf-customer-subscription-expired-ago = { $is_trial ->
        [yes] Your trial ended { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    } ago. Get a subscription to use the VPN again.
       *[no] Your subscription expired { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    } ago. Renew it to use the VPN again.
    }
    .title = Access paused — the VPN isn't working
    .emoji = ⛔
ntf-customer-torrent-blocker-report = We noticed torrent traffic over the VPN. Torrents are against the service rules, so your connection is limited{ $block_unit ->
        [minute] { " " }for { $block_span ->
            [one] { $block_span } minute
           *[other] { $block_span } minutes
        }
        [hour] { " " }for { $block_span } h
       *[none] {""}
    }. Turn off your torrent client or exclude it from the VPN so it doesn't happen again. Repeated violations may restrict access for longer.
    .title = Connection temporarily limited
    .emoji = ⛔
ntf-customer-promocode-discount-expiring = Your { $percent }% off with promocode { $code } is valid for { $span_unit ->
        [day] { $span ->
            [one] { $span } more day
           *[other] { $span } more days
        }
       *[hour] { $span ->
            [one] { $span } more hour
           *[other] { $span } more hours
        }
    }. Make your purchase before it’s gone.
    .title = Your discount is about to expire
    .emoji = ⏳
ntf-customer-payments-restored = Payments are back! You can now buy or renew a subscription. Thanks for waiting.
    .title = Payments are back
    .emoji = ❇️
ntf-telegram-label =
    .event = Event
    .user = User
    .id = ID
    .telegram-id = Telegram ID
    .name = Name
    .username = Username
    .email = Email
    .details = Details
    .payment = Payment
    .subscription = Subscription
    .trial-subscription = Trial subscription
    .plan = Plan
    .trial-plan = Trial plan
    .promocode = Promocode
    .device = Device
    .build = Build
    .access = Access
    .session = Session
    .order = Order
    .ip = IP
    .login = Login
    .method = Method
    .provider = Provider
    .user-agent = User agent
    .kind = Type
    .run = Run
    .bonus-days = Bonus days
    .channel = Channel
    .error = Error
    .node = Node
    .reason = Reason
    .billing-date = Billing date
    .version = Version
    .supported = Supported
    .bot = Bot
    .broadcast = Broadcast
    .sent = Delivered
    .failed = Failed
    .blocked = Blocked the bot
    .admin = Admin
    .previous-status = Previous status
    .ad-link = Ad link
    .referral-code = Referral code
    .sign-in-method = Sign-in method
    .hours = Hours passed
    .destination = Destination
    .payment-method = Payment method
    .amount = Amount
    .refund = Refund
    .status = Status
    .traffic = Traffic
    .traffic-limit = Traffic limit
    .device-limit = Device limit
    .left = Left
    .duration = Duration
    .type = Type
    .code = Code
    .reward = Reward
    .branch = Branch
    .commit = Commit
    .build-time = Build time
    .mode = Mode
    .payments = Payments
    .registration = Registration
    .uptime = Uptime
    .hwid = HWID
    .platform = Platform
    .model = Model
    .os-version = OS version
    .channel-bot = Bot
    .channel-cabinet = Web cabinet
    .method-password = Password
    .method-passkey = Passkey
    .method-oauth = OAuth
    .refund-full = full
    .refund-partial = partial
    .unlimited = Unlimited
ntf-telegram-subscription-status = { $value ->
        [ACTIVE] Active
        [LIMITED] Out of traffic
        [EXPIRED] Expired
        [DISABLED] Disabled
        [DELETED] Deleted
       *[other] { $value }
    }
ntf-telegram-plan-type = { $value ->
        [TRAFFIC] Traffic
        [DEVICES] Devices
        [BOTH] Traffic + devices
       *[UNLIMITED] Unlimited
    }
ntf-telegram-transaction-status = { $value ->
        [PENDING] Awaiting payment
        [PAID] Paid
        [FAILED] Issue failed
        [CANCELED] Canceled
        [REFUNDED] Refunded
       *[other] { $value }
    }
ntf-telegram-backup-kind = { $value ->
        [DATABASE] Database
        [ASSETS] Files
       *[other] { $value }
    }
ntf-telegram-sign-in-method = { $value ->
        [TELEGRAM] Telegram
        [EMAIL] Email
        [GOOGLE] Google
        [YANDEX] Yandex
       *[other] { $value }
    }
ntf-telegram-oauth-provider = { $value ->
        [GITHUB] GitHub
        [TELEGRAM] Telegram
        [OIDC] OIDC
        [GOOGLE] Google
        [YANDEX] Yandex
       *[other] { $value }
    }
ntf-telegram-access-mode = { $value ->
        [PUBLIC] open to everyone
        [INVITED] invited only
        [RESTRICTED] closed to everyone
       *[other] { $value }
    }
ntf-telegram-payments = { $value ->
        [yes] allowed
       *[no] disabled
    }
ntf-telegram-registration = { $value ->
        [yes] allowed
       *[no] disabled
    }
ntf-telegram-promocode-type = { $value ->
        [DURATION] Duration
        [TRAFFIC] Traffic
        [DEVICES] Devices
        [SUBSCRIPTION] Subscription
        [PERSONAL_DISCOUNT] Personal discount
        [PURCHASE_DISCOUNT] Purchase discount
       *[other] { $value }
    }
ntf-telegram-unlimited = no end date
ntf-telegram-days = { $count ->
        [one] { $count } day
       *[other] { $count } days
    }
ntf-telegram-uptime = { $days ->
        [0] { $hours } h { $minutes } min
       *[other] { $days } d { $hours } h
    }
ntf-telegram-traffic = { $unit ->
        [MB] { $amount } MB
        [TB] { $amount } TB
       *[GB] { $amount } GB
    }
ntf-subscription-changed = { $user } changed their subscription plan.
    .title = Subscription changed!
ntf-subscription-device-added = { $user } added a new device.
    .title = User added a new device!
ntf-subscription-device-removed = { $user } removed a device.
    .title = User removed a device!
ntf-promocode-activated = { $user } activated a promocode.
    .title = Promocode activated!
ntf-customer-referral-attached = { $name } joined through your invite link.{ $rewarded ->
        [yes] { " " }You'll get your reward once they pay for a subscription.
       *[no] {""}
    }
    .title = You invited a friend!
    .emoji = 🎉
