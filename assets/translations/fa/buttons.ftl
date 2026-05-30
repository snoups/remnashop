btn-back = 
    .general = ⬅️ بازگشت
    .menu = ↩️ منوی اصلی
    .menu-return = ↩️ بازگشت به منوی اصلی
    .dashboard = ↩️ بازگشت به پنل مدیریت

btn-common =
    .notification-close = ❌ بستن
    .devices-empty = ⚠️ دستگاه متصلی ندارید
    .cancel = لغو

    .squad-choice = { $selected -> 
    [1] 🔘
    *[0] ⚪
    } { $name }

    .duration = ⌛ { $value ->
    [0] { unlimited }
    *[other] { unit-day }
    }

btn-devices =
    .delete-all = 🗑 حذف همه دستگاه‌ها
    .reissue = 🔄 صدور مجدد اشتراک
    .confirm-delete = ✅ بله، حذف شود
    .confirm-reissue = ✅ بله، بازنشانی شود
    .cancel-reissue = ❌ خیر

btn-remnashop-info =
    .release-latest = 👀 مشاهده
    .how-upgrade = ❓ نحوه به‌روزرسانی
    .github = ⭐ GitHub
    .telegram = 👪 تلگرام
    .donate = 💰 حمایت از توسعه‌دهنده
    .guide = ❓ راهنما

btn-requirement =
    .rules-accept = ✅ پذیرش قوانین
    .channel-join = ❤️ پیوستن به کانال
    .channel-confirm = ✅ تأیید

btn-menu =
    .trial = 🎁 رایگان امتحان کنید
    .connect = 🚀 اتصال
    .devices = 📱 دستگاه‌ها
    .subscription = 💳 اشتراک
    .invite = 👥 دعوت
    .support = 🆘 پشتیبانی
    .dashboard = 🛠 پنل مدیریت

    .connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] ترافیک شما تمام شده
    [EXPIRED] اشتراک شما منقضی شده
    *[OTHER] اشتراک شما فعال نیست
    } ⚠️

btn-invite =
    .about = ❓ درباره جایزه
    .copy = 📋 کپی لینک
    .send = 📩 دعوت
    .qr = 🧾 QR کد
    .withdraw-points = 💎 تبدیل امتیاز

btn-dashboard =
    .statistics = 📊 آمار
    .users = 👥 کاربران
    .broadcast = 📢 پیام همگانی
    .promocodes = 🎟 کدهای تخفیف
    .access = 🔓 دسترسی
    .remnawave = 🌊 رمناویو
    .remnashop = 🛠 رمناشاپ
    .importer = 📥 ورود کاربران

btn-statistics =
    .users = 👥 کاربران
    .subscriptions = 💳 اشتراک‌ها
    .transactions = 🧾 تراکنش‌ها
    .promocodes = 🎟 کدهای تخفیف
    .referrals = 👪 معرف‌ها

    .subscription-page =
    { $page ->
        [0] { $is_current ->
            [1] [ آمار کلی ]
            *[0] آمار کلی
        }
        *[other] { $is_current ->
            [1] [ { $plan_name } ]
            *[0] { $plan_name }
        }
    }

    .transaction-page =
    { $page ->
        [0] { $is_current ->
            [1] [ آمار کلی ]
            *[0] آمار کلی
        }
        *[other] { $is_current ->
            [1] [ { gateway-type } ]
            *[0] { gateway-type }
        }
    }

btn-users =
    .search = 🔍 جستجوی کاربر
    .recent-registered = 🆕 تازه ثبت‌نام کرده‌ها
    .recent-activity = 📝 تازه فعالیت داشته‌ها
    .blacklist = 🚫 لیست سیاه
    .unblock-all = 🔓 رفع مسدودی همه

btn-user =
    .discount = 💸 تخفیف
    .discount-personal = 👤 تخفیف شخصی
    .discount-purchase = 🎟 تخفیف خرید بعدی
    .points = 💎 امتیاز
    .statistics = 📊 آمار
    .referrals = 👪 معرف‌ها
    .message = 📩 پیام
    .role = 👮‍♂️ نقش
    .transactions = 🧾 تراکنش‌ها
    .give-access = 🔑 دسترسی به طرح‌ها
    .current-subscription = 💳 اشتراک فعلی
    .subscription-traffic-limit = 🌐 محدودیت ترافیک
    .subscription-device-limit = 📱 محدودیت دستگاه
    .subscription-expire-time = ⏳ زمان انقضا
    .subscription-squads = 🔗 اسکوادها
    .subscription-traffic-reset = 🔄 ریست ترافیک
    .subscription-devices = 🧾 لیست دستگاه‌ها
    .subscription-url = 📋 کپی لینک
    .subscription-set = ✅ فعال‌سازی اشتراک
    .subscription-delete = ❌ حذف
    .message-preview = 👀 پیش‌نمایش
    .message-confirm = ✅ ارسال
    .sync = 🌀 همگام‌سازی
    .sync-remnawave = 🌊 استفاده از داده رمناویو
    .sync-remnashop = 🛠 استفاده از داده رمناشاپ
    .give-subscription = 🎁 دادن اشتراک
    .subscription-internal-squads = ⏺️ اسکوادهای داخلی
    .subscription-external-squads = ⏹️ اسکواد خارجی

    .allowed-plan-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $plan_name }

    .subscription-active-toggle = { $is_active ->
    [1] 🔴 غیرفعال
    *[0] 🟢 فعال
    }

    .transaction = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [CANCELED] ❌
    [REFUNDED] 💸
    [FAILED] ⚠️
    *[OTHER] { $status }
    } { $created_at }
    
    .trial-toggle = { $is_trial_available ->
    [1] 🧪 تست: فعال
    *[0] 🧪 تست: غیرفعال
    }

    .block = { $is_blocked ->
    [1] 🔓 رفع مسدودی
    *[0] 🔒 مسدود
    }

btn-broadcast =
    .list = 📄 همه پیام‌ها
    .all = 👥 همه
    .plan = 📦 بر اساس طرح
    .subscribed = ✅ دارای اشتراک
    .unsubscribed = ❌ بدون اشتراک
    .expired = ⌛ منقضی
    .trial = ✳️ دارای تست
    .content = ✉️ ویرایش متن
    .buttons = ✳️ ویرایش دکمه‌ها
    .preview = 👀 پیش‌نمایش
    .confirm = ✅ شروع ارسال
    .refresh = 🔄 به‌روزرسانی
    .viewing = 👀 مشاهده
    .cancel = ⛔ توقف
    .delete = ❌ حذف

    .plan-title = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }
    
    .button-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    }
    
    .title = { $status ->
    [PROCESSING] ⏳
    [COMPLETED] ✅
    [CANCELED] ⛔
    [DELETED] ❌
    [ERROR] ⚠️
    *[OTHER] { $status }
    } { $created_at }
    
btn-goto =
    .subscription = 💳 خرید اشتراک
    .promocode = 🎟 فعال کردن کد تخفیف
    .invite = 👥 دعوت
    .subscription-renew = 🔄 تمدید اشتراک
    .user-profile = 👤 رفتن به پروفایل کاربر
    .referrer-profile = 🤝 رفتن به معرف
    .contact-support = 📩 رفتن به پشتیبانی

btn-promocodes =
    .list = 📃 لیست کدها
    .search = 🔍 جستجوی کد
    .create = 🆕 ایجاد
    .delete = 🗑️ حذف
    .edit = ✏️ ویرایش

btn-access =
    .mode = { access-mode }
    .conditions = ⚙️ شرایط
    .rules = ✳️ پذیرش قوانین
    .channel = ❇️ عضویت کانال

    .payments-toggle = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } پرداخت‌ها

    .registration-toggle = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } ثبت‌نام

    .condition-toggle = { $enabled ->
    [1] 🔘 فعال
    *[0] ⚪ غیرفعال
    }

btn-remnashop =
    .admins = 👮‍♂️ مدیران
    .gateways = 🌐 درگاه‌های پرداخت
    .referral = 👥 سیستم معرفی
    .advertising = 🎯 تبلیغات
    .plans = 📦 طرح‌ها
    .notifications = 🔔 اعلان‌ها
    .logs = 📄 لاگ‌ها
    .menu-editor = 🎛 دکمه‌های اضافی

btn-menu-editor =
    .text = 🏷️ متن
    .availability = ✴️ دسترسی
    .type = 🔖 نوع
    .payload = 📄 داده
    .confirm = ✅ ذخیره

    .button = { $is_active -> 
        [1] 🟢 
        *[0] 🔴 
    } { $text }
    
    .active = { $is_active -> 
        [1] 🟢 فعال
        *[0] 🔴 غیرفعال
    }
    
btn-gateway =
    .title = { gateway-type }
    .setting = { $field }
    .webhook-copy = 📋 کپی وب‌هوک
    .test = 🐞 تست
    .default-currency = 💸 ارز پیش‌فرض
    .placement = 🔢 تغییر جایگاه

    .active = { $is_active ->
    [1] 🟢 فعال
    *[0] 🔴 غیرفعال
    }

    .default-currency-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $symbol } { $currency }

btn-referral =
    .level = 🔢 سطح
    .reward-type = 🎀 نوع جایزه
    .accrual-strategy = 📍 شرط
    .reward-strategy = ⚖️ فرمول
    .reward = 🎁 جایزه
    
    .enable = { $is_enable -> 
    [1] 🟢 فعال
    *[0] 🔴 غیرفعال
    }

    .level-choice = { $type -> 
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $type }
    }

    .reward-choice = { $type -> 
    [POINTS] 💎 امتیاز
    [EXTRA_DAYS] ⏳ روز
    *[OTHER] { $type }
    }

    .accrual-strategy-choice = { $type -> 
    [ON_FIRST_PAYMENT] 💳 اولین پرداخت
    [ON_EACH_PAYMENT] 💸 هر پرداخت
    *[OTHER] { $type }
    }

    .reward-strategy-choice = { $type -> 
    [AMOUNT] 🔸 ثابت
    [PERCENT] 🔹 درصدی
    *[OTHER] { $type }
    }

btn-notifications =
    .user = 👥 کاربری
    .system = ⚙️ سیستمی
    
    .user-choice = { $enabled ->
    [1] 🔘
    [0] ⚪
    } { $type ->
    [EXPIRES_IN_3_DAYS] اشتراک ۳ روز دیگه تموم میشه
    [EXPIRES_IN_2_DAYS] اشتراک ۲ روز دیگه تموم میشه
    [EXPIRES_IN_1_DAY] اشتراک فردا تموم میشه
    [EXPIRED] اشتراک تموم شده
    [EXPIRED_1_DAY_AGO] دیروز تموم شده
    [LIMITED] ترافیک تموم شده
    [REFERRAL_ATTACHED] معرف اومده
    [REFERRAL_REWARD_RECEIVED] جایزه گرفتی
    *[OTHER] { $type }
    }

    .system-choice = { $enabled -> 
    [1] 🔘
    [0] ⚪
    } { $type ->
    [BOT_LIFECYCLE] روشن/خاموش شدن ربات
    [BOT_UPDATE] آپدیت ربات
    [USER_REGISTERED] ثبت‌نام
    [SUBSCRIPTION] خرید اشتراک
    [PROMOCODE_ACTIVATED] کد تخفیف
    [TRIAL_ACTIVATED] تست رایگان
    [NODE_STATUS_CHANGED] تغییر وضعیت نود
    [NODE_TRAFFIC_REACHED] ترافیک نود
    [USER_FIRST_CONNECTION] اولین اتصال
    [USER_DEVICES_UPDATED] تغییر دستگاه‌ها
    [USER_REVOKED_SUBSCRIPTION] لغو اشتراک
    *[OTHER] { $type }
    }

btn-plans =
    .statistics = 📊 آمار
    .create = 🆕 ایجاد
    .save = ✅ ذخیره
    .create = ✅ ایجاد طرح
    .delete = ❌ حذف
    .name = 🏷️ نام
    .description = 💬 توضیحات
    .description-remove = ❌ حذف توضیحات
    .tag = 📌 برچسب
    .tag-remove = ❌ حذف برچسب
    .type = 🔖 نوع
    .availability = ✴️ دسترسی
    .durations-prices = ⏳ مدت و قیمت
    .traffic = 🌐 ترافیک
    .devices = 📱 دستگاه
    .allowed = 👥 کاربران مجاز
    .squads = 🔗 اسکوادها
    .internal-squads = ⏺️ اسکواد داخلی
    .external-squads = ⏹️ اسکواد خارجی
    .allowed-user = { $id }
    .duration-add = 🆕 اضافه کردن مدت
    .price-choice = 💸 { $price } { $currency }
    .export = 📤 صادر
    .import = 📥 وارد
    .exporting = 📤 صادر کردن
    .importing = 📥 وارد کردن
    .url = 📋 کپی لینک

    .trial = { $is_trial ->
    [1] 🔘
    *[0] ⚪
    } تست رایگان

    .export-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $name }

    .title = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }

    .active = { $is_active -> 
    [1] 🟢 فعال
    *[0] 🔴 غیرفعال
    }
    
    .type-choice = { $type -> 
    [TRAFFIC] 🌐 ترافیک
    [DEVICES] 📱 دستگاه
    [BOTH] 🔗 ترافیک + دستگاه
    [UNLIMITED] ♾️ نامحدود
    *[OTHER] { $type }
    }

    .availability-choice = { $type -> 
    [ALL] 🌍 برای همه
    [NEW] 🌱 برای جدیدها
    [EXISTING] 👥 برای مشتریان
    [INVITED] ✉️ برای دعوت‌شده‌ها
    [ALLOWED] 🔐 برای مجازها
    [LINK] 🔗 از طریق لینک
    *[OTHER] { $type }
    }

    .traffic-strategy-choice = { $selected ->
    [1] 🔘 { traffic-strategy }
    *[0] ⚪ { traffic-strategy }
    }

    
btn-remnawave =
    .users = 👥 کاربران
    .hosts = 🌐 هاست‌ها
    .nodes = 🖥️ نودها
    .inbounds = 🔌 اینباندها

btn-importer =
    .from-xui = 💩 ورود از پنل ۳X-UI
    .from-xui-shop = 🛒 ربات ۳xui-shop
    .sync = 🌀 شروع همگام‌سازی
    .squads = 🔗 اسکوادهای داخلی
    .import-all = ✅ ورود همه
    .import-active = ❇️ ورود فعال‌ها

btn-subscription =
    .plan = 💳 رفتن به خرید اشتراک
    .new = 💸 خرید اشتراک
    .renew = 🔄 تمدید
    .change = 🔃 تغییر
    .promocode = 🎟 فعال کردن کد تخفیف
    .payment-method = { gateway-type } | { $final_amount ->
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }
    .pay = 💳 پرداخت
    .get = 🎁 رایگان بگیرید
    .back-plans = ⬅️ بازگشت به انتخاب طرح
    .back-duration = ⬅️ تغییر مدت
    .back-payment-method = ⬅️ تغییر روش پرداخت
    .connect = 🚀 اتصال

    .duration = { $period } | { $final_amount -> 
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }

btn-promocode =
    .code = 🏷️ کد
    .type = 🔖 نوع جایزه
    .availability = ✴️ دسترسی
    .reward = 🎁 جایزه
    .lifetime = ⌛ زمان اعتبار
    .allowed = 👥 کاربران مجاز
    .confirm = ✅ تأیید
    
    .active = { $is_active -> 
    [1] 🟢
    *[0] 🔴
    } وضعیت