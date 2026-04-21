event-error =
    .general =
    #ErrorEvent

    <b>🔅 Event: An error occurred!</b>

    { frg-build-info }
    
    { $telegram_id -> 
    [0] { space }
    *[HAS]
    { hdr-user }
    { frg-user-info }
    }

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

    .remnawave-version =
    #RemnawaveVersionWarningEvent

    <b>⚠️ Event: Possible incompatibility with Remnawave!</b>

    <blockquote>
    Panel version <b>{ $panel_version }</b> is higher than the tested version <b>{ $max_version }</b>. Some bot features may not work correctly.
    </blockquote>

    { frg-build-info }
    
    .remnawave =
    #RemnawaveErrorEvent

    <b>🔅 Event: Error connecting to Remnawave!</b>

    <blockquote>
    Without an active connection, the bot cannot work correctly!
    </blockquote>

    { frg-build-info }

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

    .webhook =
    #ErrorEvent

    <b>🔅 Event: Webhook error detected!</b>

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>


event-bot =
    .startup =
    #BotStartupEvent

    <b>🔅 Event: Bot started!</b>

    { frg-build-info }

    <b>🔓 Availability:</b>
    <blockquote>
    • <b>Mode</b>: { access-mode }
    • <b>Payments</b>: { $payments_allowed ->
    [0] disabled
    *[1] enabled
    }
    • <b>Registration</b>: { $registration_allowed ->
    [0] disabled
    *[1] enabled
    }
    </blockquote>

    .shutdown =
    #BotShutdownEvent

    <b>🔅 Event: Bot stopped!</b>

    { frg-build-info }

    <blockquote>
    • <b>Uptime</b>: { $uptime }
    </blockquote>

    .update =
    #BotUpdateEvent

    <b>🔅 Event: Remnashop update detected!</b>

    <b>📑 Versions:</b>
    <blockquote>
    • <b>Current</b>: { $local_version }
    • <b>Latest</b>: { $remote_version }
    </blockquote>


event-user =
    .registered =
    #UserRegisteredEvent

    <b>🔅 Event: New user!</b>

    { hdr-user }
    { frg-user-info }

    { $referrer_telegram_id ->
    [0] { empty }
    *[HAS]
    <b>🤝 Referrer:</b>
    <blockquote>
    • <b>ID</b>: <code>{ NUMBER($referrer_telegram_id, useGrouping: 0) }</code>
    • <b>Name</b>: { $referrer_name } { $referrer_username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $referrer_telegram_id }">@{ $referrer_username }</a>)
    }
    </blockquote>
    }

    .first-connected =
    #UserFirstConnectionEvent

    <b>🔅 Event: User's first connection!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-subscription }
    { frg-subscription-details }

    .device-added =
    #UserDeviceAddedEvent

    <b>🔅 Event: User added a new device!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }

    .device-deleted =
    #UserDeviceDeletedEvent

    <b>🔅 Event: User deleted a device!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }
    

event-subscription =
    .trial =
    #SubscriptionTrialEvent

    <b>🔅 Event: Trial subscription received!</b>
    { hdr-user }
    { frg-user-info }
    
    { hdr-plan }
    { frg-plan-snapshot }
    
    .new =
    #SubscriptionNewEvent

    <b>🔅 Event: Subscription purchased!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

    .renew =
    #SubscriptionRenewEvent

    <b>🔅 Event: Subscription renewed!</b>
    
    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

    .change =
    #SubscriptionChangeEvent

    <b>🔅 Event: Subscription changed!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot-comparison }

    .expiring =
    { $is_trial ->
    [0]
    <b>⚠️ Attention! Your subscription expires in { unit-day }.</b>
    
    Renew it in advance so you don't lose access to the service! 
    *[1]
    <b>⚠️ Attention! Your free trial expires in { unit-day }.</b>

    Get a subscription so you don't lose access to the service! 
    }

    .expired =
    <b>⛔ Attention! Access suspended — VPN not working.</b>

    { $is_trial ->
    [0] Your subscription has expired. Renew it to continue using VPN!
    [1] Your free trial period has ended. Get a subscription to continue using the service!
    }

    .expired-ago =
    <b>⛔ Attention! Access suspended — VPN not working.</b>

    { $is_trial ->
    [0] Your subscription expired { unit-day } ago. Renew it to continue using the service!
    [1] Your free trial period ended { unit-day } ago. Get a subscription to continue using the service!
    }

    .limited =
    <b>⛔ Attention! Access suspended — VPN not working.</b>

    Your traffic is exhausted. { $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] Renew your subscription to reset traffic and continue using the service!
        *[RESET] Traffic will be restored in { $reset_time }. You can also renew your subscription to reset traffic.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] Get a subscription to continue using the service!
        *[RESET] Traffic will be restored in { $reset_time }. You can also get a subscription to use the service without restrictions.
        }
    }

    .revoked =
    #SubscriptionRevokedEvent

    <b>🔅 Event: User reissued subscription!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-subscription }
    { frg-subscription-details }


event-node =
    .connection-lost =
    #NodeConnectionLostEvent
    
    <b>🔅 Event: Connection to node lost!</b>

    { hdr-node }
    { frg-node-info }

    .connection-restored =
    #NodeConnectionRestoredEvent

    <b>🔅 Event: Connection to node restored!</b>

    { hdr-node }
    { frg-node-info }

    .traffic-reached =
    #NodeTrafficReachedEvent

    <b>🔅 Event: Node reached traffic limit!</b>

    { hdr-node }
    { frg-node-info }


event-referral =
    .attached =
    <b>🎉 You invited a friend!</b>
    
    <blockquote>
    User <b>{ $name }</b> joined via your referral link! To get your reward, make sure they purchase a subscription.
    </blockquote>

    .reward =
    <b>💰 You received a reward!</b>
    
    <blockquote>
    User <b>{ $name }</b> made a payment. You received <b>{ $value } { $reward_type ->
    [POINTS] { $value -> 
        [one] point
        [few] points
        *[more] points 
        }

    <i>To use your points, go to the "Invite" section in the bot to see available rewards and how to use them.</i>
    [EXTRA_DAYS] extra { $value -> 
        [one] day
        [few] days
        *[more] days
        } </b> added to your subscription!
    *[OTHER] { $reward_type }
    }
    </blockquote>

    .reward-failed =
    <b>❌ Could not give reward!</b>
    
    <blockquote>
    User <b>{ $name }</b> made a payment, but we couldn't give you a reward because <b>you don't have a purchased subscription</b> to add { $value } { $reward_type ->
    [POINTS] { $value -> 
        [one] point
        [few] points
        *[more] points 
        }
    [EXTRA_DAYS] extra { $value -> 
        [one] day
        [few] days
        *[more] days
        }
    *[OTHER] { $reward_type }
    } to.
    
    <i>Get a subscription to receive bonuses for invited friends!</i>
    </blockquote>

event-remnashop-welcome =
    <b>💎 Remnashop v{ $version }</b>

    This project was created and maintained by just one <strike>developer</strike> electrician. Since the bot is completely FREE and open source, it exists only thanks to your support.

    ⭐ <i>Star it on <a href="{ $repository }">GitHub</a> and join our <a href="https://t.me/@remna_shop">community</a>.</i>