event-error =
    .general =
    #ErrorEvent

    <b>🔅 رویداد: یک خطا رخ داد!</b>

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

    <b>⚠️ رویداد: ناسازگاری احتمالی با Remnawave!</b>

    <blockquote>
    نسخه پنل <b>{ $panel_version }</b> بالاتر از نسخه تست شده <b>{ $max_version }</b> است. برخی از ویژگی‌های ربات ممکن است به درستی کار نکنند.
    </blockquote>

    { frg-build-info }
    
    .remnawave =
    #RemnawaveErrorEvent

    <b>🔅 رویداد: خطا در اتصال به Remnawave!</b>

    <blockquote>
    بدون اتصال فعال، ربات نمی‌تواند به درستی کار کند!
    </blockquote>

    { frg-build-info }

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>

    .webhook =
    #ErrorEvent

    <b>🔅 رویداد: خطای وب‌هوک تشخیص داده شد!</b>

    { hdr-error }
    <blockquote>
    { $error }
    </blockquote>


event-bot =
    .startup =
    #BotStartupEvent

    <b>🔅 رویداد: ربات شروع به کار کرد!</b>

    { frg-build-info }

    <b>🔓 دسترسی:</b>
    <blockquote>
    • <b>حالت</b>: { access-mode }
    • <b>پرداخت‌ها</b>: { $payments_allowed ->
    [0] غیرفعال
    *[1] فعال
    }
    • <b>ثبت‌نام</b>: { $registration_allowed ->
    [0] غیرفعال
    *[1] فعال
    }
    </blockquote>

    .shutdown =
    #BotShutdownEvent

    <b>🔅 رویداد: ربات متوقف شد!</b>

    { frg-build-info }

    <blockquote>
    • <b>مدت کارکرد</b>: { $uptime }
    </blockquote>

    .update =
    #BotUpdateEvent

    <b>🔅 رویداد: به‌روزرسانی Remnashop تشخیص داده شد!</b>

    <b>📑 نسخه‌ها:</b>
    <blockquote>
    • <b>کنونی</b>: { $local_version }
    • <b>آخرین</b>: { $remote_version }
    </blockquote>


event-user =
    .registered =
    #UserRegisteredEvent

    <b>🔅 رویداد: کاربر جدید!</b>

    { hdr-user }
    { frg-user-info }

    { $referrer_telegram_id ->
    [0] { empty }
    *[HAS]
    <b>🤝 معرف:</b>
    <blockquote>
    • <b>شناسه</b>: <code>{ NUMBER($referrer_telegram_id, useGrouping: 0) }</code>
    • <b>نام</b>: { $referrer_name } { $referrer_username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $referrer_telegram_id }">@{ $referrer_username }</a>)
    }
    </blockquote>
    }

    .first-connected =
    #UserFirstConnectionEvent

    <b>🔅 رویداد: اولین اتصال کاربر!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-subscription }
    { frg-subscription-details }

    .device-added =
    #UserDeviceAddedEvent

    <b>🔅 رویداد: کاربر دستگاه جدید اضافه کرد!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }

    .device-deleted =
    #UserDeviceDeletedEvent

    <b>🔅 رویداد: کاربر دستگاهی حذف کرد!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-hwid }
    { frg-user-hwid }
    

event-subscription =
    .trial =
    #SubscriptionTrialEvent

    <b>🔅 رویداد: اشتراک آزمایشی دریافت شد!</b>
    { hdr-user }
    { frg-user-info }
    
    { hdr-plan }
    { frg-plan-snapshot }
    
    .new =
    #SubscriptionNewEvent

    <b>🔅 رویداد: اشتراک خریداری شد!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

    .renew =
    #SubscriptionRenewEvent

    <b>🔅 رویداد: اشتراک تمدید شد!</b>
    
    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot }

    .change =
    #SubscriptionChangeEvent

    <b>🔅 رویداد: اشتراک تغییر کرد!</b>

    { hdr-payment }
    { frg-payment-info }

    { hdr-user }
    { frg-user-info }

    { hdr-plan }
    { frg-plan-snapshot-comparison }

    .expiring =
    { $is_trial ->
    [0]
    <b>⚠️ توجه! اشتراک شما پس از { unit-day } منقضی می‌شود.</b>
    
    از قبل تمدید کنید تا دسترسی به سرویس را از دست ندهید! 
    *[1]
    <b>⚠️ توجه! آزمایشی رایگان شما پس از { unit-day } منقضی می‌شود.</b>

    اشتراک بگیرید تا دسترسی به سرویس را از دست ندهید! 
    }

    .expired =
    <b>⛔ توجه! دسترسی متوقف شده — VPN کار نمی‌کند.</b>

    { $is_trial ->
    [0] اشتراک شما منقضی شده. تمدید کنید تا استفاده از VPN ادامه یابد!
    [1] دوره آزمایشی رایگان تمام شده. اشتراک بگیرید تا استفاده از سرویس ادامه یابد!
    }

    .expired-ago =
    <b>⛔ توجه! دسترسی متوقف شده — VPN کار نمی‌کند.</b>

    { $is_trial ->
    [0] اشتراک شما { unit-day } پیش منقضی شده. تمدید کنید تا استفاده از سرویس ادامه یابد!
    [1] دوره آزمایشی رایگان شما { unit-day } پیش تمام شده. اشتراک بگیرید تا استفاده از سرویس ادامه یابد!
    }

    .limited =
    <b>⛔ توجه! دسترسی متوقف شده — VPN کار نمی‌کند.</b>

    ترافیک شما تمام شده. { $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] اشتراک را تمدید کنید تا ترافیک بازنشانی شود!
        *[RESET] ترافیک پس از { $reset_time } بازنشانی می‌شود. می‌توانید اشتراک را تمدید کنید.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] اشتراک بگیرید تا ادامه دهید!
        *[RESET] ترافیک پس از { $reset_time } بازنشانی می‌شود. می‌توانید اشتراک بگیرید.
        }
    }

    .revoked =
    #SubscriptionRevokedEvent

    <b>🔅 رویداد: کاربر اشتراک را صدور مجدد کرد!</b>

    { hdr-user }
    { frg-user-info }

    { hdr-subscription }
    { frg-subscription-details }


event-node =
    .connection-lost =
    #NodeConnectionLostEvent
    
    <b>🔅 رویداد: اتصال به نود از دست رفت!</b>

    { hdr-node }
    { frg-node-info }

    .connection-restored =
    #NodeConnectionRestoredEvent

    <b>🔅 رویداد: اتصال به نود برقرار شد!</b>

    { hdr-node }
    { frg-node-info }

    .traffic-reached =
    #NodeTrafficReachedEvent

    <b>🔅 رویداد: نود به حد مجاز ترافیک رسید!</b>

    { hdr-node }
    { frg-node-info }


event-referral =
    .attached =
    <b>🎉 یک دوست دعوت کردید!</b>
    
    <blockquote>
    کاربر <b>{ $name }</b> از لینک دعوت شما پیوست! برای دریافت پاداش، مطمئن شوید که اشتراک می‌خرد.
    </blockquote>

    .reward =
    <b>💰 پاداش دریافت کردید!</b>
    
    <blockquote>
    کاربر <b>{ $name }</b> پرداخت انجام داد. شما <b>{ $value } { $reward_type ->
    [POINTS] { $value -> 
        [one] امتیاز
        [few] امتیاز
        *[more] امتیاز 
        }

    <i>برای استفاده از امتیازهای خود، به بخش «دعوت» در ربات بروید تا پاداش‌های موجود و نحوه استفاده از آنها را ببینید.</i>
    [EXTRA_DAYS] { $value -> 
        [one] روز
        [few] روز
        *[more] روز
        } </b> به اشتراک شما اضافه شد!
    *[OTHER] { $reward_type }
    }
    </blockquote>

    .reward-failed =
    <b>❌ امکان دادن پاداش وجود ندارد!</b>
    
    <blockquote>
    کاربر <b>{ $name }</b> پرداخت انجام داد، اما نتوانستیم پاداش بدهیم چون <b>شما اشتراک خریداری شده ندارید</b> که { $value } { $reward_type ->
    [POINTS] { $value -> 
        [one] امتیاز
        [few] امتیاز
        *[more] امتیاز 
        }
    [EXTRA_DAYS] { $value -> 
        [one] روز
        [few] روز
        *[more] روز
        }
    *[OTHER] { $reward_type }
    } به آن اضافه کنیم.
    
    <i>برای دریافت پاداش برای دوستان دعوت شده، اشتراک بگیرید!</i>
    </blockquote>

event-remnashop-welcome =
    <b>💎 Remnashop v{ $version }</b>

    این پروژه توسط فقط یک <strike>توسعه‌دهنده</strike> برقکار ایجاد و نگهداری می‌شود. از آنجایی که ربات کاملاً رایگان و متن‌باز است، فقط با حمایت شما وجود دارد.

    ⭐ <i>در <a href="{ $repository }">GitHub</a> ستاره بدهید و به <a href="https://t.me/@remna_shop">جامعه</a> ما بپیوندید.</i>