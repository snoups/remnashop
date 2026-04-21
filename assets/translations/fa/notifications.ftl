ntf-error =
    .unknown = ⚠️ <i>یک خطا رخ داد.</i>
    .permission-denied = ⚠️ <i>دسترسی شما کافی نیست.</i>
    .log-not-found = ⚠️ <i>فایل لاگ پیدا نشد.</i>
    .logs-disabled = ⚠️ <i>لاگ‌گیری غیرفعال است.</i>
    
    .lost-context = ⚠️ <i>خطایی رخ داد. با /start دوباره شروع کنید.</i>
    .lost-context-restart = ⚠️ <i>خطایی رخ داد. مکالمه دوباره شروع شد.</i>

ntf-common =
    .trial-unavailable = ⚠️ <i>اشتراک رایگان فعلاً در دسترس نیست.</i>
    .throttling = ⚠️ <i>درخواست‌های زیادی می‌فرستید. لطفاً صبر کنید.</i>
    .double-click-confirm = ⚠️ <i>برای تأیید، دوباره بزنید.</i>
    .squads-empty = ⚠️ <i>اسکوادی پیدا نشد. از پنل بررسی کنید.</i>

    .withdraw-points = ❌ <i>امتیاز کافی برای تبدیل ندارید.</i>
    .internal-squads-empty = ❌ <i>حداقل یک اسکواد داخلی انتخاب کنید.</i>

    .invalid-value = ❌ <i>مقدار نامعتبر است.</i>
    .value-updated = ✅ <i>با موفقیت به‌روز شد.</i>

    .plan-not-found = ❌ <i>طرح پیدا نشد یا در دسترس نیست.</i>

    .connect-not-available =
    ⚠️ { $status ->
    [LIMITED]
    کل ترافیک استفاده شد. { $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] برای ریست کردن ترافیک و ادامه، اشتراک را تمدید کنید!
        *[RESET] ترافیک بعد از { $reset_time } ریست می‌شود. می‌توانید تمدید کنید.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] برای ادامه، اشتراک بگیرید!
        *[RESET] ترافیک بعد از { $reset_time } ریست می‌شود. می‌توانید بگیرید.
        }
    }
    [EXPIRED]  
    { $is_trial ->
    [0] اشتراک شما منقضی شده. تمدید کنید یا جدید بگیرید.
    [1] دوره رایگان تمام شده. برای ادامه اشتراک بگیرید.
    }
    *[OTHER] خطایی در بررسی وضعیت رخ داد یا اشتراک غیرفعال شده. با پشتیبانی تماس بگیرید.
    }
    
ntf-command =
    .paysupport = 💸 <b>برای درخواست بازگشت پول، با پشتیبانی تماس بگیرید.</b>
    .rules = ⚠️ <b>لطفاً قبل از استفاده، <a href="{ $url }">قوانین</a> را بخوانید.</b>
    .help = 🆘 <b>پایین بزنید تا با پشتیبانی تماس بگیرید.</b>

ntf-requirement =
    .channel-join-required = ❇️ در کانال ما عضو شوید و <b>روز رایگان، تبلیغات و اخبار</b> بگیرید. بعد «تأیید» را بزنید.
    .channel-join-required-left = ⚠️ از کانال خارج شدید! برای ادامه، دوباره عضو شوید.
    .rules-accept-required = ⚠️ <b>قبل از استفاده، <a href="{ $url }">قوانین</a> را بخوانید و بپذیرید.</b>
    .channel-join-error = ⚠️ عضویت شما دیده نمی‌شود! بررسی کنید و دوباره تلاش کنید.
    
ntf-user =
    .not-found = <i>❌ کاربر پیدا نشد.</i>
    .transactions-empty = ❌ <i>تراکنشی نیست.</i>
    .subscription-empty = ❌ <i>اشتراک فعال پیدا نشد.</i>
    .subscription-deleted = ✅ <i>اشتراک با موفقیت حذف شد.</i>
    .plans-empty = ❌ <i>طرحی در دسترس نیست.</i>
    .devices-empty = ❌ <i>دستگاهی نیست.</i>
    .allowed-plans-empty = ❌ <i>طرحی برای دادن دسترسی نیست.</i>
    .message-success = ✅ <i>پیام با موفقیت ارسال شد.</i>
    .message-failed = ❌ <i>ارسال پیام نشد.</i>

    .sync-already = ✅ <i>داده‌ها یکسان هستند.</i>
    .sync-missing-data = ⚠️ <i>همگام‌سازی ممکن نیست. داده اشتراک نیست.</i>
    .sync-success = ✅ <i>همگام‌سازی انجام شد.</i>

    .invalid-expire-time = ❌ <i>امکان { $operation ->
    [ADD] تمدید
    *[SUB] کاهش
    } تاریخ وجود ندارد.</i>

    .invalid-points = ❌ <i>امکان { $operation ->
    [ADD] اضافه کردن
    *[SUB] کم کردن
    } امتیاز نیست.</i>

ntf-access =
    .maintenance = 🚧 <i>ربات در حال تعمیر است. بعداً تلاش کنید.</i>
    .registration-disabled = ❌ <i>ثبت‌نام بسته شده.</i>
    .registration-invite-only = ❌ <i>ثبت‌نام فقط با دعوت امکان‌پذیر است.</i>
    .payments-disabled = 🚧 <i>پرداخت‌ها فعلاً در دسترس نیستند! به‌زودی درست می‌شود.</i>
    .payments-restored = ❇️ <i>پرداخت‌ها درست شدند! می‌توانید اشتراک بگیرید یا تمدید کنید.</i>

ntf-plan =
    .not-file = ⚠️ <i>طرح‌ها را به صورت فایل json بفرستید.</i>
    .import-failed = ❌ <i>ورود نشد.</i>
    .import-success = ✅ <i>با موفقیت وارد شد.</i>
    .export-plans_not_selected =  ❌ <i>حداقل یک طرح برای صادر کردن انتخاب کنید.</i>
    .export-failed = ❌ <i>صادر نشد.</i>
    .export-success = ✅ <i>طرح‌های انتخابی صادر شدند.</i>
    .trial-single-duration = ❌ <i>طرح تست فقط یک مدت می‌تواند داشته باشد.</i>
    .duration-already-exists = ❌ <i>این مدت قبلاً وجود دارد.</i>
    .name-already-exists = ❌ <i>طرحی با این نام قبلاً وجود دارد.</i>
    .user-already-allowed = ❌ <i>این کاربر قبلاً اضافه شده.</i>

    .updated = ✅ <i>طرح با موفقیت به‌روز شد.</i>
    .created = ✅ <i>طرح با موفقیت ساخته شد.</i>
    .deleted = ✅ <i>طرح با موفقیت حذف شد.</i>

ntf-gateway =
    .not-configured = ❌ <i>درگاه پرداخت تنظیم نشده.</i>
    .not-configurable = ❌ <i>این درگاه تنظیماتی ندارد.</i>

    .test-payment-created = ✅ <i><a href="{ $url }">پرداخت تست</a> ساخته شد.</i>
    .test-payment-error = ❌ <i>خطا در ساختن پرداخت تست.</i>
    .test-payment-confirmed = ✅ <i>پرداخت تست با موفقیت انجام شد.</i>

ntf-subscription =
    .plans-unavailable = ❌ <i>در حال حاضر طرحی در دسترس نیست.</i>
    .gateways-unavailable = ❌ <i>در حال حاضر درگاه پرداختی نیست.</i>
    .renew-plan-unavailable = ❌ <i>طرح فعلی قدیمی است و قابل تمدید نیست.</i>
    .payment-creation-failed = ❌ <i>خطا در ساختن پرداخت. دوباره تلاش کنید.</i>

ntf-manual-transfer =
    .receipt-received = ✅ <i>رسید گرفتیم! منتظر تأیید مدیر بمانید.</i>
    .confirmed = ✅ <i>پرداخت شما تأیید شد! اشتراک فعال شد.</i>
    .rejected = ❌ <i>پرداخت شما رد شد. با پشتیبانی تماس بگیرید.</i>

ntf-broadcast =
    .message = { $content }
    .text-too-long = ❌ تعداد کاراکتر زیاد است ({ $max_limit }).
    .list-empty = ❌ <i>پیامی نیست.</i>
    .plans-unavailable = ❌ <i>طرحی نیست.</i>
    .audience-unavailable = ❌ <i>کاربری برای این گروه پیدا نشد.</i>
    .content-empty = ❌ <i>متن خالی است.</i>
    .content-saved = ✅ <i>متن با موفقیت ذخیره شد.</i>

    .not-cancelable = ❌ <i>امکان لغو نیست.</i>
    .canceled = ✅ <i>با موفقیت لغو شد.</i>
    .deleting = ⚠️ <i>در حال حذف پیام‌ها...</i>
    .already-deleted = ❌ <i>قبلاً حذف شده یا در حال حذف است.</i>

    .deleted-success =
        ✅ پیام <code>{ $task_id }</code> حذف شد.

        <blockquote>
        • <b>کل پیام‌ها</b>: { $total_count }
        • <b>حذف شده</b>: { $deleted_count }
        • <b>نشده</b>: { $failed_count }
        </blockquote>

ntf-importer =
    .not-file = ⚠️ <i>فایل دیتابیس را بفرستید.</i>
    .db-failed = ❌ <i>خطا در صادر کردن کاربرها.</i>
    .users-empty = ❌ <i>کاربری در دیتابیس نیست.</i>

    .started = ✅ <i>شروع شد! منتظر بمانید...</i>
    .already-running = ⚠️ <i>در حال انجام است. لطفاً صبر کنید.</i>

ntf-sync =
    .started = ✅ <i>شروع شد! منتظر بمانید...</i>
    .users-not-found = ❌ <i>کاربری برای همگام‌سازی پیدا نشد.</i>
    .already-running = ⚠️ <i>در حال انجام است. لطفاً صبر کنید.</i>

ntf-menu-editor =
    .button-saved = ✅ <i>دکمه با موفقیت ذخیره شد.</i>
    .invalid-payload = ❌ <i>فرمت URL معتبر نیست.</i>

ntf-devices =
    .deleted = ✅ <i>دستگاه حذف شد.</i>
    .all-deleted = ✅ <i>همه دستگاه‌ها حذف شدند.</i>
    .reissued = ✅ <i>اشتراک با موفقیت عوض شد.</i>