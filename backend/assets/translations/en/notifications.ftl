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
ntf-points-withdrawal-requested = { $user } asks to withdraw { $amount } points
    .title = Points withdrawal request
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
ntf-customer-subscription-purchased = Your subscription is active. Connection details are in the cabinet and the bot.
    .title = Subscription activated
ntf-customer-subscription-renewed = Your subscription was extended by { $duration_days } days.
    .title = Subscription renewed
ntf-customer-subscription-changed = Your plan was changed. Connection details are in the cabinet and the bot.
    .title = Plan changed
ntf-customer-subscription-add-on-granted = An add-on was added to your subscription.
    .title = Add-on activated
ntf-customer-subscription-granted = You were given a subscription for { $duration_days } days.
    .title = Subscription granted
ntf-customer-transaction-refunded = Your payment of { $amount } { $currency } was refunded.
    .title = Payment refunded
ntf-customer-transaction-partially-refunded = { $amount } { $currency } of your payment was refunded.
    .title = Partial refund
ntf-customer-subscription-expiring = Your subscription ends in { $hours } h.
    .title = Subscription ending soon
ntf-customer-subscription-expired = Your subscription has expired.
    .title = Subscription expired
ntf-customer-subscription-traffic-limited = Your traffic limit is reached.
    .title = Traffic limit reached
ntf-customer-subscription-traffic-threshold = Your traffic is running low.
    .title = Traffic running low
ntf-customer-cabinet-new-device-sign-in = New sign-in to your cabinet from { $ip } ({ $browser }). If it wasn't you, sign out everywhere in the cabinet and contact support.
    .title = New sign-in
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
