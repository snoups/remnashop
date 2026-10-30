ntf-test = Push notifications work on this device.
    .title = Test notification
ntf-session-theft-detected = A reused refresh token ended session #{ $session_id } of user #{ $user_id }. IP: { $ip }
    .title = Session theft
ntf-login-failed = Wrong password for “{ $login }”. IP: { $ip }
    .title = Login failed
ntf-passkey-login-failed = Passkey sign-in was rejected. IP: { $ip }
    .title = Passkey login failed
ntf-oauth-login-failed = { $provider } sign-in was rejected. IP: { $ip }
    .title = OAuth login failed
ntf-backup-failed = { $kind } backup failed: { $error }
    .title = Backup failed
ntf-bonus-days-renewal-stuck = { $days } bonus days of user #{ $user_id } were not applied to subscription #{ $subscription_id }: { $error }. Apply them by hand.
    .title = Bonus days not applied
ntf-subscription-purchased = { $user } bought a subscription ({ $purchase_type })
    .title = Subscription purchased
ntf-subscription-renewed = { $user } renewed for { $duration_days } days
    .title = Subscription renewed
ntf-transaction-refunded = Order #{ $order_id }: { $amount } { $currency } refunded via { $gateway_type }
    .title = Transaction refunded
ntf-transaction-partially-refunded = Order #{ $order_id }: partial refund { $amount } { $currency } via { $gateway_type }, check it manually
    .title = Partial refund
ntf-transaction-fulfilled-manually = { $actor } issued order #{ $order_id } for { $target } by hand
    .title = Subscription issued manually
ntf-paid-order-not-fulfilled = Order #{ $order_id }: { $amount } { $currency } via { $gateway_type } is paid, but no subscription was issued yet. Retries continue; check it.
    .title = Paid order not issued
ntf-admin-created = { $actor } created admin { $target }
    .title = Admin created
ntf-admin-deleted = { $actor } deleted admin { $target }
    .title = Admin deleted
ntf-admin-promoted = { $actor } made { $target } an admin
    .title = Admin appointed
ntf-admin-demoted = { $actor } demoted { $target }
    .title = Admin demoted
ntf-admin-permissions-updated = { $actor } changed permissions of { $target }
    .title = Admin permissions changed
ntf-broadcast-completed = Broadcast #{ $broadcast_id } finished: { $sent } delivered, { $failed } failed, { $blocked } blocked the bot.
    .title = Broadcast sent
ntf-broadcast-failed = Broadcast #{ $broadcast_id } stopped: { $error }
    .title = Broadcast failed
ntf-suppressed = { $count } similar alerts since the previous one were not sent.
ntf-sources-merged = Alerts from several sources were merged; the source shown is the last one.
ntf-customer-open-cabinet = Open cabinet
ntf-customer-button-renew = Renew subscription
ntf-customer-button-buy = Buy a subscription
ntf-customer-button-close = Close
ntf-customer-subscription-purchased = Your subscription is active. Connect a device to start using it.
    .title = Subscription activated
ntf-customer-subscription-renewed = Your subscription was extended by { $duration_days ->
        [one] { $duration_days } day
       *[other] { $duration_days } days
    }.
    .title = Subscription renewed
ntf-customer-subscription-changed = Your plan was changed. Your connection stays the same, nothing to set up.
    .title = Plan changed
ntf-customer-subscription-add-on-granted = { $addon_type ->
        [TRAFFIC] { $amount } GB of traffic was added to your subscription.
       *[DEVICES] { $amount ->
            [one] { $amount } device
           *[other] { $amount } devices
        } added to your subscription.
    }
    .title = Add-on activated
ntf-customer-subscription-granted = You were given a subscription for { $duration_days ->
        [one] { $duration_days } day
       *[other] { $duration_days } days
    }.
    .title = Subscription granted
ntf-customer-transaction-refunded = Your payment of { $money } was refunded.
    .title = Payment refunded
ntf-customer-transaction-partially-refunded = { $money } of your payment was refunded.
    .title = Partial refund
ntf-customer-paid-order-not-fulfilled = We received your payment of { $money }, but issuing the subscription is taking longer than usual. We're on it; if it doesn't arrive soon, contact support.
    .title = Payment received
ntf-customer-subscription-expiring = Your subscription ends in { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    }. { $is_trial ->
        [yes] Get a subscription to keep your access.
       *[no] Renew it to keep your access.
    }
    .title = Subscription ending soon
ntf-customer-subscription-expired = Your subscription has expired. { $is_trial ->
        [yes] Get a subscription to get your access back.
       *[no] Renew it to get your access back.
    }
    .title = Subscription expired
ntf-customer-subscription-traffic-limited = Your traffic limit is reached. { $is_trial ->
        [yes] Get a subscription to get your access back.
       *[no] Renew your subscription to get your access back.
    }
    .title = Traffic limit reached
ntf-customer-subscription-traffic-threshold = Your traffic is running low. { $is_trial ->
        [yes] Get a subscription to keep your access.
       *[no] Renew your subscription to keep your access.
    }
    .title = Traffic running low
ntf-customer-cabinet-new-device-sign-in = New sign-in to your cabinet from { $ip } ({ $browser }). If it wasn't you, sign out on all other devices and contact support.
    .title = New sign-in
ntf-customer-accounts-merged = Your accounts were merged: the other account's subscriptions, payments and sign-in methods are now here. If it wasn't you, contact support.
    .title = Accounts merged
ntf-customer-referral-reward-issued = You got { $amount } { $reward_type ->
        [EXTRA_DAYS] { $amount ->
            [one] bonus day
           *[other] bonus days
        }
        [POINTS] { $amount ->
            [one] point
           *[other] points
        }
       *[other] reward
    } for an invited friend.
    .title = Referral reward
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
ntf-panel-login-failed = Failed Remnawave panel sign-in as “{ $username }”. IP: { $ip }
    .title = Panel sign-in failed
ntf-panel-login-succeeded = Remnawave panel sign-in as “{ $username }”. IP: { $ip }
    .title = Panel sign-in
ntf-rescue-cli-used = { $action ->
        [reset_owner_access] The owner’s access was reset from the rescue console: new password, IP allowlist cleared, sessions, passkeys and linked accounts removed.
        [enable_password_login] Password sign-in was turned on from the rescue console.
        [reset_encrypted_secrets] Every secret stored in the database was erased from the rescue console: enter the bot token, gateway, OAuth, SMTP and captcha credentials again.
       *[restore_backup] The database was restored from a backup from the rescue console.
    }
    .title = Rescue console
ntf-required-channel-check-failed = The bot can't check membership in channel { $channel_id }: { $error }. Customers are let through until it's fixed.
    .title = Channel check failed
ntf-telegram-webhook-failed = Telegram webhook error: { $error }
    .title = Telegram webhook error
ntf-node-connection-lost = Node “{ $node_name }” lost connection.
    .title = Node offline
ntf-node-connection-restored = Node “{ $node_name }” is back online.
    .title = Node online
ntf-node-traffic-reached = Node “{ $node_name }” reached its traffic limit.
    .title = Node traffic limit
ntf-node-billing-due = Payment for node “{ $node_name }” at { $provider } is due { $next_billing_at }.
    .title = Node payment due
ntf-remnawave-unavailable = Remnawave panel doesn't respond ({ $error }).
    .title = Panel unavailable
ntf-remnawave-restored = Remnawave panel responds again.
    .title = Panel available
ntf-remnawave-version-mismatch = Remnawave { $version } is outside the supported range { $supported }.
    .title = Unsupported panel version
ntf-panel-started = Remnawave panel restarted.
    .title = Panel started
ntf-bot-started = Bot @{ $username } started.
    .title = Bot started
ntf-bot-stopped = Bot stopped.
    .title = Bot stopped
ntf-telegram-user-registered = New customer { $user } joined via the bot.
    .title = New customer
ntf-cabinet-user-registered = New customer { $user } joined via the web cabinet ({ $method }).
    .title = New customer
ntf-telegram-registration-blocked = Registration of { $user } via the bot was blocked.
    .title = Registration blocked
ntf-cabinet-registration-blocked = Registration of { $user } via the web cabinet was blocked.
    .title = Registration blocked
ntf-subscription-first-connected = { $user } connected to the VPN for the first time.
    .title = First connection
ntf-torrent-blocker-report = Torrent traffic from { $user } blocked on “{ $node_name }” ({ $destination }).
    .title = Torrent blocked
ntf-subscription-expired = { $user }'s subscription expired.
    .title = Subscription expired
ntf-subscription-traffic-limited = { $user } ran out of traffic.
    .title = Traffic exhausted
ntf-subscription-revoked = { $user }'s subscription link was reissued.
    .title = Link reissued
ntf-subscription-not-connected = { $user } hasn't connected { $hours } h after subscribing.
    .title = Not connected
ntf-customer-subscription-not-connected = You subscribed { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    } ago but haven't connected yet. Connect a device, it only takes a couple of minutes.
    .title = Let's get you connected
ntf-customer-subscription-expired-ago = Your subscription expired { $span_unit ->
        [day] { $span ->
            [one] { $span } day
           *[other] { $span } days
        }
       *[hour] { $span } h
    } ago. { $is_trial ->
        [yes] Get a subscription to get your access back.
       *[no] Renew it to get your access back.
    }
    .title = Subscription expired
ntf-customer-torrent-blocker-report = Using torrents with the VPN on is forbidden. Your torrent traffic was blocked; repeated violations may lead to restrictions.
    .title = Torrents are not allowed
ntf-customer-promocode-discount-expiring = Your { $percent }% discount from promocode { $code } is valid for { $span_unit ->
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
