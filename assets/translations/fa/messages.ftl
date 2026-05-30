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
    • اعتبار تمام شده.
    
    <i>{ $is_trial ->
    [0] اشتراک شما تمام شده. تمدید کنید تا ادامه دهید!
    [1] دوره رایگان تمام شده. برای ادامه اشتراک بگیرید!
    }</i>
    </blockquote>
    [LIMITED]
    <blockquote>
    • ترافیک شما تمام شده.

    <i>{ $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] برای ریست کردن ترافیک و ادامه، اشتراک را تمدید کنید!
        *[RESET] ترافیک بعد از { $reset_time } ریست می‌شود. می‌توانید تمدید کنید.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] برای ادامه، اشتراک بگیرید!
        *[RESET] ترافیک بعد از { $reset_time } ریست می‌شود. می‌توانید بگیرید.
        }
    }</i>
    </blockquote>
    [DISABLED]
    <blockquote>
    • اشتراک شما غیرفعال شده.

    <i>برای علت با پشتیبانی تماس بگیرید!</i>
    </blockquote>
    *[NONE]
    <blockquote>
    • اشتراکی ندارید.

    <i>{ $trial_available ->
    [1] 🎁 برای شما تست رایگان هست — پایین بزنید بگیرید.
    *[0] ↘️ برای خرید، به «اشتراک» بروید.
    }</i>
    </blockquote>
    }

msg-menu-devices =
    <b>📱 مدیریت دستگاه‌ها</b>

    اتصال: <b>{ $current_count } / { $max_count }</b>

    { $has_devices ->
    [0] { empty }
    *[HAS] روی دستگاه بزنید تا حذف شود.
    اگه دستگاه کم دارید — اشتراک را عوض کنید.
    }

msg-menu-devices-confirm-reissue =
    🔄 <b>صدور مجدد اشتراک</b>

    ⚠️ بعد از ریست، لینک قدیمی <b>کار نمی‌کند</b>.

    باید:
    • اشتراک قدیمی را از برنامه حذف کنید
    • لینک جدید را از بخش «اتصال» بگیرید

    مطمئنید می‌خواهید ریست کنید?

msg-menu-devices-confirm-delete =
    🗑 حذف <b>{ $selected_device_label }</b>?

msg-menu-devices-confirm-delete-all =
    🗑 حذف <b>همه</b>?

msg-menu-invite =
    <b>👥 دعوت از دوستان</b>
    
    لینک خودتان را به اشتراک بگذارید و جایزه بگیرید به صورت { $reward_type ->
        [POINTS] <b>امتیاز که می‌توانید به اشتراک یا پول واقعی تبدیل کنید</b>
        [EXTRA_DAYS] <b>روز رایگان به اشتراک خودتان</b>
        *[OTHER] { $reward_type }
    }!

    <b>📊 آمار:</b>
    <blockquote>
    👥 کل دعوت‌شده‌ها: { $referrals }
    💳 پرداخت‌ها از لینک شما: { $payments }
    { $reward_type -> 
    [POINTS] 💎 امتیازهای شما: { $points }
    *[EXTRA_DAYS] { empty }
    }
    </blockquote>

msg-menu-invite-about =
    <b>🎁 جزئیات جایزه</b>

    <b>✨ چطور جایزه بگیرید:</b>
    <blockquote>
    { $accrual_strategy ->
    [ON_FIRST_PAYMENT] جایزه برای اولین خرید اشتراک توسط کاربر دعوت‌شده محاسبه می‌شود.
    [ON_EACH_PAYMENT] جایزه برای هر خرید یا تمدید توسط کاربر دعوت‌شده محاسبه می‌شود.
    *[OTHER] { $accrual_strategy }
    }
    </blockquote>

    <b>💎 چه چیزی می‌گیرید:</b>
    <blockquote>
    { $max_level -> 
    [1] برای دوستان دعوت‌شده: { $reward_level_1 }
    *[MORE]
    { $identical_reward ->
    [0]
    1️⃣ برای دوستان شما: { $reward_level_1 }
    2️⃣ برای دوستان آن‌ها: { $reward_level_2 }
    *[1]
    برای همه: { $reward_level_1 }
    }
    }
    
    { $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }
        [EXTRA_DAYS] <i>(همه روزهای اضافه به اشتراک فعلی شما اضافه می‌شود)</i>
        *[OTHER] { $reward_type }
    }
    [PERCENT] { $reward_type ->
        [POINTS] <i>(درصد امتیاز از هزینه اشتراک خریداری‌شده)</i>
        [EXTRA_DAYS] <i>(درصد روز اضافه از اشتراک خریداری‌شده)</i>
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    </blockquote>

msg-invite-reward = { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value -> 
            [one] امتیاز
            [few] امتیاز
            *[more] امتیاز 
            }
        [EXTRA_DAYS] { space }روز اضافه { $value -> 
            [one] روز
            [few] روز
            [more] روز
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] امتیاز
        [EXTRA_DAYS] روز اضافه
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }


# Dashboard
msg-dashboard-main = <b>🛠 پنل مدیریت</b>
msg-users-main = <b>👥 کاربران</b>
msg-broadcast-main = <b>📢 پیام همگانی</b>
msg-statistics-main = <b>📊 آمار</b>


# Subscription
msg-subscription-main = <b>💳 اشتراک</b>
msg-subscription-plans = <b>📦 انتخاب طرح</b>
msg-subscription-new-success = دکمه <code>`{ btn-subscription.connect }`</code> را بزنید و دستورالعمل‌ها را دنبال کنید!
msg-subscription-renew-success = اشتراک شما تمدید شد به مدت { $added_duration }.

msg-subscription-plan = 
    <b>📦 طرح موجود از لینک</b>
    
    طرح <b>{ $name }</b> از لینک برای شما موجود است. پایین بزنید تا مدت و روش پرداخت را انتخاب کنید.

    { $description ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $description }
    </blockquote>
    }

    { $purchase_type ->
    [RENEW] <i>⚠️ اشتراک فعلی <u>تمدید</u> می‌شود.</i>
    [CHANGE] <i>⚠️ اشتراک فعلی با این طرح <u>عوض</u> می‌شود.</i>
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

    • <b>ترافیک</b>: { $traffic }
    • <b>دستگاه</b>: { $devices }
    { $period ->
    [0] { empty }
    *[HAS] • <b>مدت</b>: { $period }
    }
    { $final_amount ->
    [0] { empty }
    *[HAS] • <b>قیمت</b>: { frg-payment-amount }
    }
    </blockquote>
    
    <blockquote>
    { $discount_percent ->
    [0] { empty }
    *[HAS] <i>شامل { $is_personal_discount ->
        [1] تخفیف شخصی { $discount_percent }%
        *[0] تخفیف { $discount_percent }%
        }
        </i>
    }
    </blockquote>

msg-subscription-duration = 
    <b>⏳ انتخاب مدت</b>

    { msg-subscription-details }

msg-subscription-payment-method =
    <b>💳 انتخاب روش پرداخت</b>

    { msg-subscription-details }

msg-subscription-confirm =
    <b>🛒 تأیید { $purchase_type ->
    [RENEW] تمدید
    [CHANGE] تغییر
    *[OTHER] خرید
    } اشتراک</b>

    { msg-subscription-details }

    { $purchase_type ->
    [RENEW] <i>⚠️ اشتراک فعلی <u>تمدید</u> می‌شود.</i>
    [CHANGE] <i>⚠️ اشتراک فعلی <u>عوض</u> می‌شود.</i>
    *[OTHER] { empty }
    }

msg-manual-transfer-receipt =
    <b>🏦 اطلاعات پرداخت</b>

    { msg-subscription-details }

    <b>شماره کارت:</b>
    { $bank_info.bank_name ->
        *[not_empty] • بانک: { $bank_info.bank_name }
    }
    { $bank_info.account_holder ->
        *[not_empty] • صاحب: { $bank_info.account_holder }
    }
    { $bank_info.account_number ->
        *[not_empty] • حساب: { $bank_info.account_number }
    }
    { $bank_info.card_number ->
        *[not_empty] • کارت: { $bank_info.card_number }
    }

    <i>📎 عکس یا اسکرین‌شات پرداخت را بفرستید.</i>

msg-subscription-trial =
    <b>✅ تست رایگان گرفتید!</b>

    { msg-subscription-new-success }

msg-subscription-success =
    <b>✅ پرداخت موفق!</b>

msg-subscription-failed =
    ❌ <b>خطایی رخ داد!</b>

    نگران نباشید، پشتیبانی مطلع شده و به زودی با شما تماس می‌گیرد.