# Test
btn-test = Кнопка
msg-test = Сообщение
unlimited = ∞
development = В разработке
test-payment = Тестовый платеж

# RemnaShop
ntf-remnashop-info = 
    <b>💎 remnashop</b>

    Данный проект был создан и поддерживается всего одним <strike>разработчиком</strike>. Поскольку бот полностью бесплатный и с открытым исходным кодом, он существует только благодаря вашей поддержке.

    ⭐ <i>Поставьте звёздочку на GitHub и присоединяйтесь к нашему сообществу.</i>
btn-remnashop-github = GitHub
btn-remnashop-telegram = Telegram
btn-remnashop-donate = Поддержать разработчика

# Payment
payment-invoice-description = Подписка { $name } на { $duration }

# Commands
cmd-start = Перезапустить бота
cmd-help = Помощь

# Layout
space = {" "}
separator = {"\u00A0"}

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
# unit-unlimited = { unlimited }

unit-unlimited = { $value ->
    [-1] { unlimited }
    *[other] { $value }
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
    [ALL] 🟢 Разрешен для всех
    [INVITED] ⚪ Разрешен для приглашенных
    [PURCHASE] 🟠 Запрещены покупки
    [BLOCKED] 🔴 Запрещены любые действия
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