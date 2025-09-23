# Test
btn = Кнопка
msg = Сообщение
unlimited = ∞
development = В разработке
test-payment = Тестовый платеж

# Remnashop
ntf-remnashop = 
    <b>💎 remnashop</b>

    Данный проект был создан и поддерживается всего одним <strike>разработчиком</strike>. Поскольку бот полностью бесплатный и с открытым исходным кодом, он существует только благодаря вашей поддержке.

    ⭐ <i>Поставьте звёздочку на GitHub и присоединяйтесь к нашему сообществу.</i>

btn-remnashop-github = GitHub
btn-remnashop-telegram = Telegram
btn-remnashop-donate = Поддержать разработчика


# Payment
payment-invoice-description = { $name } { $traffic } { $devices } { $duration }

# Commands
cmd-start = Перезапустить бота
cmd-help = Помощь

# Used to create a blank line between elements
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
unit-byte = Б
unit-kilobyte = КБ
unit-megabyte = МБ
unit-gigabyte = ГБ
unit-terabyte = ТБ

unit-second = { $value} { $value ->
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

gateway-type = { $gateway_type ->
    [TELEGRAM_STARS] Telegram Stars
    [YOOKASSA] ЮKassa
    [YOOMONEY] ЮMoney
    [CRYPTOMUS] Cryptomus
    [HELEKET] Heleket
    *[OTHER] { $gateway_type }
}

