# Back
btn-back = ⬅️ Назад
btn-back-menu = ⬅️ Вернуться в меню
btn-back-dashboard = ⬅️ Вернуться в панель управления


# Rules
btn-rules-accept = ✅ Принять правила


# Channel
btn-channel-join = ❤️ Перейти в канал
btn-channel-confirm = ✅ Подтвердить


# Notification
btn-notification-close = ❌ Закрыть


# Menu
btn-menu-connect = 🚀 Подключиться
btn-menu-trial = 🎁 ПОПРОБОВАТЬ БЕСПЛАТНО
btn-menu-subscription = 💳 Подписка
btn-menu-invite = 👥 Пригласить
btn-menu-support = 🆘 Поддержка
btn-menu-dashboard = 🛠 Панель управления


# Connect
btn-connect = 🚀 Подключиться


# Dashboard
btn-dashboard-statistics = 📊 Статистика
btn-dashboard-users = 👥 Пользователи
btn-dashboard-broadcast = 📢 Рассылка
btn-dashboard-promocodes = 🎟 Промокоды
btn-dashboard-access = 🔓 Режим доступа
btn-dashboard-remnawave = 🌊 RemnaWave
btn-dashboard-remnashop = 🛍 RemnaShop


# Users
btn-users-search = 🔍 Поиск пользователя
btn-users-recent-registered = 🆕 Последние зарегистрированные
btn-users-recent-activity = 📝 Последние взаимодействующие
btn-users-blacklist = 🚫 Чёрный список
btn-users-unblock-all = 🔓 Разблокировать всех
btn-users-unblock-all-confirm = ✅ Подтвердить


# User
btn-user-statistics = 📊 Статистика
btn-user-message = 📩 Сообщение
btn-user-role = 👮‍♂️ Изменить роль
btn-user-transactions = 🧾 Транзакции
btn-user-subscription = 💳 Подписка
btn-user-role-choice = { role }

btn-user-block = { $is_blocked ->
    [1] 🔓 Разблокировать
    *[0] 🔒 Заблокировать
    }


# Broadcast
btn-broadcast-list = 📄 Список всех рассылок
btn-broadcast-all = 👥 Всем
btn-broadcast-plan = 📦 По плану
btn-broadcast-subscribed = ✅ С подпиской
btn-broadcast-unsubscribed = ❌ Без подписки
btn-broadcast-expired = ⌛ Просроченным
btn-broadcast-trial = ✳️ С пробником
btn-broadcast-content = ✉️ Редактировать контент
btn-broadcast-buttons = ✳️ Редактировать кнопки
btn-broadcast-preview = 👀 Предпросмотр
btn-broadcast-confirm = ✅ Запустить рассылку
btn-broadcast-refresh = 🔄 Обновить данные
btn-broadcast-viewing = 👀 Просмотр
btn-broadcast-cancel = ⛔ Остановить рассылку
btn-broadcast-delete = ❌ Удалить отправленное

btn-broadcast-button-select = { $selected ->
    [1] 🔘
    *[0] ⚪
    }

btn-broadcast =  { $status ->
    [PROCESSING] ⏳
    [COMPLETED] ✅
    [CANCELED] ⛔
    [DELETED] ❌
    [ERROR] ⚠️
    *[OTHER] { $broadcast_status }
} { $created_at }


# Go to
btn-goto-subscription = 💳 Купить подписку
btn-goto-promocode = 🎟 Активировать промокод
btn-goto-subscription-renew = 🔄 Продлить подписку


# Promocodes
btn-promocodes-list = 📃 Список промокодов
btn-promocodes-search = 🔍 Поиск промокода
btn-promocodes-create = 🆕 Создать
btn-promocodes-delete = 🗑️ Удалить
btn-promocodes-edit = ✏️ Редактировать


# Access
btn-access-mode = { access-mode }
btn-access-conditions = ⚙️ Условия доступа
btn-access-rules = ✳️ Принятие правил
btn-access-channel = ❇️ Подписка на канал

btn-access-condition-toggle = { $enabled ->
    [1] 🔘 Включено
    *[0] ⚪ Выключено
    }


# RemnaShop
btn-remnashop-admins = 👮‍♂️ Администраторы
btn-remnashop-gateways = 🌐 Платежные системы
btn-remnashop-referral = 👥 Реферальная
btn-remnashop-advertising = 🎯 Реклама
btn-remnashop-plans = 📦 Планы
btn-remnashop-notifications = 🔔 Уведомления
btn-remnashop-logs = 📄 Логи
btn-remnashop-audit = 🔍 Аудит


# Gateways
btn-gateway-title = { gateway-type }
btn-gateways-guide = Инструкция
btn-gateways-setting = { $field }

btn-gateway-active = { $is_active ->
    [1] 🟢 Включено
    *[0] 🔴 Выключено
    }

btn-gateway-test = 🐞 Тест
btn-gateways-default-currency = 💸 Валюта по умолчанию

btn-gateways-default-currency-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $symbol } { $currency }


# Notifications
btn-notifications-user = 👥 Пользовательские

btn-notifications-user-choice = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [EXPIRES_IN_3_DAYS] Подписка истекает (3 дня)
    [EXPIRES_IN_2_DAYS] Подписка истекает (2 дня)
    [EXPIRES_IN_1_DAYS] Подписка истекает (1 дня)
    [EXPIRED] Подписка истекла
    [LIMITED] Трафик исчерпан
    *[OTHER] { $type }
    }
btn-notifications-system = ⚙️ Системные

btn-notifications-system-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [BOT_LIFETIME] Жизненный цикл бота
    [USER_REGISTERED] Регистрация пользователя
    [SUBSCRIPTION] Оформление подписки
    [PROMOCODE_ACTIVATED] Активация промокода
    [NODE_STATUS] Статус узла
    [USER_FIRST_CONNECTED] Первое подключение
    [USER_HWID] Устройства пользователя
    *[OTHER] { $type }
    }


# Plans
btn-plan = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }

btn-plans-statistics = 📊 Статистика
btn-plans-create = 🆕 Создать
btn-plan-confirm = ✅ Подтвердить
btn-plan-name = 🏷️ Имя
btn-plan-type = 🔖 Тип
btn-plan-availability = ✴️ Доступ

btn-plan-active = { $is_active -> 
    [1] 🟢
    *[0] 🔴
    } Статус

btn-plan-durations-prices = ⏳ Длительности и 💰 Цены
btn-plan-traffic = 🌐 Трафик
btn-plan-devices = 📱 Устройства
btn-plan-allowed = 👥 Разрешенные пользователи
btn-plan-squads = 🔗 Внутренние сквады
btn-allowed-user = { $id }

btn-plan-type-choice = { $type -> 
    [TRAFFIC] 🌐 Трафик
    [DEVICES] 📱 Устройства
    [BOTH] 🔗 Трафик + устройства
    [UNLIMITED] ♾️ Безлимит
    *[OTHER] { $type }
    }

btn-plan-availability-choice = { $type -> 
    [ALL] 🌍 Для всех
    [NEW] 🌱 Для новых
    [EXISTING] 👥 Для клиентов
    [INVITED] ✉️ Для приглашенных
    [ALLOWED] 🔐 Для разрешенных
    [TRIAL] 🎁 Для пробника
    *[OTHER] { $type }
    }

btn-plan-duration = ⌛ { $value ->
    [-1] { unlimited }
    *[other] { unit-day }
    }

btn-plan-duration-add = 🆕 Добавить длительность
btn-plan-price-choice = 💸 { $price } { $currency }

btn-plan-squad-choice = { $selected -> 
    [1] 🔘
    *[0] ⚪
    } { $name }


# RemnaWave
btn-remnawave-users = 👥 Пользователи
btn-remnawave-hosts = 🌐 Хосты
btn-remnawave-nodes = 🖥️ Ноды
btn-remnawave-inbounds = 🔌 Инбаунды


# Subscription
btn-subscription-new = 💸 Купить подписку
btn-subscription-renew = 🔄 Продлить
btn-subscription-change = 🔃 Изменить
btn-subscription-promocode = 🎟 Активировать промокод
btn-subscription-plan = { $name }
btn-subscription-duration = { $period } | { $price } { $currency }
btn-subscription-payment-method = { gateway-type } | { $price } { $currency }
btn-subscription-pay = 💳 Оплатить
btn-subscription-get = 🆓 Получить бесплатно
btn-subscription-back-plans = ⬅️ Назад к выбору плана
btn-subscription-back-duration = ⬅️ Изменить длительность
btn-subscription-back-payment-method = ⬅️ Изменить способ оплаты
btn-subscription-connect = 🚀 Подключиться