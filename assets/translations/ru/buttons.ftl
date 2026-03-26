btn-back = 
    .general = ⬅️ Назад
    .menu = ↩️ Главное меню
    .menu-return = ↩️ Вернуться в главное меню
    .dashboard = ↩️ Вернуться в панель управления

btn-common =
    .notification-close = ❌ Закрыть
    .devices-empty = ⚠️ У вас нет подключённых устройств
    .cancel = Отмена

    .squad-choice = { $selected -> 
    [1] 🔘
    *[0] ⚪
    } { $name }

    .duration = ⌛ { $value ->
    [0] { unlimited }
    *[other] { unit-day }
    }

btn-devices =
    .delete-all = 🗑 Удалить все устройства
    .reissue = 🔄 Перевыпустить подписку
    .confirm-delete = ✅ Да, удалить
    .confirm-reissue = ✅ Да, сбросить
    .cancel-reissue = ❌ Нет

btn-remnashop-info =
    .release-latest = 👀 Посмотреть
    .how-upgrade = ❓ Как обновить
    .github = ⭐ GitHub
    .telegram = 👪 Telegram
    .donate = 💰 Поддержать разработчика
    .guide = ❓ Инструкция

btn-requirement =
    .rules-accept = ✅ Принять правила
    .channel-join = ❤️ Перейти в канал
    .channel-confirm = ✅ Подтвердить

btn-menu =
    .trial = 🎁 ПОПРОБОВАТЬ БЕСПЛАТНО
    .connect = 🚀 Подключиться
    .devices = 📱 Мои устройства
    .subscription = 💳 Подписка
    .invite = 👥 Пригласить
    .support = 🆘 Поддержка
    .dashboard = 🛠 Панель управления

    .connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] ПРЕВЫШЕН ЛИМИТ ТРАФИКА
    [EXPIRED] СРОК ДЕЙСТВИЯ ИСТЕК
    *[OTHER] ВАША ПОДПИСКА НЕ РАБОТАЕТ
    } ⚠️

btn-invite =
    .about = ❓ Подробнее о награде
    .copy = 📋 Скопировать ссылку
    .send = 📩 Пригласить
    .qr = 🧾 QR-код
    .withdraw-points = 💎 Обменять баллы

btn-dashboard =
    .statistics = 📊 Статистика
    .users = 👥 Пользователи
    .broadcast = 📢 Рассылка
    .promocodes = 🎟 Промокоды
    .access = 🔓 Режим доступа
    .remnawave = 🌊 RemnaWave
    .remnashop = 🛍 RemnaShop
    .importer = 📥 Импорт пользователей

btn-statistics =
    .users = 👥 Пользователи
    .subscriptions = 💳 Подписки
    .transactions = 🧾 Транзакции
    .promocodes = 🎁 Промокоды
    .referrals = 👪 Рефералы

    .subscription-page =
    { $page ->
        [0] { $is_current ->
            [1] [ Общая статистика ]
            *[0] Общая статистика
        }
        *[other] { $is_current ->
            [1] [ { $plan_name } ]
            *[0] { $plan_name }
        }
    }

    .transaction-page =
    { $page ->
        [0] { $is_current ->
            [1] [ Общая статистика ]
            *[0] Общая статистика
        }
        *[other] { $is_current ->
            [1] [ { gateway-type } ]
            *[0] { gateway-type }
        }
    }

btn-users =
    .search = 🔍 Поиск пользователя
    .recent-registered = 🆕 Последние зарегистрированные
    .recent-activity = 📝 Последние взаимодействующие
    .blacklist = 🚫 Черный список
    .unblock-all = 🔓 Разблокировать всех

btn-user =
    .discount = 💸 Изменить скидку
    .points = 💎 Изменить баллы
    .statistics = 📊 Статистика
    .referrals = 👪 Рефералы
    .message = 📩 Сообщение
    .role = 👮‍♂️ Изменить роль
    .transactions = 🧾 Транзакции
    .give-access = 🔑 Доступ к планам
    .current-subscription = 💳 Текущая подписка
    .subscription-traffic-limit = 🌐 Лимит трафика
    .subscription-device-limit = 📱 Лимит устройств
    .subscription-expire-time = ⏳ Время истечения
    .subscription-squads = 🔗 Сквады
    .subscription-traffic-reset = 🔄 Сбросить трафик
    .subscription-devices = 🧾 Список устройств
    .subscription-url = 📋 Скопировать ссылку
    .subscription-set = ✅ Установить подписку
    .subscription-delete = ❌ Удалить
    .message-preview = 👀 Предпросмотр
    .message-confirm = ✅ Отправить
    .sync = 🌀 Синхронизировать
    .sync-remnawave = 🌊 Использовать данные Remnawave
    .sync-remnashop = 🛍 Использовать данные Remnashop
    .give-subscription = 🎁 Выдать подписку
    .subscription-internal-squads = ⏺️ Внутренние сквады
    .subscription-external-squads = ⏹️ Внешний сквад

    .allowed-plan-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $plan_name }

    .subscription-active-toggle = { $is_active ->
    [1] 🔴 Выключить
    *[0] 🟢 Включить
    }

    .transaction = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [CANCELED] ❌
    [REFUNDED] 💸
    [FAILED] ⚠️
    *[OTHER] { $status }
    } { $created_at }
    
    .block = { $is_blocked ->
    [1] 🔓 Разблокировать
    *[0] 🔒 Заблокировать
    }

btn-broadcast =
    .list = 📄 Список всех рассылок
    .all = 👥 Всем
    .plan = 📦 По плану
    .subscribed = ✅ С подпиской
    .unsubscribed = ❌ Без подписки
    .expired = ⌛ Просроченным
    .trial = ✳️ С пробником
    .content = ✉️ Редактировать содержимое
    .buttons = ✳️ Редактировать кнопки
    .preview = 👀 Предпросмотр
    .confirm = ✅ Запустить рассылку
    .refresh = 🔄 Обновить данные
    .viewing = 👀 Просмотр
    .cancel = ⛔ Остановить рассылку
    .delete = ❌ Удалить отправленное

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
    .subscription = 💳 Купить подписку
    .promocode = 🎟 Активировать промокод
    .invite = 👥 Пригласить
    .subscription-renew = 🔄 Продлить подписку
    .user-profile = 👤 Перейти к пользователю
    .referrer-profile = 🤝 Перейти к пригласителю
    .contact-support = 📩 Перейти в поддержку

btn-promocodes =
    .list = 📃 Список промокодов
    .search = 🔍 Поиск промокода
    .create = 🆕 Создать
    .delete = 🗑️ Удалить
    .edit = ✏️ Редактировать

btn-access =
    .mode = { access-mode }
    .conditions = ⚙️ Условия доступа
    .rules = ✳️ Принятие правил
    .channel = ❇️ Подписка на канал

    .payments-toggle = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } Платежи

    .registration-toggle = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } Регистрация

    .condition-toggle = { $enabled ->
    [1] 🔘 Включено
    *[0] ⚪ Выключено
    }

btn-remnashop =
    .admins = 👮‍♂️ Администраторы
    .gateways = 🌐 Платежные системы
    .referral = 👥 Реф. система
    .advertising = 🎯 Реклама
    .plans = 📦 Планы
    .notifications = 🔔 Уведомления
    .logs = 📄 Логи
    .menu-editor = 🎛 Доп. кнопки

btn-menu-editor =
    .text = 🏷️ Текст
    .availability = ✴️ Доступ
    .type = 🔖 Тип
    .payload = 📄 Данные
    .confirm = ✅ Сохранить

    .button = { $is_active -> 
        [1] 🟢 
        *[0] 🔴 
    } { $text }
    
    .active = { $is_active -> 
        [1] 🟢 Включена
        *[0] 🔴 Выключена
    }
    
btn-gateway =
    .title = { gateway-type }
    .setting = { $field }
    .webhook-copy = 📋 Скопировать вебхук
    .test = 🐞 Тест
    .default-currency = 💸 Валюта по умолчанию
    .placement = 🔢 Изменить позиционирование

    .active = { $is_active ->
    [1] 🟢 Включено
    *[0] 🔴 Выключено
    }

    .default-currency-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $symbol } { $currency }

btn-referral =
    .level = 🔢 Уровень
    .reward-type = 🎀 Тип награды
    .accrual-strategy = 📍 Условие начисления
    .reward-strategy = ⚖️ Форма начисления
    .reward = 🎁 Награда
    
    .enable = { $is_enable -> 
    [1] 🟢 Включена
    *[0] 🔴 Выключена
    }

    .level-choice = { $type -> 
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $type }
    }

    .reward-choice = { $type -> 
    [POINTS] 💎 Баллы
    [EXTRA_DAYS] ⏳ Дни
    *[OTHER] { $type }
    }

    .accrual-strategy-choice = { $type -> 
    [ON_FIRST_PAYMENT] 💳 Первый платеж
    [ON_EACH_PAYMENT] 💸 Каждый платеж
    *[OTHER] { $type }
    }

    .reward-strategy-choice = { $type -> 
    [AMOUNT] 🔸 Фиксированная
    [PERCENT] 🔹 Процентная
    *[OTHER] { $type }
    }

btn-notifications =
    .user = 👥 Пользовательские
    .system = ⚙️ Системные
    
    .user-choice = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [EXPIRES_IN_3_DAYS] Подписка истекает (3 дня)
    [EXPIRES_IN_2_DAYS] Подписка истекает (2 дня)
    [EXPIRES_IN_1_DAY] Подписка истекает (1 день)
    [EXPIRED] Подписка истекла
    [EXPIRED_1_DAY_AGO] Подписка истекла (1 день)
    [LIMITED] Трафик исчерпан
    [REFERRAL_ATTACHED] Реферал закреплен
    [REFERRAL_REWARD_RECEIVED] Вознаграждение за реферала
    *[OTHER] { $type }
    }

    .system-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $type ->
    [BOT_LIFECYCLE] Жизненный цикл бота
    [BOT_UPDATE] Обновления бота
    [USER_REGISTERED] Регистрация пользователя
    [SUBSCRIPTION] Оформление подписки
    [PROMOCODE_ACTIVATED] Активация промокода
    [TRIAL_ACTIVATED] Активация пробника
    [NODE_STATUS_CHANGED] Статус узла
    [NODE_TRAFFIC_REACHED] Трафик узла
    [USER_FIRST_CONNECTION] Первое подключение
    [USER_DEVICES_UPDATED] Устройства пользователя
    [USER_REVOKED_SUBSCRIPTION] Сброс подписки
    *[OTHER] { $type }
    }

btn-plans =
    .statistics = 📊 Статистика
    .create = 🆕 Создать
    .save = ✅ Сохранить
    .create = ✅ Создать план
    .delete = ❌ Удалить
    .name = 🏷️ Название
    .description = 💬 Описание
    .description-remove = ❌ Удалить текущее описание
    .tag = 📌 Тег
    .tag-remove = ❌ Удалить текущий тег
    .type = 🔖 Тип
    .availability = ✴️ Доступ
    .durations-prices = ⏳ Длительности и 💰 Цены
    .traffic = 🌐 Трафик
    .devices = 📱 Устройства
    .allowed = 👥 Разрешенные пользователи
    .squads = 🔗 Сквады
    .internal-squads = ⏺️ Внутренние сквады
    .external-squads = ⏹️ Внешний сквад
    .allowed-user = { $id }
    .duration-add = 🆕 Добавить длительность
    .price-choice = 💸 { $price } { $currency }
    .export = 📤 Экспорт
    .import = 📥 Импорт
    .exporting = 📤 Экспортировать
    .importing = 📥 Импортировать
    .url = 📋 Скопировать ссылку на план

    .trial = { $is_trial ->
    [1] 🔘
    *[0] ⚪
    } Пробник 

    .export-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $name }

    .title = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }

    .active = { $is_active -> 
    [1] 🟢 Включен
    *[0] 🔴 Выключен
    }
    
    .type-choice = { $type -> 
    [TRAFFIC] 🌐 Трафик
    [DEVICES] 📱 Устройства
    [BOTH] 🔗 Трафик + устройства
    [UNLIMITED] ♾️ Безлимит
    *[OTHER] { $type }
    }

    .availability-choice = { $type -> 
    [ALL] 🌍 Для всех
    [NEW] 🌱 Для новых
    [EXISTING] 👥 Для клиентов
    [INVITED] ✉️ Для приглашенных
    [ALLOWED] 🔐 Для разрешенных
    [LINK] 🔗 По ссылке
    *[OTHER] { $type }
    }

    .traffic-strategy-choice = { $selected ->
    [1] 🔘 { traffic-strategy }
    *[0] ⚪ { traffic-strategy }
    }

    
btn-remnawave =
    .users = 👥 Пользователи
    .hosts = 🌐 Хосты
    .nodes = 🖥️ Ноды
    .inbounds = 🔌 Инбаунды

btn-importer =
    .from-xui = 💩 Импорт из панели 3X-UI
    .from-xui-shop = 🛒 Бот 3xui-shop
    .sync = 🌀 Запустить синхронизацию
    .squads = 🔗 Внутренние сквады
    .import-all = ✅ Импортировать всех
    .import-active = ❇️ Импортировать активных

btn-subscription =
    .plan = 💳 Перейти к оформлению подписки
    .new = 💸 Купить подписку
    .renew = 🔄 Продлить
    .change = 🔃 Изменить
    .promocode = 🎟 Активировать промокод
    .payment-method = { gateway-type } | { $price } { $currency }
    .pay = 💳 Оплатить
    .get = 🎁 Получить бесплатно
    .back-plans = ⬅️ Назад к выбору плана
    .back-duration = ⬅️ Изменить длительность
    .back-payment-method = ⬅️ Изменить способ оплаты
    .connect = 🚀 Подключиться

    .duration = { $period } | { $final_amount -> 
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }

btn-promocode =
    .code = 🏷️ Код
    .type = 🔖 Тип награды
    .availability = ✴️ Доступ
    .reward = 🎁 Награда
    .lifetime = ⌛ Время жизни
    .allowed = 👥 Разрешенные пользователи
    .confirm = ✅ Подтвердить
    
    .active = { $is_active -> 
    [1] 🟢
    *[0] 🔴
    } Статус