# Menu
msg-subscription =
    <blockquote>
    • <b>Лимит трафика</b>: { $traffic_limit }
    • <b>Лимит устройств</b>: { $device_limit }
    • <b>Заканчивается через</b>: { $expiry_time }
    </blockquote>

msg-menu-subscription =
    <b>💳 Подписка:</b>
    { $status ->
    [ACTIVE]
    { msg-subscription }
    [EXPIRED]
    <blockquote>
    • Срок действия истёк.

    <i>Чтобы продлить, перейдите в меню «💳 Подписка»</i>
    </blockquote>
    [LIMITED]
    <blockquote>
    • Вы привысили лимит трафика.

    <i>Чтобы сбросить трафик, перейдите в меню «💳 Подписка»</i>
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
    • <b>ID</b>: <code>{ $id }</code>
    • <b>Имя</b>: { $name }
    </blockquote>


# Dashboard
msg-dashboard-main = <b>🛠 Панель управления</b>
msg-statistics-main = <b>📊 Статистика</b>
msg-users-main = <b>👥 Пользователи</b>
msg-broadcast-main = <b>📢 Рассылка</b>
msg-promocodes-main = <b>🎟 Промокоды</b>


# Access
msg-access-main =
    <b>🔓 Режим доступа</b>
    
    <b>Статус</b>: { access-mode }

msg-access-conditions =
    <b>⚙️ Условия доступа</b>

msg-access-rules =
    <b>✳️ Изменить ссылку на правила</b>

    Введите ссылку

msg-access-channel =
    <b>❇️ Изменить ссылку на канал/группу</b>

    Введите ссылку (в формате @channelusername)


# Broadcast
msg-broadcast-list = <b>📄 Список рассылок</b>
msg-broadcast-select-plan = <b>📦 Выберите план для рассылки</b>
msg-broadcast-send = <b>📢 Отправить рассылку ({ audience-type })</b>

    { $audience_count } { $audience_count ->
    [one] пользователю
    [few] пользователям
    *[more] пользователей
    } будет отправлена рассылка

msg-broadcast-content =
    <b>✉️ Контент рассылки</b>

    Отправьте любое сообщение: текст, изображение или всё вместе (поддерживается HTML)

msg-broadcast-buttons = <b>✳️ Кнопки рассылки</b>

msg-broadcast-view =
    <b>📢 Рассылка</b>

    <blockquote>
    • <b>ID</b>: <code>{ $id }</code>
    • <b>Статус</b>: { broadcast-status }
    • <b>Аудитория</b>: { audience-type }
    • <b>Создано</b>: { $created_at }
    </blockquote>

    <blockquote>
    • <b>Всего сообщений</b>: { $total_count }
    • <b>Успешных</b>: { $success_count }
    • <b>Неудачных</b>: { $failed_count }
    </blockquote>


# Users
msg-users-search =
    <b>🔍 Поиск пользователя</b>

    Введите ID пользователя, часть имени или перешлите любое его сообщение

msg-users-search-results =
    <b>🔍 Поиск пользователя</b>

    Найдено <b>{ $count }</b> { $count ->
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

    <b>👤 Профиль:</b>
    <blockquote>
    • <b>ID</b>: <code>{ $id }</code>
    • <b>Имя</b>: { $name } { $username -> 
        [0] { space }
        *[has] (<a href="tg://user?id={ $id }">@{ $username }</a>)
    }
    • <b>Роль</b>: { role }
    </blockquote>

    { msg-user-subscription }

msg-user-role = 
    <b>👮‍♂️ Изменить роль</b>
    
    Выберите новую роль для пользователя

msg-users-blacklist =
    <b>🚫 Черный список</b>

    Заблокировано: <b>{ $count_blocked }</b> / <b>{ $count_users }</b> ({ $percent }%)

msg-users-unblock-all =
    <b>🚫 Черный список</b>

    Вы уверены, что хотите разблокировать всех пользователей?


# RemnaWave
msg-remnawave-main =
    <b>🌊 RemnaWave</b>
    
    <b>🖥️ Система:</b>
    <blockquote>
    • <b>ЦПУ</b>: { $cpu_cores } { $cpu_cores ->
    [one] ядро
    [few] ядра
    *[more] ядер
    } { $cpu_threads } { $cpu_threads ->
    [one] поток
    [few] потока
    *[more] потоков
    }
    • <b>ОЗУ</b>: { $ram_used } / { $ram_total } ({ $ram_used_percent }%)
    • <b>Аптайм</b>: { $uptime }
    </blockquote>

msg-remnawave-users =
    <b>👥 Пользователи</b>

    <b>📊 Статистика:</b>
    <blockquote>
    • <b>Всего</b>: { $users_total }
    • <b>Активные</b>: { $users_active }
    • <b>Отключённые</b>: { $users_disabled }
    • <b>Ограниченные</b>: { $users_limited }
    • <b>Истёкшие</b>: { $users_expired }
    </blockquote>

    <b>🟢 Онлайн:</b>
    <blockquote>
    • <b>За день</b>: { $online_last_day }
    • <b>За неделю</b>: { $online_last_week }
    • <b>Никогда не заходили</b>: { $online_never }
    • <b>Сейчас онлайн</b>: { $online_now }
    </blockquote>

msg-remnawave-host-details =
    { $remark } ({ $status ->
    [ON] включен
    *[OFF] выключен
    }):
    <blockquote>
    • <b>Адрес</b>: <code>{ $address }:{ $port }</code>
    • <b>Инбаунд</b>: <code>{ $inbound_uuid }</code>
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
    • <b>Адрес</b>: <code>{ $address }:{ $port }</code>
    • <b>Аптайм (xray)</b>: { $xray_uptime }
    • <b>Пользователей онлайн</b>: { $users_online }
    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    </blockquote>

msg-remnawave-nodes =
    <b>🖥️ Ноды</b>

    { $nodes }

msg-remnawave-inbound-details =
    🔗 { $tag }
    <blockquote>
    • <b>UUID</b>: <code>{ $uuid }</code>
    • <b>Протокол</b>: { $type } ({ $network })
    • <b>Порт</b>: { $port }
    • <b>Безопасность</b>: { $security } 
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
    • <b>Имя</b>: { $name }
    • <b>Тип</b>: { plan-type }
    • <b>Доступ</b>: { availability-type }
    • <b>Статус</b>: { $is_active -> 
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    </blockquote>
    
    <blockquote>
    • <b>Лимит трафика</b>: { $is_unlimited_traffic -> 
        [1] { unlimited }
        *[0] { $traffic_limit }
        }
    • <b>Лимит устройств</b>: { $is_unlimited_devices -> 
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

    Выберите какие внутренние группы будут доступны этому плану


# Notifications
msg-notifications-main = <b>🔔 Настройка уведомлений</b>
msg-notifications-user = <b>👥 Пользовательские уведомления</b>
msg-notifications-system = <b>⚙️ Системные уведомления</b>


# Subscription
msg-subscription-duration-details =
    { $period -> 
    [0] {space}
    *[has] • Длительность: <b>{ $period }</b>
    }

msg-subscription-price-details =
    { $final_amount -> 
    [0] {space}
    *[has] • Стоимость: <b>{ $final_amount } { $currency }</b>
        { $discount_percent -> 
        [0] { space }
        *[more] <strike>{ $original_amount } { $currency }</strike> ({ $discount_percent }%)
        }
    }

msg-subscription-details =
    <b>{ $plan }</b>
    <blockquote>
    • Лимит трафика: <b>{ $traffic }</b>
    • Лимит устройств: <b>{ $devices }</b>
    { msg-subscription-duration-details }
    { msg-subscription-price-details }
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

msg-subscription-trial =
    <b>✅ Пробная подписка успешно получена!</b>

    { msg-subscription-new-success }

msg-subscription-success =
    <b>✅ Оплата прошла успешно!</b>

    { $purchase_type ->
    [NEW] { msg-subscription-new-success }
    [RENEW] { msg-subscription-renew-success }
    *[CHANGE] { msg-subscription-change-success }
    }

msg-subscription-new-success = Чтобы начать пользоваться нашим сервисом, нажмите кнопку <code>`🔌 Подключиться`</code> и следуйте инструкциям!
msg-subscription-renew-success = Ваша подписка продлена на { $added_duration }.

msg-subscription-change-success = 
    Ваша подписка была изменена.

    <b>{ $plan_name }</b>
    { msg-subscription }

msg-subscription-failed = 
    <b>❌ Произошла ошибка!</b>

    Не волнуйтесь, техподдержка уже уведомлена и свяжется с вами в ближайшее время. Приносим извинения за неудобства.