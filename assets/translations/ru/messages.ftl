msg-plan-details =
    <blockquote>
    { $type ->
    [TRAFFIC]
    • Лимит трафика: { $traffic_limit }
    [DEVICES]
    • Лимит устройств: { $devices_limit }
    [BOTH]
    • Лимит трафика: { $traffic_limit }
    • Лимит устройств: { $devices_limit }
    *[UNLIMITED]
    • Лимит трафика: { unlimited } { unit-gigabyte }
    • Лимит устройств: { unlimited }
    }
    • Заканчивается через: { $expiry_time }
    </blockquote>


# Menu
msg-menu-subscription =
    <b>💳 Подписка:</b>
    { $status ->
    [ACTIVE]
    { msg-plan-details }
    [EXPIRED]
    <blockquote>
    • Срок действия истёк.

    <i>Чтобы продлить перейдите в меню «💳 Подписка»</i>
    </blockquote>
    *[NONE]
    <blockquote>
    • У вас нет оформленной подписки.

    <i>Для оформления перейдите в меню «💳 Подписка»</i>
    </blockquote>
    }

msg-menu-profile =
    <b>👤 Профиль:</b>
    <blockquote>
    • ID: <code>{ $id }</code>
    • Имя: { $name }
    </blockquote>


# Dashboard
msg-dashboard-main = <b>🛠 Панель управления</b>
msg-statistics-main = <b>📊 Статистика</b>
msg-users-main = <b>👥 Пользователи</b>
msg-broadcast-main = <b>📢 Рассылка</b>
msg-promocodes-main = <b>🎟 Промокоды</b>
msg-maintenance-main =
    <b>🚧 Режим обслуживания</b>
    
    Статус: { $status ->
    [GLOBAL] 🔴 Включен (глобальный)
    [PURCHASE] 🟠 Включен (платежи)
    *[OFF] ⚪ Выключен
    }


# Users
msg-users-search =
    <b>🔍 Поиск пользователя</b>

    Введите ID пользователя, часть имени или перешлите любое его сообщение

msg-users-search-results =
    <b>🔍 Поиск пользователя</b>

    Найдено { $count } { $count ->
    [one] пользователь
    [few] пользователя
    *[more] пользователей
    }, { $count ->
    [one] соответствующий
    *[more] соответствующих
    } запросу

msg-users-recent-registered = <b>🆕 Последние зарегистрированные</b>
msg-users-recent-activity = <b>📝 Последние взаимодействующие</b>

msg-user-subscription =
    <b>💳 Подписка:</b>
    { $status ->
    [ACTIVE]
    { $plan_details }
    [EXPIRED]
    <blockquote>
    • Срок действия истёк.
    </blockquote>
    *[NONE]
    <blockquote>
    • Нет оформленной подписки.
    </blockquote>
    }

msg-user-main = 
    <b>📝 Информация о пользователе</b>

    👤 Профиль:
    <blockquote>
    • ID: <code>{ $id }</code>
    • Имя: { $name } { $username -> 
        [0] { space }
        *[has] (<a href="tg://user?id={ $id }">@{ $username }</a>)
    }
    • Роль: { role }
    </blockquote>

    { msg-user-subscription }

msg-user-role = 
    <b>👮‍♂️ Изменить роль</b>
    
    Выберите новую роль для пользователя

msg-users-blacklist =
    <b>🚫 Черный список</b>

    Заблокировано: { $count_blocked } / { $count_users } ({ $percent }%)

msg-users-unblock-all =
    <b>🚫 Черный список</b>

    Вы уверены, что хотите разблокировать всех пользователей?


# RemnaWave
msg-remnawave-main =
    <b>🌊 RemnaWave</b>
    
    🖥️ Система:
    <blockquote>
    • ЦПУ: { $cpu_cores } { $cpu_cores ->
    [one] ядро
    [few] ядра
    *[more] ядер
    } { $cpu_threads } { $cpu_threads ->
    [one] поток
    [few] потока
    *[more] потоков
    }
    • ОЗУ: { $ram_used } / { $ram_total } ({ $ram_used_percent }%)
    • Аптайм: { $uptime }
    </blockquote>

msg-remnawave-users =
    <b>👥 Пользователи</b>

    📊 Статистика:
    <blockquote>
    • Всего: { $users_total }
    • Активные: { $users_active }
    • Отключённые: { $users_disabled }
    • Ограниченные: { $users_limited }
    • Истёкшие: { $users_expired }
    </blockquote>

    🟢 Онлайн:
    <blockquote>
    • За день: { $online_last_day }
    • За неделю: { $online_last_week }
    • Никогда не заходили: { $online_never }
    • Сейчас онлайн: { $online_now }
    </blockquote>

msg-remnawave-host-details =
    { $remark } ({ $status ->
    [ON] включен
    *[OFF] выключен
    }):
    <blockquote>
    • Адрес: <code>{ $address }:{ $port }</code>
    • Инбаунд: <code>{ $inbound_uuid }</code>
    </blockquote>

msg-remnawave-hosts =
    <b>🌐 Хосты</b>
    
    { $hosts }

msg-remnawave-node-details =
    { $country } { $name } ({ $status ->
    [ON] подключено
    *[OFF] отключено
    }):
    <blockquote>
    • Адрес: <code>{ $address }:{ $port }</code>
    • Аптайм (xray): { $xray_uptime }
    • Пользователей онлайн: { $users_online }
    • Трафик: { $traffic_used } / { $traffic_limit }
    </blockquote>

msg-remnawave-nodes =
    <b>🖥️ Ноды</b>

    { $nodes }

msg-remnawave-inbound-details =
    🔗 { $tag }
    <blockquote>
    • UUID: <code>{ $uuid }</code>
    • Протокол: { $type } ({ $network })
    • Порт: { $port }
    • Безопасность: { $security } 
    </blockquote>

msg-remnawave-inbounds =
    <b>🔌 Инбаунды</b>

    { $inbounds }


# RemnaShop
msg-remnashop-main = <b>🛍 RemnaShop</b>
msg-admins-main = <b>👮‍♂️ Администраторы</b>


# Gateways
msg-gateways-main = <b>🌐 Платежные системы</b>
msg-gateways-settings = <b>🌐 { gateway-type }</b>

msg-gateways-field =
    <b>🌐 { gateway-type }</b>

    Введите новое значение для { $field }

msg-gateways-default-currency = <b>💸 Валюта по умолчанию</b>


# Plans
msg-plans-main = <b>📦 Планы</b>

msg-plan-config =
    <b>📦 Конфигурация плана</b>

    <blockquote>
    Имя: { $name }
    Тип: { $type -> 
        [TRAFFIC] Трафик
        [DEVICES] Устройства
        [BOTH] Трафик + устройства
        *[UNLIMITED] Безлимитный
        }
    Доступ: { $availability -> 
        [ALL] Для всех
        [NEW] Для новых
        [EXISTING] Для существующих
        [INVITED] Для приглашенных
        *[ALLOWED] Для разрешенных
        }
    Статус: { $is_active -> 
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    </blockquote>
    
    <blockquote>
    Лимит трафика: { $is_unlimited_traffic -> 
        [1] { unlimited }
        *[0] { $traffic_limit } { unit-gigabyte }
        }
    Лимит устройств: { $is_unlimited_devices -> 
        [1] { unlimited }
        *[0] { $device_limit }
        }
    </blockquote>

    Выберите пункт для изменения

msg-plan-name =
    <b>🏷️ Изменить имя</b>

    Введите новое название плана

msg-plan-type =
    <b>🔖 Изменить тип</b>

    Выберите новый тип плана

msg-plan-availability =
    <b>✴️ Изменить доступность</b>

    Выберите доступность плана

msg-plan-traffic =
    <b>🌐 Изменить лимит трафика</b>

    Введите новый лимит трафика плана

msg-plan-devices =
    <b>📱 Изменить лимит устройств</b>

    Введите новый лимит устройств плана

msg-plan-durations =
    <b>⏳ Длительности плана</b>

    Выберите длительность для настройки цены

msg-plan-duration =
    <b>⏳ Добавить длительность плана</b>

    Введите новую длительность в днях

msg-plan-prices =
    <b>💰 Изменить цены длительности ({ $value ->
            [-1] { unlimited }
            *[other] { unit-day }
        })</b>

    Выберите валюту с ценой для изменения

msg-plan-price =
    <b>💰 Изменить цену для длительности ({ $value ->
            [-1] { unlimited }
            *[other] { unit-day }
        })</b>

    Введите новую цену для валюты { $currency }

msg-plan-allowed-users = 
    <b>👥 Изменить список разрешенных пользователей</b>

    Введите ID пользователя для добавления в список

msg-plan-squads =
    <b>🔗 Изменить список внутренних сквадов</b>

    Выберите какие внутренние группы будут доступны этому плану.


# Notifications
msg-notifications-main = <b>🔔 Настройка уведомлений</b>
msg-notifications-user = <b>👥 Пользовательские уведомления</b>
msg-notifications-system = <b>⚙️ Системные уведомления</b>


# Subscription
msg-subscription-duration-details =
    { $period -> 
    [0] {space}
    *[has] • Длительность: { $period }
    }

msg-subscription-price-details =
    { $price -> 
    [0] {space}
    *[has] • Стоимость: { $price } { $currency }
    }

msg-subscription-details =
    { $plan }
    <blockquote>
    { $type ->
    [TRAFFIC]
    • Лимит трафика: { $traffic } { unit-gigabyte }
    • Лимит устройств: { unlimited }
    { msg-subscription-duration-details }
    { msg-subscription-price-details }
    [DEVICES]
    • Лимит трафика: { unlimited }
    • Лимит устройств: { $devices }
    { msg-subscription-duration-details }
    { msg-subscription-price-details }
    [BOTH]
    • Лимит трафика: { $traffic } { unit-gigabyte }
    • Лимит устройств: { $devices }
    { msg-subscription-duration-details }
    { msg-subscription-price-details }
    *[UNLIMITED]
    • Лимит трафика: { unlimited }
    • Лимит устройств: { unlimited }
    { msg-subscription-duration-details }
    { msg-subscription-price-details }
    }
    </blockquote>

msg-subscription-main = <b>💳 Подписка</b>
msg-subscription-plans = <b>📦 Выберите план</b>

msg-subscription-duration = 
    <b>⏳ Выберите длительность</b>

    { msg-subscription-details }

msg-subscription-payment-method =
    <b>💳 Выберите способ оплаты</b>

    { msg-subscription-details }

msg-subscription-confirm =
    <b>🛒 Подтверждение покупки</b>

    { msg-subscription-details }