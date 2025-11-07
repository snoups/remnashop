# Layout
space = {" "}
empty = { "!empty!" }
btn-test = Кнопка
msg-test = Сообщение
development = Временно недоступно!
test-payment = Тестовый платеж
unlimited = ∞
unknown = —

unit-unlimited = { $value ->
    [-1] { unlimited }
    [0] { unlimited }
    *[other] { $value }
}

# Other
payment-invoice-description = { purchase-type } подписки { $name } на { $duration }
contact-support = Здравствуйте! Мне нужна помощь.
cmd-start = Перезапустить бота
cmd-help = Помощь


# Headers
hdr-user = <b>👤 Пользователь:</b>
hdr-user-profile = <b>👤 Профиль:</b>

hdr-subscription = { $is_trial ->
    [1] <b>🎁 Пробная подписка:</b>
    *[0] <b>💳 Подписка:</b>
    }

hdr-plan = <b>📦 План:</b>
hdr-payment = <b>💰 Платеж:</b>
hdr-error = <b>⚠️ Ошибка:</b>
hdr-node = <b>🖥 Нода:</b
hdr-hwid = <b>📱 Устройство:</b>

# Fragments
frg-user =
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Имя</b>: { $user_name }
    { $personal_discount ->
    [0] { empty }
    *[HAS] • <b>Ваша скидка</b>: { $personal_discount }%
    }
    </blockquote>

frg-user-info =
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Имя</b>: { $user_name } { $username -> 
        [0] { empty }
        *[HAS] (<a href="tg://user?id={ $user_id }">@{ $username }</a>)
    }
    </blockquote>

frg-user-details =
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Имя</b>: { $user_name } { $username -> 
        [0] { space }
        *[HAS] (<a href="tg://user?id={ $user_id }">@{ $username }</a>)
    }
    • <b>Роль</b>: { role }
    • <b>Язык</b>: { language }
    </blockquote>

frg-user-discounts-details =
    <blockquote>
    • <b>Персональная</b>: { $personal_discount }%
    • <b>На следующую покупку</b>: { $purchase_discount }%
    </blockquote>

frg-subscription =
    <blockquote>
    • <b>Лимит трафика</b>: { $traffic_limit }
    • <b>Лимит устройств</b>: { $device_limit }
    • <b>Осталось</b>: { $expire_time }
    </blockquote>

frg-subscription-details =
    <blockquote>
    • <b>ID</b>: <code>{ $subscription_id }</code>
    • <b>Статус</b>: { subscription-status }
    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    • <b>Лимит устройств</b>: { $device_limit }
    • <b>Осталось</b>: { $expire_time }
    </blockquote>

frg-payment-info =
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Способ оплаты</b>: { gateway-type }
    • <b>Сумма</b>: { frg-payment-amount }
    </blockquote>

frg-payment-amount = { $final_amount }{ $currency } { $discount_percent -> 
    [0] { empty }
    *[more] { space } <strike>{ $original_amount }{ $currency }</strike> (-{ $discount_percent }%)
    }

frg-plan-snapshot =
    <blockquote>
    • <b>План</b>: <code>{ $plan_name }</code>
    • <b>Тип</b>: { plan-type }
    • <b>Лимит трафика</b>: { $plan_traffic_limit }
    • <b>Лимит устройств</b>: { $plan_device_limit }
    • <b>Длительность</b>: { $plan_duration }
    </blockquote>

frg-plan-snapshot-comparison =
    <blockquote>
    • <b>План</b>: <code>{ $previous_plan_name }</code> -> <code>{ $plan_name }</code>
    • <b>Тип</b>: { $previous_plan_type } -> { plan-type }
    • <b>Лимит трафика</b>: { $previous_plan_traffic_limit } -> { $plan_traffic_limit }
    • <b>Лимит устройств</b>: { $previous_plan_device_limit } -> { $plan_device_limit }
    • <b>Длительность</b>: { $previous_plan_duration } -> { $plan_duration }
    </blockquote>

frg-node-info =
    <blockquote>
    • <b>Название</b>: { $country } { $name }
    • <b>Адрес</b>: <code>{ $address }:{ $port }</code>
    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    • <b>Последний статус</b>: { $last_status_message }
    • <b>Статус изменен</b>: { $last_status_change }
    </blockquote>

frg-user-hwid =
    <blockquote>
    • <b>HWID</b>: <code>{ $hwid }</code>

    • <b>Платформа</b>: { $platform }
    • <b>Модель</b>: { $device_model }
    • <b>Версия ОС</b>: { $os_version }
    • <b>Агент</b>: { $user_agent }
    </blockquote>

# Roles
role-dev = Разработчик
role-admin = Администратор
role-user = Пользователь
role = 
    { $role ->
    [DEV] { role-dev }
    [ADMIN] { role-admin }
    *[USER] { role-user }
}


# Units
unit-device = { $value -> 
    [-1] { unlimited }
    *[other] { $value } 
} { $value ->
    [-1] { space }
    [one] устройство
    [few] устройства
    *[other] устройств
}

unit-byte = { $value } Б
unit-kilobyte = { $value } КБ
unit-megabyte = { $value } МБ
unit-gigabyte = { $value } ГБ
unit-terabyte = { $value } ТБ

unit-second = { $value } { $value ->
    [one] секунда
    [few] секунды
    *[other] секунд
}

unit-minute = { $value } { $value ->
    [one] минута
    [few] минуты
    *[other] минут
}

unit-hour = { $value } { $value ->
    [one] час
    [few] часа
    *[other] часов
}

unit-day = { $value } { $value ->
    [one] день
    [few] дня
    *[other] дней
}

unit-month = { $value } { $value ->
    [one] месяц
    [few] месяца
    *[other] месяцев
}

unit-year = { $value } { $value ->
    [one] год
    [few] года
    *[other] лет
}


# Types
plan-type = { $plan_type -> 
    [TRAFFIC] Трафик
    [DEVICES] Устройства
    [BOTH] Трафик + устройства
    [UNLIMITED] Безлимитный
    *[OTHER] { $plan_type }
}

promocode-type = { $promocode_type -> 
    [DURATION] Длительность
    [TRAFFIC] Трафик
    [DEVICES] Устройства
    [SUBSCRIPTION] Подписка
    [PERSONAL_DISCOUNT] Персональная скидка
    [PURCHASE_DISCOUNT] Скидка на покупку
    *[OTHER] { $promocode_type }
}

availability-type = { $availability_type -> 
    [ALL] Для всех
    [NEW] Для новых
    [EXISTING] Для существующих
    [INVITED] Для приглашенных
    [ALLOWED] Для разрешенных
    [TRIAL] Для пробника
    *[OTHER] { $availability_type }
}

gateway-type = { $gateway_type ->
    [TELEGRAM_STARS] Telegram Stars
    [YOOKASSA] ЮKassa
    [YOOMONEY] ЮMoney
    [CRYPTOMUS] Cryptomus
    [HELEKET] Heleket
    [URLPAY] UrlPay
    *[OTHER] { $gateway_type }
}

access-mode = { $access_mode ->
    [PUBLIC] 🟢 Разрешен для всех
    [INVITED] ⚪ Разрешен для приглашенных
    [PURCHASE_BLOCKED] 🟡 Запрещены покупки
    [REG_BLOCKED] 🟠 Запрещена регистрация
    [RESTRICTED] 🔴 Запрещен для всех
    *[OTHER] { $access_mode }
}

audience-type = { $audience_type ->
    [ALL] Всем
    [PLAN] По плану
    [SUBSCRIBED] С подпиской
    [UNSUBSCRIBED] Без подписки
    [EXPIRED] Просроченным
    [TRIAL] С пробником
    *[OTHER] { $audience_type }
}

broadcast-status = { $broadcast_status ->
    [PROCESSING] В процессе
    [COMPLETED] Завершена
    [CANCELED] Отменена
    [DELETED] Удалена
    [ERROR] Ошибка
    *[OTHER] { $broadcast_status }
}

transaction-status = { $transaction_status ->
    [PENDING] Ожидание
    [COMPLETED] Завершена
    [CANCELED] Отменена
    [REFUNDED] Возврат
    [FAILED] Ошибка
    *[OTHER] { $transaction_status }
}

subscription-status = { $subscription_status ->
    [ACTIVE] Активна
    [DISABLED] Отключена
    [LIMITED] Исчерпан трафик
    [EXPIRED] Истекла
    [DELETED] Удалена
    *[OTHER] { $subscription_status }
}

purchase-type = { $purchase_type ->
    [NEW] Покупка
    [RENEW] Продление
    [CHANGE] Изменение
    *[OTHER] { $purchase_type }
}

language = { $language ->
    [ar] Арабский
    [az] Азербайджанский
    [be] Белорусский
    [cs] Чешский
    [de] Немецкий
    [en] Английский
    [es] Испанский
    [fa] Персидский
    [fr] Французский
    [he] Иврит
    [hi] Хинди
    [id] Индонезийский
    [it] Итальянский
    [ja] Японский
    [kk] Казахский
    [ko] Корейский
    [ms] Малайский
    [nl] Нидерландский
    [pl] Польский
    [pt] Португальский
    [ro] Румынский
    [ru] Русский
    [sr] Сербский
    [tr] Турецкий
    [uk] Украинский
    [uz] Узбекский
    [vi] Вьетнамский
    *[OTHER] { $language }
}