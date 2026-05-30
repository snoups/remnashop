space = {" "}
empty = { "!empty!" }
btn-test = دکمه
msg-test = پیام
development = در حال توسعه!
test-payment = پرداخت آزمایشی
unknown = —

development-promocodes = کدهای تخفیف هنوز پیاده‌سازی نشده‌اند، برای تشویق و تسریع توسعه می‌توانید کمک کنید.

payment-invoice-description = { $purchase-type } اشتراک { $name } به مدت { $duration }

inline-invite =
    .title = دعوت از دوستان
    .description = برای ارسال لینک دعوت کلیک کنید!
    .message =
        🚀 سلام! می‌خواهید VPN پایدار و سریع داشته باشید؟

        { $bot_name } - به شما کمک می‌کند!

        ↘️ روی دکمه کلیک کنید و رایگان امتحان کنید!
    .start = 🚀 پیوستن

message =
    .withdraw-points = سلام! می‌خواستم درخواست تبادل امتیاز کنم.
    .paysupport = سلام! می‌خواستم درخواست بازگشت وجه کنم.
    .help = سلام! به کمک نیاز دارم.

command =
    .start = راه‌اندازی مجدد ربات
    .paysupport = بازگشت وجه
    .rules = شرایط استفاده
    .help = راهنما

hdr-user = <b>👤 کاربر:</b>
hdr-user-profile = <b>👤 پروفایل:</b>
hdr-payment = <b>💰 پرداخت:</b>
hdr-error = <b>⚠️ خطا:</b>
hdr-node = <b>🖥 نود:</b>
hdr-hwid = <b>📱 دستگاه:</b>

hdr-subscription = { $is_trial ->
    [1] <b>🎁 اشتراک آزمایشی:</b>
    *[0] <b>💳 اشتراک:</b>
}

hdr-plan = { $is_trial_plan ->
    [1] <b>🎁 طرح آزمایشی:</b>
    *[0] <b>📦 طرح:</b>
}

frg-user =
    <blockquote>
    • <b>شناسه</b>: <code>{ NUMBER($telegram_id, useGrouping: 0) }</code>
    • <b>نام</b>: { $name }
    { $show_personal_discount ->
    [1] • <b>تخفیف شخصی</b>: { $personal_discount }%
    *[0] { empty }
    }
    { $show_purchase_discount ->
    [1] • <b>تخفیف خرید</b>: { $purchase_discount }%
    *[0] { empty }
    }
    </blockquote>

frg-user-info =
    <blockquote>
    • <b>شناسه</b>: <code>{ NUMBER($telegram_id, useGrouping: 0) }</code> 
    • <b>نام</b>: { $name } { $username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $telegram_id }">@{ $username }</a>)
    }
    </blockquote>

frg-user-details =
    <blockquote>
    • <b>شناسه</b>: <code>{ NUMBER($telegram_id, useGrouping: 0) }</code>
    • <b>نام</b>: { $name } { $username -> 
        [0] { space }
        *[HAS] (<a href="tg://user?id={ $telegram_id }">@{ $username }</a>)
    }
    • <b>نقش</b>: { role }
    • <b>زبان</b>: { language }
    • <b>ربات مسدود شده</b>: { $is_bot_blocked ->
        [1] بله
        *[0] خیر
    }
    { $show_points ->
    [1] • <b>امتیاز</b>: { $points }
    *[0] { empty }
    }
    </blockquote>

frg-user-discounts-details =
    <blockquote>
    • <b>شخصی</b>: { $personal_discount }%
    • <b>خرید بعدی</b>: { $purchase_discount }%
    </blockquote>

frg-subscription =
    <blockquote>
    • <b>محدودیت ترافیک</b>: { $traffic_limit }
    • <b>محدودیت دستگاه</b>: { $device_limit }
    • <b>مانده</b>: { $expire_time }
    </blockquote>

frg-subscription-details =
    <blockquote>
    • <b>شناسه</b>: <code>{ $subscription_id }</code>
    • <b>وضعیت</b>: { subscription-status }
    • <b>ترافیک</b>: { $traffic_used } / { $traffic_limit }
    • <b>محدودیت دستگاه</b>: { $device_limit }
    • <b>مانده</b>: { $expire_time }
    </blockquote>

frg-payment-info =
    <blockquote>
    • <b>شناسه</b>: <code>{ $payment_id }</code>
    • <b>روش پرداخت</b>: { gateway-type }
    • <b>مبلغ</b>: { frg-payment-amount }
    </blockquote>

frg-payment-amount = { $final_amount }{ $currency } { $discount_percent -> 
    [0] { space }
    *[more] { space } <strike>{ $original_amount }{ $currency }</strike> (-{ $discount_percent }%)
    }

frg-plan-snapshot =
    <blockquote>
    • <b>طرح</b>: <code>{ $plan_name }</code>
    • <b>نوع</b>: { plan-type } 
    • <b>محدودیت ترافیک</b>: { $plan_traffic_limit }
    • <b>محدودیت دستگاه</b>: { $plan_device_limit }
    • <b>مدت</b>: { $plan_duration }
    </blockquote>

frg-plan-snapshot-comparison =
    <blockquote>
    • <b>طرح</b>: <code>{ $previous_plan_name }</code> -> <code>{ $plan_name }</code>
    • <b>نوع</b>: { $previous_plan_type } -> { plan-type }
    • <b>محدودیت ترافیک</b>: { $previous_plan_traffic_limit } -> { $plan_traffic_limit }
    • <b>محدودیت دستگاه</b>: { $previous_plan_device_limit } -> { $plan_device_limit }
    • <b>مدت</b>: { $previous_plan_duration } -> { $plan_duration }
    </blockquote>

frg-node-info =
    <blockquote>
    • <b>نام</b>: { $country } { $name }
    • <b>آدرس</b>: <code>{ $address }{ $port ->
        [0] { space }
        *[HAS] :{ $port }</code>
    }
    • <b>ترافیک</b>: { $traffic_used } / { $traffic_limit }
    { $last_status_message -> 
    [0] { empty }
    *[HAS] • <b>آخرین وضعیت</b>: { $last_status_message }
    }
    { $last_status_change -> 
    [0] { empty }
    *[HAS] • <b>تغییر وضعیت</b>: { $last_status_change }
    }
    </blockquote>

frg-user-hwid =
    <blockquote>
    • <b>HWID</b>: <code>{ $hwid }</code>
    { $platform ->
    [0] { space }
    *[HAS] • <b>پلتفرم</b>: { $platform }
    }
    { $device_model ->
    [0] { space }
    *[HAS] • <b>مدل</b>: { $device_model }
    }
    { $os_version ->
    [0] { space }
    *[HAS] • <b>نسخه</b>: { $os_version }
    }
    { $user_agent ->
    [0] { space }
    *[HAS] • <b>عامل</b>: { $user_agent }
    }
    </blockquote>

frg-build-info =
    { $has_build ->
    [0] { space }
    *[HAS]
    <b>🏗️ اطلاعات ساخت:</b>
    <blockquote>
    زمان ساخت: { $time }
    شاخه: { $branch } ({ $tag })
    کامیت: <a href="{ $commit_url }">{ $commit }</a>
    </blockquote>
    }

role-owner = مالک
role-dev = توسعه‌دهنده
role-admin = مدیر
role-preview = پیش‌نمایش
role-user = کاربر
role = 
    { $role ->
    [5] { role-owner }
    [4] { role-dev }
    [3] { role-admin }
    [2] { role-preview }
    *[1] { role-user }
}

unlimited = ∞

unit-unlimited = { $value ->
    [0] { unlimited }
    *[other] { $value }
}

unit-device = { $value -> 
    [0] { unlimited }
    *[other] { $value } 
} { $value ->
    [0] { space }
    [one] دستگاه
    [few] دستگاه
    *[other] دستگاه
}

unit-byte = { $value } B
unit-kilobyte = { $value } KB
unit-megabyte = { $value } MB
unit-gigabyte = { $value } GB
unit-terabyte = { $value } TB

unit-second = { $value } { $value ->
    [one] ثانیه
    [few] ثانیه
    *[other] ثانیه
}

unit-minute = { $value } { $value ->
    [one] دقیقه
    [few] دقیقه
    *[other] دقیقه
}

unit-hour = { $value } { $value ->
    [one] ساعت
    [few] ساعت
    *[other] ساعت
}

unit-day = { $value } { $value ->
    [one] روز
    [few] روز
    *[other] روز
}

unit-month = { $value } { $value ->
    [one] ماه
    [few] ماه
    *[other] ماه
}

unit-year = { $value } { $value ->
    [one] سال
    [few] سال
    *[other] سال
}


plan-type = { $plan_type -> 
    [TRAFFIC] ترافیک
    [DEVICES] دستگاه
    [BOTH] ترافیک + دستگاه
    [UNLIMITED] نامحدود
    *[OTHER] { $plan_type }
}

promocode-type = { $promocode_type -> 
    [DURATION] مدت
    [TRAFFIC] ترافیک
    [DEVICES] دستگاه
    [SUBSCRIPTION] اشتراک
    [PERSONAL_DISCOUNT] تخفیف شخصی
    [PURCHASE_DISCOUNT] تخفیف خرید
    *[OTHER] { $promocode_type }
}

availability-type = { $availability_type -> 
    [ALL] برای همه
    [NEW] برای جدیدها
    [EXISTING] برای موجودها
    [INVITED] برای دعوت‌شدگان
    [ALLOWED] برای مجازها
    [LINK] با لینک
    *[OTHER] { $availability_type }
}

gateway-type = { $gateway_type ->
    [TELEGRAM_STARS] Telegram Stars
    [YOOKASSA] YooKassa
    [YOOMONEY] YooMoney
    [CRYPTOMUS] Cryptomus
    [HELEKET] Heleket
    [CRYPTOPAY] CryptoPay
    [FREEKASSA] FreeKassa
    [MULENPAY] MulenPay
    [PAYMASTER] PayMaster
    [PLATEGA] Platega
    [ROBOKASSA] RoboKassa
    [URLPAY] UrlPay
    [WATA] WATA
    [MANUAL_TRANSFER] انتقال بانکی
    *[OTHER] { $gateway_type }
}

access-mode = { $access_mode ->
    [PUBLIC] 🟢 مجاز برای همه
    [INVITED] 🟡 مجاز برای دعوت‌شدگان
    [RESTRICTED] 🔴 محدود برای همه
    *[OTHER] { $access_mode }
}

audience-type = { $audience_type ->
    [ALL] همه
    [PLAN] بر اساس طرح
    [SUBSCRIBED] با اشتراک
    [UNSUBSCRIBED] بدون اشتراک
    [EXPIRED] منقضی
    [TRIAL] با آزمایشی
    *[OTHER] { $audience_type }
}

broadcast-status = { $broadcast_status ->
    [PROCESSING] در حال انجام
    [COMPLETED] تکمیل شده
    [CANCELED] لغو شده
    [DELETED] حذف شده
    [ERROR] خطا
    *[OTHER] { $broadcast_status }
}

transaction-status = { $transaction_status ->
    [PENDING] در انتظار
    [COMPLETED] تکمیل شده
    [CANCELED] لغو شده
    [REFUNDED] بازگشت داده شده
    [FAILED] ناموفق
    *[OTHER] { $transaction_status }
}

subscription-status = { $subscription_status ->
    [ACTIVE] فعال
    [DISABLED] غیرفعال
    [LIMITED] ترافیک تمام شده
    [EXPIRED] منقضی شده
    [DELETED] حذف شده
    *[OTHER] { $subscription_status }
}

purchase-type = { $purchase_type ->
    [NEW] خرید
    [RENEW] تمدید
    [CHANGE] تغییر
    *[OTHER] { $purchase_type }
}

traffic-strategy = { $strategy_type -> 
    [NO_RESET] هنگام پرداخت
    [DAY] هر روز
    [WEEK] هر هفته
    [MONTH] هر ماه
    [MONTH_ROLLING] هر ماه (بر اساس تاریخ ایجاد)
    *[OTHER] { $strategy_type }
    }

reward-type = { $reward_type -> 
    [POINTS] امتیاز
    [EXTRA_DAYS] روز
    *[OTHER] { $reward_type }
    }

accrual-strategy = { $accrual_strategy_type -> 
    [ON_FIRST_PAYMENT] اولین پرداخت
    [ON_EACH_PAYMENT] هر پرداخت
    *[OTHER] { $accrual_strategy_type }
    }

reward-strategy = { $reward_strategy_type -> 
    [AMOUNT] ثابت
    [PERCENT] درصدی
    *[OTHER] { $reward_strategy_type }
    }

button-type = { $button_type ->
    [URL] باز کردن لینک
    [COPY] کپی کردن متن
    [WEB_APP] باز کردن وب‌اپ
    *[OTHER] { $button_type }
}

language = { $language ->
    [ar] عربی
    [az] آذربایجانی
    [be] بلاروسی
    [cs] چکی
    [de] آلمانی
    [en] انگلیسی
    [es] اسپانیایی
    [fa] فارسی
    [fr] فرانسوی
    [he] عبری
    [hi] هندی
    [id] اندونزیایی
    [it] ایتالیایی
    [ja] ژاپنی
    [kk] قزاق
    [ko] کره‌ای
    [ms] مالایی
    [nl] هلندی
    [pl] لهستانی
    [pt] پرتغالی
    [ro] رومانیایی
    [ru] روسی
    [sr] صربستانی
    [tr] ترکی
    [uk] اوکراینی
    [uz] ازبک
    [vi] ویتنامی
    *[OTHER] { $language }
}