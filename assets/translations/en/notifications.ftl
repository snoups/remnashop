ntf-error =
    .unknown = ⚠️ <i>An error occurred.</i>
    .permission-denied = ⚠️ <i>You don't have enough permissions.</i>
    .log-not-found = ⚠️ <i>Log file not found.</i>
    .logs-disabled = ⚠️ <i>File logging is disabled.</i>
    
    .lost-context = ⚠️ <i>An error occurred. Restart the dialog with /start.</i>
    .lost-context-restart = ⚠️ <i>An error occurred. Dialog restarted.</i>

ntf-common =
    .trial-unavailable = ⚠️ <i>Trial subscription is temporarily unavailable.</i>
    .throttling = ⚠️ <i>You're sending too many requests. Please wait.</i>
    .double-click-confirm = ⚠️ <i>Click again to confirm the action.</i>
    .squads-empty = ⚠️ <i>Squads not found. Check their existence in the panel.</i>

    .withdraw-points = ❌ <i>You don't have enough points to exchange.</i>
    .internal-squads-empty = ❌ <i>Select at least one internal squad.</i>

    .invalid-value = ❌ <i>Invalid value.</i>
    .value-updated = ✅ <i>Parameter successfully updated.</i>

    .plan-not-found = ❌ <i>Plan not found or unavailable.</i>

    .connect-not-available =
    ⚠️ { $status ->
    [LIMITED]
    You have exhausted all available traffic. { $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] Renew your subscription to reset traffic and continue using the service!
        *[RESET] Traffic will be restored in { $reset_time }. You can also renew your subscription to reset traffic.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] Get a subscription to continue using the service!
        *[RESET] Traffic will be restored in { $reset_time }. You can also get a subscription to use the service without restrictions.
        }
    }
    [EXPIRED]  
    { $is_trial ->
    [0] Your subscription has expired. Renew or get a new subscription.
    *[1] Your free trial period has ended. Get a subscription to continue using the service.
    }
    *[OTHER] An error occurred while checking status or subscription was disabled. Contact support.
    }
    
ntf-command =
    .paysupport = 💸 <b>To request a refund, contact support.</b>
    .rules = ⚠️ <b>Please read the <a href="{ $url }">Terms of Use</a> before using the service.</b>
    .help = 🆘 <b>Click the button below to contact support.</b>

ntf-requirement =
    .channel-join-required = ❇️ Subscribe to our channel and get <b>free days, promotions and news</b>. After subscribing, click "Confirm".
    .channel-join-required-left = ⚠️ You unsubscribed from the channel. Subscribe to continue using the bot.
    .rules-accept-required = ⚠️ <b>Before using the service, read and accept the <a href="{ $url }">Terms of Use</a>.</b>
    .channel-join-error = ⚠️ We don't see your channel subscription. Check your subscription and try again.
    
ntf-user =
    .not-found = <i>❌ User not found.</i>
    .transactions-empty = ❌ <i>Transaction list is empty.</i>
    .subscription-empty = ❌ <i>No active subscription found.</i>
    .subscription-deleted = ✅ <i>Subscription successfully deleted.</i>
    .plans-empty = ❌ <i>No available plans.</i>
    .devices-empty = ❌ <i>Device list is empty.</i>
    .allowed-plans-empty = ❌ <i>No available plans to grant access.</i>
    .message-success = ✅ <i>Message sent successfully.</i>
    .message-failed = ❌ <i>Failed to send message.</i>

    .sync-already = ✅ <i>Subscription data is identical.</i>
    .sync-missing-data = ⚠️ <i>Sync not possible. Subscription data is missing in both panel and bot.</i>
    .sync-success = ✅ <i>Subscription sync completed.</i>

    .invalid-expire-time = ❌ <i>Cannot { $operation ->
    [ADD] extend
    *[SUB] shorten
    } subscription by the specified number of days.</i>

    .invalid-points = ❌ <i>Cannot { $operation ->
    [ADD] add
    *[SUB] deduct
    } the specified number of points.</i>

ntf-access =
    .maintenance = 🚧 <i>Bot is under maintenance. Try again later.</i>
    .registration-disabled = ❌ <i>Registration of new users is disabled.</i>
    .registration-invite-only = ❌ <i>Registration is available by invitation only.</i>
    .payments-disabled = 🚧 <i>Payments are temporarily unavailable! You will be notified after restoration.</i>
    .payments-restored = ❇️ <i>Payments restored! Now you can buy or renew your subscription. Thank you for waiting.</i>

ntf-plan =
    .not-file = ⚠️ <i>Send plans as json file.</i>
    .import-failed = ❌ <i>Failed to import.</i>
    .import-success = ✅ <i>Successfully imported.</i>
    .export-plans_not_selected =  ❌ <i>Select at least one plan to export.</i>
    .export-failed = ❌ <i>Failed to export.</i>
    .export-success = ✅ <i>Selected plans exported.</i>
    .trial-single-duration = ❌ <i>Trial plan can only have one duration.</i>
    .duration-already-exists = ❌ <i>Such duration already exists.</i>
    .name-already-exists = ❌ <i>A plan with this name already exists.</i>
    .user-already-allowed = ❌ <i>User identifier already added.</i>

    .updated = ✅ <i>Plan successfully updated.</i>
    .created = ✅ <i>Plan successfully created.</i>
    .deleted = ✅ <i>Plan successfully deleted.</i>

ntf-gateway =
    .not-configured = ❌ <i>Payment gateway is not configured.</i>
    .not-configurable = ❌ <i>Payment gateway has no settings.</i>

    .test-payment-created = ✅ <i><a href="{ $url }">Test payment</a> successfully created.</i>
    .test-payment-error = ❌ <i>Error creating test payment.</i>
    .test-payment-confirmed = ✅ <i>Test payment successfully processed.</i>

ntf-subscription =
    .plans-unavailable = ❌ <i>No plans available at the moment.</i>
    .gateways-unavailable = ❌ <i>No payment systems available at the moment.</i>
    .renew-plan-unavailable = ❌ <i>Current plan is outdated and not available for renewal.</i>
    .payment-creation-failed = ❌ <i>Error creating payment. Try again later.</i>

ntf-manual-transfer =
    .receipt-received = ✅ <i>Receipt received! Wait for admin confirmation.</i>
    .confirmed = ✅ <i>Your payment is confirmed! Subscription activated.</i>
    .rejected = ❌ <i>Your payment was rejected. Contact support.</i>

ntf-broadcast =
    .message = { $content }
    .text-too-long = ❌ Maximum character limit exceeded ({ $max_limit }).
    .list-empty = ❌ <i>Broadcast list is empty.</i>
    .plans-unavailable = ❌ <i>No available plans.</i>
    .audience-unavailable = ❌ <i>No users for selected audience.</i>
    .content-empty = ❌ <i>Content is empty.</i>
    .content-saved = ✅ <i>Content saved successfully.</i>

    .not-cancelable = ❌ <i>Broadcast cannot be canceled.</i>
    .canceled = ✅ <i>Broadcast canceled successfully.</i>
    .deleting = ⚠️ <i>Deleting sent messages.</i>
    .already-deleted = ❌ <i>Broadcast already deleted or being deleted.</i>

    .deleted-success =
        ✅ Broadcast <code>{ $task_id }</code> deleted successfully.

        <blockquote>
        • <b>Total messages</b>: { $total_count }
        • <b>Deleted</b>: { $deleted_count }
        • <b>Failed to delete</b>: { $failed_count }
        </blockquote>

ntf-importer =
    .not-file = ⚠️ <i>Send database as file.</i>
    .db-failed = ❌ <i>Error exporting users from database.</i>
    .users-empty = ❌ <i>User list in database is empty.</i>

    .started = ✅ <i>Import started. Wait for completion...</i>
    .already-running = ⚠️ <i>Import already running. Please wait.</i>

ntf-sync =
    .started = ✅ <i>Sync started. Wait for completion...</i>
    .users-not-found = ❌ <i>Users for sync not found.</i>
    .already-running = ⚠️ <i>Sync already running. Please wait.</i>

ntf-menu-editor =
    .button-saved = ✅ <i>Button saved successfully.</i>
    .invalid-payload = ❌ <i>Invalid URL format for payload.</i>

ntf-devices =
    .deleted = ✅ <i>Device deleted.</i>
    .all-deleted = ✅ <i>All devices deleted.</i>
    .reissued = ✅ <i>Subscription successfully reissued.</i>