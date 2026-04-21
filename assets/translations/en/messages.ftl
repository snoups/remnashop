# Menu
msg-main-menu =
    { hdr-user-profile }
    { frg-user }

    { hdr-subscription }
    { $status ->
    [ACTIVE]
    { frg-subscription }
    [EXPIRED]
    <blockquote>
    • Your subscription has expired.
    
    <i>{ $is_trial ->
    [0] Renew it to continue using the service!
    *[1] Your free trial period has ended. Get a subscription to continue using the service!
    }</i>
    </blockquote>
    [LIMITED]
    <blockquote>
    • Your traffic has been exhausted.

    <i>{ $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] Renew your subscription to reset traffic and continue using the service!
        *[RESET] Traffic will be restored in { $reset_time }. You can also renew your subscription to reset traffic.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] Get a subscription to continue using the service!
        *[RESET] Traffic will be restored in { $reset_time }. You can also get a subscription to use the service without restrictions.
        }
    }</i>
    </blockquote>
    [DISABLED]
    <blockquote>
    • Your subscription is disabled.

    <i>Contact support to find out why!</i>
    </blockquote>
    *[NONE]
    <blockquote>
    • You don't have an active subscription.

    <i>{ $trial_available ->
    [1] 🎁 A free trial is available for you — click the button below to get it.
    *[0] ↘️ To purchase access, go to the "Subscription" menu.
    }</i>
    </blockquote>
    }

msg-menu-devices =
    <b>📱 Device Management</b>

    Connected: <b>{ $current_count } / { $max_count }</b>

    { $has_devices ->
    [0] { empty }
    *[HAS] Click on a device to delete it.
    If you need more devices — change your subscription.
    }

msg-menu-devices-confirm-reissue =
    🔄 <b>Reissue Subscription</b>

    ⚠️ After reset, the old link <b>will stop working</b>.

    You will need:
    • Delete the old subscription from the app
    • Add the new link from the "Connection" section

    Are you sure you want to reset the link?

msg-menu-devices-confirm-delete =
    🗑 Delete device <b>{ $selected_device_label }</b>?

msg-menu-devices-confirm-delete-all =
    🗑 Delete <b>all devices</b>?

msg-menu-invite =
    <b>👥 Invite Friends</b>

    You will receive a reward for each invited friend!

    Your link:
    <code>{ $link }</code>

    <b>{ $referral_count } friends</b> joined using your link.

msg-menu-invite-about =
    <b>👥 Invite & Earn</b>

    <b>Your reward:</b> { $reward }

    <b>How it works:</b>
    1. Share your link with friends
    2. Friends subscribe using your link
    3. Reward is credited automatically!

    <b>Your link:</b>
    <code>{ $link }</code>

    <b>Referrals:</b> { $referral_count }

msg-menu-support =
    <b>🆘 Support</b>

    Select an option to contact support:

msg-menu-dashboard =
    <b>🛠 Dashboard</b>

    Select a section to manage:

msg-invite-referral-link-copied = ✅ Link copied!

msg-invite-referral-reward-received =
    🎉 <b>Referral reward received!</b>

    { $reward } has been credited to your balance.

msg-invite-referral-attached =
    👋 <b>Referral attached!</b>

    Your referrer is now { $referrer_name }.

    Your reward will be credited when they subscribe.


# Subscription
msg-subscription-main = <b>💳 Subscription</b>
msg-subscription-plans = <b>📦 Select a plan</b>
msg-subscription-new-success = To start using our service, click the <code>`{ btn-subscription.connect }`</code> button and follow the instructions!
msg-subscription-renew-success = Your subscription has been renewed for { $added_duration }.

msg-subscription-plan = 
    <b>📦 Available plan via link</b>
    
    The plan <b>{ $name }</b> is available to you via link. Click the button below to go to duration and payment method selection.

    { $description ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $description }
    </blockquote>
    }

    { $purchase_type ->
    [RENEW] <i>⚠️ Your current subscription will be <u>renewed</u> for the selected period.</i>
    [CHANGE] <i>⚠️ Your current subscription will be <u>replaced</u> with this plan without recalculating the remaining time.</i>
    *[OTHER] { empty }
    }
    
msg-subscription-details =
    <b>{ $plan }:</b>
    <blockquote>
    { $description ->
    [0] { empty }
    *[HAS]
    { $description }
    }

    • <b>Traffic limit</b>: { $traffic }
    • <b>Device limit</b>: { $devices }
    { $period ->
    [0] { empty }
    *[HAS] • <b>Duration</b>: { $period }
    }
    { $final_amount ->
    [0] { empty }
    *[HAS] • <b>Price</b>: { frg-payment-amount }
    }
    </blockquote>
    
    <blockquote>
    { $discount_percent ->
    [0] { empty }
    *[HAS] <i>Prices include { $is_personal_discount ->
        [1] your personal discount { $discount_percent }%
        *[0] one-time discount { $discount_percent }%
        }
        </i>
    }
    </blockquote>

msg-subscription-duration = 
    <b>⏳ Select duration</b>

    { msg-subscription-details }

msg-subscription-payment-method =
    <b>💳 Select payment method</b>

    { msg-subscription-details }

msg-subscription-confirm =
    <b>🛒 Confirm { $purchase_type ->
    [RENEW] renewal
    [CHANGE] change
    *[OTHER] purchase
    } of subscription</b>

    { msg-subscription-details }

    { $purchase_type ->
    [RENEW] <i>⚠️ Your current subscription will be <u>renewed</u> for the selected period.</i>
    [CHANGE] <i>⚠️ Your current subscription will be <u>replaced</u> with the selected one without recalculating the remaining time.</i>
    *[OTHER] { empty }
    }

msg-manual-transfer-receipt =
    <b>🏦 Payment details</b>

    { msg-subscription-details }

    <b>Transfer details:</b>
    { $bank_name ->
        *[not_empty] • Bank: { $bank_name }
    }
    { $account_holder ->
        *[not_empty] • Account holder: { $account_holder }
    }
    { $account_number ->
        *[not_empty] • Account: { $account_number }
    }
    { $card_number ->
        *[not_empty] • Card: { $card_number }
    }

    <i>📎 Send a receipt/screenshot of payment to this chat.</i>

msg-subscription-trial =
    <b>✅ Trial subscription successfully received!</b>

    { msg-subscription-new-success }

msg-subscription-success =
    <b>✅ Payment successful!</b>

    { $purchase_type ->
    [NEW] { msg-subscription-new-success }
    [RENEW] { msg-subscription-renew-success }
    [CHANGE] { msg-subscription-new-success }
    *[OTHER]
    }

msg-subscription-failed =
    ❌ <b>Payment failed!</b>

    Something went wrong. Try again or contact support.


# Menu Editor
msg-menu-editor-main = <b>🎛 Extra Buttons</b>
msg-menu-editor-edit = <b>✏️ Edit Button</b>


# Referral
msg-referral-main = <b>👥 Referral System</b>

    <b>Level:</b> { $level }
    <b>Reward:</b> { $reward }


# Access
msg-access-main = <b>🔓 Access Mode</b>

msg-access-rules =
    <b>📜 Terms of Use</b>

    Please read the terms of use carefully before using the service.

msg-access-channel =
    <b>❇️ Channel Subscription</b>

    Subscribe to our channel to continue using the bot.


# Promocodes
msg-promocode-main = <b>🎟 Promo Codes</b>
msg-promocode-activate = <b>🎟 Activate Promo Code</b>
msg-promocode-success = ✅ <b>Promo code activated!</b>
msg-promocode-invalid = ❌ <b>Invalid promo code.</b>


# Statistics
msg-statistics-main = <b>📊 Statistics</b>

msg-statistics-users =
    <b>👥 Users</b>

    <b>📊 Statistics:</b>
    <blockquote>
    • <b>Total</b>: { $total }
    • <b>Active</b>: { $active }
    • <b>Expired</b>: { $expired }
    • <b>Disabled</b>: { $disabled }
    </blockquote>

msg-statistics-subscriptions =
    <b>💳 Subscriptions</b>

msg-statistics-transactions =
    <b>🧾 Transactions</b>

msg-statistics-referrals =
    <b>👪 Referrals</b>


# Gateways
msg-gateways-main = <b>🌐 Payment Systems</b>

msg-gateways-settings =
    <b>🌐 Configuration { gateway-type }</b>

    { $settings }


# Broadcast
msg-broadcast-main = <b>📢 Broadcast</b>
msg-broadcast-preview = <b>👀 Preview</b>


# Importer
msg-importer-main = <b>📥 User Import</b>
msg-importer-sync = <b>🌀 Sync Users</b>
msg-importer-from-xui = <b>📥 Import from x-ui</b>


# Notifications
msg-notifications-main = <b>🔔 Notification Settings</b>
msg-notifications-user = <b>👥 User Notifications</b>
msg-notifications-system = <b>⚙️ System Notifications</b>


# Plans
msg-plans-main = <b>📦 Plans</b>
msg-plans-create = <b>🆕 Create Plan</b>
msg-plans-edit = <b>✏️ Edit Plan</b>
msg-plans-delete = <b>🗑️ Delete Plan</b>


# User Profile
msg-user-profile = { hdr-user-profile } { frg-user-details }


# Notifications
msg-system-updated =
    ✅ <b>System updated!</b>

msg-user-created =
    ✅ <b>User created successfully!</b>

msg-user-deleted =
    ✅ <b>User deleted successfully!</b>

msg-user-subscription-set =
    ✅ <b>Subscription set successfully!</b>

msg-user-subscription-deleted =
    ✅ <b>Subscription deleted successfully!</b>

msg-user-subscription-revoked =
    ✅ <b>Subscription revoked successfully!</b>

msg-user-devices-deleted =
    ✅ <b>All devices deleted!</b>

msg-user-devices-reissued =
    ✅ <b>Devices reissued successfully!</b>

msg-user-devices-synced =
    ✅ <b>User devices synced successfully!</b>

msg-user-broadcast-sent =
    ✅ <b>Message sent to user!</b>

msg-user-transaction-info =
    <b>🧾 Transaction Info</b>

    { hdr-payment }
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Type</b>: { purchase-type }
    • <b>Status</b>: { transaction-status }
    • <b>Payment method</b>: { gateway-type }
    • <b>Amount</b>: { frg-payment-amount }
    • <b>Created</b>: { $created_at }
    </blockquote>

    { $is_test -> 
    [1] ⚠️ Test transaction
    *[0]
    { hdr-plan }
    { frg-plan-snapshot }
    }
    
msg-user-role = 
    <b>👮‍♂️ Change Role</b>
    
    Select a new role for the user.

msg-users-blacklist =
    <b>🚫 Blacklist</b>

    Blocked: <b>{ $count_blocked }</b> / <b>{ $count_users }</b> ({ $percent }%).

msg-user-message =
    <b>📩 Send Message to User</b>

    Send any message: text, image or all together (HTML supported).
    

# RemnaWave
msg-remnawave-main =
    <b>🌊 RemnaWave v{ $version }</b>
    
    <b>🖥️ System:</b>
    <blockquote>
    • <b>CPU</b>: { $cpu_cores } { $cpu_cores ->
    [one] core
    [few] cores
    *[more] cores
    }
    • <b>RAM</b>: { $ram_used } / { $ram_total } ({ $ram_used_percent }%)
    • <b>Uptime</b>: { $uptime }
    </blockquote>

msg-remnawave-users =
    <b>👥 Users</b>

    <b>📊 Statistics:</b>
    <blockquote>
    • <b>Total</b>: { $users_total }
    • <b>Active</b>: { $users_active }
    • <b>Disabled</b>: { $users_disabled }
    • <b>Limited</b>: { $users_limited }
    • <b>Expired</b>: { $users_expired }
    </blockquote>

    <b>🟢 Online:</b>
    <blockquote>
    • <b>Today</b>: { $online_last_day }
    • <b>This week</b>: { $online_last_week }
    • <b>Never logged in</b>: { $online_never }
    • <b>Online now</b>: { $online_now }
    </blockquote>

msg-remnawave-host-details =
    <b>{ $remark } ({ $is_disabled ->
    [1] disabled
    *[0] enabled
    }):</b>
    <blockquote>
    • <b>Address</b>: <code>{ $address }:{ $port }</code>
    { $inbound_uuid ->
    [0] { empty }
    *[HAS] • <b>Inbound</b>: <code>{ $inbound_uuid }</code>
    }
    </blockquote>

msg-remnawave-node-details =
    <b>{ $country } { $name } ({ $is_connected ->
    [1] connected
    *[0] disconnected
    }):</b>
    <blockquote>
    • <b>Address</b>: <code>{ $address }{ $port -> 
    [0] { empty }
    *[HAS]:{ $port }
    }</code>
    • <b>Uptime (xray)</b>: { $xray_uptime }
    • <b>Users online</b>: { $users_online }
    • <b>Traffic</b>: { $traffic_used } / { $traffic_limit }
    </blockquote>

msg-remnawave-inbound-details =
    <b>🔗 { $tag }</b>
    <blockquote>
    • <b>ID</b>: <code>{ $inbound_id }</code>
    • <b>Protocol</b>: { $type } { $network -> 
    [0] { space }
    *[HAS] ({ $network })
    }
    { $port ->
    [0] { empty }
    *[HAS] • <b>Port</b>: { $port }
    }
    { $security ->
    [0] { empty }
    *[HAS] • <b>Security</b>: { $security } 
    }
    </blockquote>


# Plans
msg-plan-internal-squads =
    <b>⏺️ Change Internal Squads List</b>

    Select which internal groups will be assigned to this plan.

msg-plan-external-squads =
    <b>⏹️ Change External Squad</b>

    Select which external group will be assigned to this plan.