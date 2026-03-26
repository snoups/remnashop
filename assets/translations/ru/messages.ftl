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
    • Срок действия истек.
    
    <i>{ $is_trial ->
    [0] Ваша подписка истекла. Продлите ее, чтобы продолжить пользоваться сервисом!
    *[1] Ваш бесплатный пробный период закончился. Оформите подписку, чтобы продолжить пользоваться сервисом!
    }</i>
    </blockquote>
    [LIMITED]
    <blockquote>
    • Ваш трафик израсходован.

    <i>{ $is_trial ->
    [0] { $traffic_strategy ->
        [NO_RESET] Продлите подписку, чтобы сбросить трафик и продолжить пользоваться сервисом!
        *[RESET] Трафик будет восстановлен через { $reset_time }. Вы также можете продлить подписку, чтобы сбросить трафик.
        }
    *[1] { $traffic_strategy ->
        [NO_RESET] Оформите подписку, чтобы продолжить пользоваться сервисом!
        *[RESET] Трафик будет восстановлен через { $reset_time }. Вы также можете оформить подписку, чтобы пользоваться сервисом без ограничений.
        }
    }</i>
    </blockquote>
    [DISABLED]
    <blockquote>
    • Ваша подписка отключена.

    <i>Свяжитесь с поддержкой для выяснения причины!</i>
    </blockquote>
    *[NONE]
    <blockquote>
    • У вас нет оформленной подписки.

    <i>{ $trial_available ->
    [1] 🎁 Для вас доступен бесплатный пробник — нажмите кнопку ниже, чтобы его получить.
    *[0] ↘️ Для покупки доступа перейдите в меню «Подписка».
    }</i>
    </blockquote>
    }

msg-menu-devices =
    <b>📱 Управление устройствами</b>

    Подключено: <b>{ $current_count } / { $max_count }</b>

    { $has_devices ->
    [0] { empty }
    *[HAS] Нажмите на устройство чтобы удалить его.
    Если не хватает устройств — измените подписку.
    }

msg-menu-devices-confirm-reissue =
    🔄 <b>Перевыпуск подписки</b>

    ⚠️ После сброса старая ссылка <b>перестанет работать</b>.

    Вам потребуется:
    • Удалить старую подписку из приложения
    • Добавить новую ссылку из раздела «Подключение»

    Вы уверены, что хотите сбросить ссылку?

msg-menu-devices-confirm-delete =
    🗑 Удалить устройство <b>{ $selected_device_label }</b>?

msg-menu-devices-confirm-delete-all =
    🗑 Удалить <b>все устройства</b>?

msg-menu-invite =
    <b>👥 Пригласить друзей</b>
    
    Делитесь вашей уникальной ссылкой и получайте вознаграждение в виде { $reward_type ->
        [POINTS] <b>баллов, которые можно обменять на подписку или реальные деньги</b>
        [EXTRA_DAYS] <b>бесплатных дней к вашей подписке</b>
        *[OTHER] { $reward_type }
    }!

    <b>📊 Статистика:</b>
    <blockquote>
    👥 Всего приглашенных: { $referrals }
    💳 Платежей по вашей ссылке: { $payments }
    { $reward_type -> 
    [POINTS] 💎 Ваши баллы: { $points }
    *[EXTRA_DAYS] { empty }
    }
    </blockquote>

msg-menu-invite-about =
    <b>🎁 Подробнее о вознаграждении</b>

    <b>✨ Как получить награду:</b>
    <blockquote>
    { $accrual_strategy ->
    [ON_FIRST_PAYMENT] Награда начисляется за первую покупку подписки приглашенным пользователем.
    [ON_EACH_PAYMENT] Награда начисляется за каждую покупку или продление подписки приглашенным пользователем.
    *[OTHER] { $accrual_strategy }
    }
    </blockquote>

    <b>💎 Что вы получаете:</b>
    <blockquote>
    { $max_level -> 
    [1] За приглашенных друзей: { $reward_level_1 }
    *[MORE]
    { $identical_reward ->
    [0]
    1️⃣ За ваших друзей: { $reward_level_1 }
    2️⃣ За приглашенных вашими друзьями: { $reward_level_2 }
    *[1]
    За ваших друзей и приглашенных вашими друзьями: { $reward_level_1 }
    }
    }
    
    { $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }
        [EXTRA_DAYS] <i>(Все дополнительные дни начисляются к вашей текущей подписке)</i>
        *[OTHER] { $reward_type }
    }
    [PERCENT] { $reward_type ->
        [POINTS] <i>(Процент баллов от стоимости их приобретенной подписки)</i>
        [EXTRA_DAYS] <i>(Процент доп. дней от их приобретенной подписки)</i>
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    </blockquote>

msg-invite-reward = { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value -> 
            [one] балл
            [few] балла
            *[more] баллов 
            }
        [EXTRA_DAYS] { space }доп. { $value -> 
            [one] день
            [few] дня
            *[more] дней
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] баллов
        [EXTRA_DAYS] доп. дней
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }


# Dashboard
msg-dashboard-main = <b>🛠 Панель управления</b>
msg-users-main = <b>👥 Пользователи</b>
msg-broadcast-main = <b>📢 Рассылка</b>
msg-statistics-main = <b>📊 Статистика</b>
    
msg-statistics-users =
    <b>👥 Статистика по пользователям</b>

    <blockquote>
    • <b>Всего</b>: { $total_users }
    • <b>Новые за день</b>: { $new_users_daily }
    • <b>Новые за неделю</b>: { $new_users_weekly }
    • <b>Новые за месяц</b>: { $new_users_monthly }

    • <b>С подпиской</b>: { $users_with_subscription }
    • <b>Без подписки</b>: { $users_without_subscription }
    • <b>С пробным периодом</b>: { $users_with_trial }
    </blockquote>

    <blockquote>
    • <b>Заблокированные</b>: { $blocked_users }
    • <b>Заблокировали бота</b>: { $bot_blocked_users }

    • <b>Конверсия пользователей → покупка</b>: { $user_conversion }%
    • <b>Конверсия пробников → подписка</b>: { $trial_conversion }%
    </blockquote>

msg-statistics-subscriptions =
    { $plan_name ->
    [0] <b>💳 Статистика по подпискам</b>
    *[HAS] <b>📦 Статистика плана «{ $plan_name }»</b>
    }

    <blockquote>
    • <b>Всего</b>: { $total }
    • <b>Активные</b>: { $total_active }
    • <b>Истекшие</b>: { $total_expired }
    • <b>Истекающие (7 дней)</b>: { $expiring_soon }
    { $plan_name ->
    [0] • <b>Пробные</b>: { $active_trial }
    *[HAS] • <b>Популярная длительность</b>: { $popular_duration }
    }
    </blockquote>

    { $plan_name ->
    [0] <blockquote>
    • <b>С безлимитом</b>: { $total_unlimited }
    • <b>С лимитом трафика</b>: { $total_traffic }  
    • <b>С лимитом устройств</b>: { $total_devices }
    </blockquote>
    *[HAS] <b>Общий доход</b>:
    <blockquote>
    { $all_income }
    </blockquote>
    }
    
msg-statistics-subscriptions-plan-income = { $income }{ $currency }
    
msg-statistics-transactions =
    { $gateway_type ->
    [0] <b>🧾 Общая статистика по транзакциям</b>
    *[HAS] <b>🧾 Статистика { gateway-type }</b>
    }

    <blockquote>
    • <b>Всего транзакций</b>: { $total_transactions }
    • <b>Завершенных транзакций</b>: { $completed_transactions }
    • <b>Бесплатных транзакций</b>: { $free_transactions }
    { $gateway_type ->
    [0] { $popular_gateway ->
        [0] { empty }
        *[HAS] • <b>Популярная платежная система</b>: { $popular_gateway }
        }
    *[HAS] { empty }
    }
    </blockquote>

    { $gateway_type ->
    [0] { empty }
    *[HAS] <blockquote>
    • <b>Общий доход</b>: { $total_income }{ $currency }
    • <b>Доход за день</b>: { $daily_income }{ $currency }
    • <b>Доход за неделю</b>: { $weekly_income }{ $currency }
    • <b>Доход за месяц</b>: { $monthly_income }{ $currency }
    • <b>Средний чек</b>: { $average_check }{ $currency }
    • <b>Сумма скидок</b>: { $total_discounts }{ $currency }
    </blockquote>
    }

msg-statistics-promocodes =
    <b>🎁 Статистика по промокодам</b>

    <blockquote>
    • <b>Общее кол-во активаций</b>: { $total_promo_activations }
    • <b>Самый популярный промокод</b>: { $most_popular_promo ->
    [0] { unknown }
    *[HAS] { $most_popular_promo }
    }
    • <b>Выдано дней</b>: { $total_promo_days }
    • <b>Выдано трафика</b>: { $total_promo_days }
    • <b>Выдано подписок</b>: { $total_promo_subscriptions }
    • <b>Выдано личных скидок</b>: { $total_promo_personal_discounts }
    • <b>Выдано одноразовых скидок</b>: { $total_promo_purchase_discounts }
    </blockquote>

msg-statistics-referrals =
    <b>👪 Статистика по рефералам</b>

    <blockquote>
    • <b>Всего рефералов</b>: { $total_referrals }
    • <b>Уровень 1</b>: { $level_1_count }
    • <b>Уровень 2</b>: { $level_2_count }
    • <b>Уникальных реферреров</b>: { $unique_referrers }
    { $top_referrer_telegram_id ->
        [0] { empty }
        *[HAS] • <b>Топ реферрер</b>: { $top_referrer_username ->
            [0] { NUMBER($top_referrer_telegram_id, useGrouping: 0) }
            *[HAS] <a href="tg://user?id={ $top_referrer_telegram_id }">@{ $top_referrer_username }</a> 
            } ({ $top_referrer_referrals_count } приглашенных)
    }
    </blockquote>

    <blockquote>
    • <b>Выдано наград</b>: { $total_rewards_issued }
    • <b>Выдано баллов</b>: { $total_points_issued }
    • <b>Выдано дней</b>: { $total_days_issued }
    </blockquote>


# Access
msg-access-main =
    <b>🔓 Режим доступа</b>
    
    <blockquote>
    • <b>Режим</b>: { access-mode }
    • <b>Платежи</b>: { $payments_allowed ->
    [0] запрещены
    *[1] разрешены
    }.
    • <b>Регистрация</b>: { $registration_allowed ->
    [0] запрещена
    *[1] разрешена
    }.
    </blockquote>

msg-access-conditions =
    <b>⚙️ Условия доступа</b>

msg-access-rules =
    <b>✳️ Изменить ссылку на правила</b>

    { $rules_url ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $rules_url }
    </blockquote>
    }

    Введите ссылку (в формате https://telegram.org/tos).

msg-access-channel =
    <b>❇️ Изменить ссылку на канал/группу</b>

    { $channel_url ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $channel_url } { $channel_id -> 
        [0] { empty } 
        *[HAS] (ID: { $channel_id }) 
        }
    </blockquote>
    }
    
    Если ваша группа не имеет @username, отправьте ID группы и ссылку-приглашение отдельными сообщениями.
    
    Если у вас публичный канал/группа, введите только @username.


# Broadcast
msg-broadcast-list = <b>📄 Список рассылок</b>
msg-broadcast-plan-select = <b>📦 Выберите план для рассылки</b>
msg-broadcast-send = <b>📢 Отправить рассылку ({ audience-type })</b>

    { $audience_count } { $audience_count ->
    [one] пользователю
    [few] пользователям
    *[more] пользователей
    } будет отправлена рассылка

msg-broadcast-content =
    <b>✉️ Содержимое рассылки</b>

    Отправьте любое сообщение: текст, изображение или все вместе (поддерживается HTML).

msg-broadcast-buttons = <b>✳️ Кнопки рассылки</b>

msg-broadcast-view =
    <b>📢 Рассылка</b>

    <blockquote>
    • <b>ID</b>: <code>{ $broadcast_id }</code>
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
msg-users-recent-registered = <b>🆕 Последние зарегистрированные</b>
msg-users-recent-activity = <b>📝 Последние взаимодействующие</b>
msg-user-transactions = <b>🧾 Транзакции пользователя</b>
msg-user-devices = <b>📱 Устройства пользователя ({ $current_count } / { $max_count })</b>
msg-user-give-access = <b>🔑 Предоставить доступ к плану</b>

msg-users-search =
    <b>🔍 Поиск пользователя</b>

    Введите ID пользователя, часть имени или перешлите любое его сообщение.

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

msg-user-main = 
    <b>📝 Информация о пользователе</b>

    { hdr-user-profile }
    { frg-user-details }

    <b>💸 Скидка:</b>
    <blockquote>
    • <b>Персональная</b>: { $personal_discount }%
    • <b>На следующую покупку</b>: { $purchase_discount }%
    </blockquote>
    
    { hdr-subscription }
    { $status ->
    [ACTIVE]
    { frg-subscription }
    [EXPIRED]
    <blockquote>
    • Срок действия истек.
    </blockquote>
    [LIMITED]
    <blockquote>
    • Превышен лимит трафика.
    </blockquote>
    [DISABLED]
    <blockquote>
    • Подписка отключена.
    </blockquote>
    *[NONE]
    <blockquote>
    • Нет текущей подписки.
    </blockquote>
    }

msg-user-statistics =
    <b>📊 Статистика пользователя</b>

    <blockquote>
    • <b>Дата регистрации</b>: { $registered_at }
    • <b>Последний платеж</b>: { $last_payment_at ->
        [0] { unknown }
        *[HAS] { $last_payment_at }
    }
    </blockquote>

    { $payment_amounts ->
    [0] { space }
    *[HAS] <blockquote>
    { $payment_amounts }
    </blockquote>
    }

    <blockquote>
    • <b>Приглашен</b>: { $referrer_telegram_id ->
        [0] { unknown }
        *[HAS] { $referrer_username -> 
            [0] { NUMBER($referrer_telegram_id, useGrouping: 0) }
            *[HAS] <a href="tg://user?id={ $referrer_telegram_id }">@{ $referrer_username }</a>
            }
    }
    • <b>Приглашенных (ур. 1)</b>: { $referrals_level_1 }
    • <b>Приглашенных (ур. 2)</b>: { $referrals_level_2 }
    • <b>Получено поинтов</b>: { $reward_points }
    • <b>Получено дней</b>: { $reward_days }
    </blockquote>

msg-user-statistics-payment-amount = • <b>Оплачено ({ $currency })</b>: { $amount }

msg-user-referrals = <b>👪 Рефералы пользователя</b>

msg-user-sync = 
    <b>🌀 Синхронизировать пользователя</b>

    <b>🛍 Remnashop:</b> { $bot_version }
    <blockquote>
    { $has_bot_subscription -> 
    [0] Данные отсутствуют
    *[HAS]{ $bot_subscription }
    }
    </blockquote>

    <b>🌊 Remnawave:</b> { $remna_version }
    <blockquote>
    { $has_remna_subscription -> 
    [0] Данные отсутствуют
    *[HAS] { $remna_subscription }
    }
    </blockquote>

    Выберите актуальные данные для синхронизации.

msg-user-sync-version = { $version ->
    [NEWER] (новее)
    [OLDER] (старее)
    *[UNKNOWN] { empty }
    }

msg-user-sync-subscription =
    • <b>ID</b>: <code>{ $id }</code>
    • Статус: { $status -> 
    [ACTIVE] Активна
    [DISABLED] Отключена
    [LIMITED] Исчерпан трафик
    [EXPIRED] Истекла
    [DELETED] Удалена
    *[OTHER] { $status }
    }
    • Ссылка: <a href="{ $url }">*********</a>

    • Лимит трафика: { $traffic_limit }
    • Лимит устройств: { $device_limit }
    • Осталось: { $expire_time }

    • Внутренние сквады: { $internal_squads ->
    [0] { unknown }
    *[HAS] { $internal_squads }
    }
    • Внешний сквад: { $external_squad ->
    [0] { unknown }
    *[HAS] { $external_squad }
    }
    • Сброс трафика: { $traffic_limit_strategy -> 
    [NO_RESET] При оплате
    [DAY] Каждый день
    [WEEK] Каждую неделю
    [MONTH] Каждый месяц
    *[OTHER] { $traffic_limit_strategy }
    }
    • Тег: { $tag -> 
    [0] { unknown }
    *[HAS] { $tag }
    }

msg-user-sync-waiting =
    <b>🌀 Синхронизация пользователя</b>

    Пожалуйста, подождите... Идет процесс синхронизации данных пользователя. Вы автоматически вернетесь к редактору пользователя по завершении.

msg-user-give-subscription =
    <b>🎁 Выдать подписку</b>

    Выберите план, который хотите выдать пользователю.

msg-user-give-subscription-duration =
    <b>⏳ Выберите длительность</b>

    Выберите длительность выдаваемой подписки.

msg-user-discount =
    <b>💸 Изменить персональную скидку</b>

    Выберите по кнопке или введите свой вариант.

msg-user-points =
    <b>💎 Изменить баллы реферальной системы</b>

    <b>Текущее кол-во баллов: { $current_points }</b>

    Выберите по кнопке или введите свой вариант, чтобы добавить или отнять.

msg-user-subscription-traffic-limit =
    <b>🌐 Изменить лимит трафика</b>

    Выберите по кнопке или введите свой вариант (в ГБ), чтобы изменить лимит трафика.

msg-user-subscription-device-limit =
    <b>📱 Изменить лимит устройств</b>

    Выберите по кнопке или введите свой вариант, чтобы изменить лимит устройств.

msg-user-subscription-expire-time =
    <b>⏳ Изменить срок действия</b>

    <b>Закончится через: { $expire_time }</b>

    Выберите по кнопке или введите свой вариант (в днях), чтобы добавить или отнять.

msg-user-subscription-squads =
    <b>🔗 Изменить список сквадов</b>

    { $internal_squads ->
    [0] { empty }
    *[HAS] <b>⏺️ Внутренние:</b> { $internal_squads }
    }

    { $external_squad ->
    [0] { empty }
    *[HAS] <b>⏹️ Внешний:</b> { $external_squad }
    }

msg-user-subscription-internal-squads =
    <b>⏺️ Изменить список внутренних сквадов</b>

    Выберите, какие внутренние группы будут присвоены этому пользователю.

msg-user-subscription-external-squads =
    <b>⏹️ Изменить внешний сквад</b>

    Выберите, какая внешняя группа будет присвоена этому пользователю.

msg-user-subscription-info =
    <b>💳 Информация о текущей подписке</b>
    
    { hdr-subscription }
    { frg-subscription-details }

    <blockquote>
    • <b>Внутренние сквады</b>: { $internal_squads ->
    [0] { unknown }
    *[HAS] { $internal_squads }
    }
    • <b>Внешний сквад</b>: { $external_squad ->
    [0] { unknown }
    *[HAS] { $external_squad }
    }
    • <b>Первое подключение</b>: { $first_connected_at -> 
    [0] { unknown }
    *[HAS] { $first_connected_at }
    }
    • <b>Последнее подключение</b>: { $last_connected_at ->
    [0] { unknown }
    *[HAS] { $last_connected_at } ({ $node_name })
    } 
    </blockquote>

    { hdr-plan }
    { frg-plan-snapshot }

msg-user-transaction-info =
    <b>🧾 Информация о транзакции</b>

    { hdr-payment }
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Тип</b>: { purchase-type }
    • <b>Статус</b>: { transaction-status }
    • <b>Способ оплаты</b>: { gateway-type }
    • <b>Сумма</b>: { frg-payment-amount }
    • <b>Создано</b>: { $created_at }
    </blockquote>

    { $is_test -> 
    [1] ⚠️ Тестовая транзакция
    *[0]
    { hdr-plan }
    { frg-plan-snapshot }
    }
    
msg-user-role = 
    <b>👮‍♂️ Изменить роль</b>
    
    Выберите новую роль для пользователя.

msg-users-blacklist =
    <b>🚫 Черный список</b>

    Заблокировано: <b>{ $count_blocked }</b> / <b>{ $count_users }</b> ({ $percent }%).

msg-user-message =
    <b>📩 Отправить сообщение пользователю</b>

    Отправьте любое сообщение: текст, изображение или все вместе (поддерживается HTML).
    

# RemnaWave
msg-remnawave-main =
    <b>🌊 RemnaWave v{ $version }</b>
    
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
    • <b>Отключенные</b>: { $users_disabled }
    • <b>Ограниченные</b>: { $users_limited }
    • <b>Истекшие</b>: { $users_expired }
    </blockquote>

    <b>🟢 Онлайн:</b>
    <blockquote>
    • <b>За день</b>: { $online_last_day }
    • <b>За неделю</b>: { $online_last_week }
    • <b>Никогда не заходили</b>: { $online_never }
    • <b>Сейчас онлайн</b>: { $online_now }
    </blockquote>

msg-remnawave-host-details =
    <b>{ $remark } ({ $is_disabled ->
    [1] выключен
    *[0] включен
    }):</b>
    <blockquote>
    • <b>Адрес</b>: <code>{ $address }:{ $port }</code>
    { $inbound_uuid ->
    [0] { empty }
    *[HAS] • <b>Инбаунд</b>: <code>{ $inbound_uuid }</code>
    }
    </blockquote>

msg-remnawave-node-details =
    <b>{ $country } { $name } ({ $is_connected ->
    [1] подключено
    *[0] отключено
    }):</b>
    <blockquote>
    • <b>Адрес</b>: <code>{ $address }{ $port -> 
    [0] { empty }
    *[HAS]:{ $port }
    }</code>
    • <b>Аптайм (xray)</b>: { $xray_uptime }
    • <b>Пользователей онлайн</b>: { $users_online }
    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    </blockquote>

msg-remnawave-inbound-details =
    <b>🔗 { $tag }</b>
    <blockquote>
    • <b>ID</b>: <code>{ $inbound_id }</code>
    • <b>Протокол</b>: { $type } { $network -> 
    [0] { space }
    *[HAS] ({ $network })
    }
    { $port ->
    [0] { empty }
    *[HAS] • <b>Порт</b>: { $port }
    }
    { $security ->
    [0] { empty }
    *[HAS] • <b>Безопасность</b>: { $security } 
    }
    </blockquote>

msg-remnawave-hosts =
    <b>🌐 Хосты</b>
    
    { $host }

msg-remnawave-nodes = 
    <b>🖥️ Ноды</b>

    { $node }

msg-remnawave-inbounds =
    <b>🔌 Инбаунды</b>

    { $inbound }


# RemnaShop
msg-remnashop-main = <b>🛍 RemnaShop { $version ->
[0] { space }
*[HAS] { $version }
}</b>

msg-admins-main = <b>👮‍♂️ Администраторы</b>


# Menu editor
msg-menu-editor-main =
    <b>🎛 Редактор кнопок главного меню</b>

    Выберите кнопку для редактирования.

msg-menu-editor-button =
    <b>🎛 Конфигуратор кнопки</b>

    <blockquote>
    • <b>Статус</b>: { $is_active -> 
        [1] 🟢 Включена
        *[0] 🔴 Выключена
        }
    • <b>Текст</b>: { $text }
    • <b>Доступ</b>: { role }
    • <b>Тип</b>: { button-type }
    • <b>Данные</b>: { $payload }
    
    </blockquote>

    Выберите пункт для изменения.

msg-menu-editor-button-text =
    <b>🏷️ Изменить текст кнопки</b>

    Введите текст кнопки (маскимум 16 символов) или ключ перевода.

msg-menu-editor-button-availability =
    <b>✴️ Изменить доступ к кнопке</b>

    Выберите роль для доступа к кнопке.

msg-menu-editor-button-type =
    <b>🔖 Изменить тип кнопки</b>

    Выберите тип кнопки.

msg-menu-editor-button-payload =
    <b>📄 Изменить данные кнопки</b>

    Введите данные кнопки (для ссылок использовать https).



# Gateways
msg-gateways-main = <b>🌐 Платежные системы</b>
msg-gateways-settings = <b>🌐 Конфигурация { gateway-type }</b>
msg-gateways-default-currency = <b>💸 Валюта по умолчанию</b>
msg-gateways-placement = <b>🔢 Изменить позиционирование</b>

msg-gateways-field =
    <b>🌐 Конфигурация { gateway-type }</b>

    Введите новое значение для { $field }.


# Referral
msg-referral-main =
    <b>👥 Реферальная система</b>

    <blockquote>
    • <b>Статус</b>: { $is_enable -> 
        [1] 🟢 Включена
        *[0] 🔴 Выключена
        }
    • <b>Тип награды</b>: { reward-type }
    • <b>Количество уровней</b>: { $referral_level }
    • <b>Условие начисления</b>: { accrual-strategy }
    • <b>Форма начисления</b>: { reward-strategy }
    </blockquote>

    Выберите пункт для изменения.

msg-referral-level =
    <b>🔢 Изменить уровень</b>

    Выберите максимальный уровень реферала.

msg-referral-reward-type =
    <b>🎀 Изменить тип награды</b>

    Выберите новый тип награды.
    
msg-referral-accrual-strategy =
    <b>📍 Изменить условие начисления</b>

    Выберите, в каком случае будет начисляться награда.


msg-referral-reward-strategy =
    <b>⚖️ Изменить форму начисления</b>

    Выберите способ расчета награды.


msg-referral-reward-level = { $level } уровень: { $value }{ $reward_strategy_type ->
    [AMOUNT] { $reward_type ->
        [POINTS] { space }{ $value -> 
            [one] балл
            [few] балла
            *[more] баллов
            }
        [EXTRA_DAYS] { space }доп. { $value -> 
            [one] день
            [few] дня
            *[more] дней
            }
        *[OTHER] { $reward_type }
    }
    [PERCENT] % { $reward_type ->
        [POINTS] баллов
        [EXTRA_DAYS] доп. дней
        *[OTHER] { $reward_type }
    }
    *[OTHER] { $reward_strategy_type }
    }
    
msg-referral-reward =
    <b>🎁 Изменить награду</b>

    <blockquote>
    { $reward }
    </blockquote>

    { $reward_strategy_type ->
        [AMOUNT] Введите количество { $reward_type ->
            [POINTS] баллов
            [EXTRA_DAYS] дней
            *[OTHER] { $reward_type }
        }
        [PERCENT] Введите процент от { $reward_type ->
            [POINTS] <u>стоимости подписки</u>
            [EXTRA_DAYS] <u>длительности подписки</u>
            *[OTHER] { $reward_type }
        }
        *[OTHER] { $reward_strategy_type }
    } (в формате: уровень=значение)

# Plans
msg-plans-main = <b>📦 Планы</b>

msg-plans-import = 
    <b>📦 Импортировать планы</b>

    Отправьте json файл для импорта.

msg-plans-export = 
    <b>📦 Экспортировать планы</b>

    Выберите планы для экспорта.

msg-plan-configurator =
    <b>📦 Конфигуратор плана</b>

    <blockquote>
    • <b>Название</b>: { $name }
    • <b>Тип</b>: { plan-type } { $is_trial ->
    [1] (Пробник)
    *[0] { space }
    }
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

    Выберите пункт для изменения.

msg-plan-name =
    <b>🏷️ Изменить название</b>

    { $name ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $name }
    </blockquote>
    }

    Введите уникальное название плана или ключ перевода (максимум 16 символов).

msg-plan-description =
    <b>💬 Изменить описание</b>

    { $description ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $description }
    </blockquote>
    }

    Введите новое описание плана или ключ перевода.

msg-plan-tag =
    <b>📌 Изменить тег</b>

    { $tag ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $tag }
    </blockquote>
    }

    Введите новый тег плана (только латинские заглавные буквы, цифры и символ подчеркивания).

msg-plan-type =
    <b>🔖 Изменить тип</b>

    Выберите новый тип плана. Отметьте кнопкой «Пробник», чтобы предоставить данный план как пробный.

msg-plan-availability =
    <b>✴️ Изменить доступность</b>

    Выберите доступность плана.

msg-plan-traffic =
    <b>🌐 Изменить лимит и стратегию сброса трафика</b>

    Введите новый лимит трафика плана (в ГБ) и выберите стратегию его сброса.

msg-plan-devices =
    <b>📱 Изменить лимит устройств</b>

    Введите новый лимит устройств плана.

msg-plan-durations =
    <b>⏳ Длительности плана</b>

    Выберите длительность для изменения цены.

msg-plan-duration =
    <b>⏳ Добавить длительность плана</b>

    Введите новую длительность (в днях).

msg-plan-prices =
    <b>💰 Изменить цены длительности ({ $value ->
            [0] { unlimited }
            *[other] { unit-day }
        })</b>

    Выберите валюту с ценой для изменения.

msg-plan-price =
    <b>💰 Изменить цену для длительности ({ $value ->
            [0] { unlimited }
            *[other] { unit-day }
        })</b>

    Введите новую цену для валюты { $currency }.

msg-plan-allowed-users = 
    <b>👥 Изменить список разрешенных пользователей</b>

    Введите ID пользователя для добавления в список.

msg-plan-squads =
    <b>🔗 Сквады</b>

    { $internal_squads ->
    [0] { space }
    *[HAS] <b>⏺️ Внутренние:</b> { $internal_squads }
    }

    { $external_squad ->
    [0] { space }
    *[HAS] <b>⏹️ Внешний:</b> { $external_squad }
    }

msg-plan-internal-squads =
    <b>⏺️ Изменить список внутренних сквадов</b>

    Выберите, какие внутренние группы будут присвоены этому плану.

msg-plan-external-squads =
    <b>⏹️ Изменить внешний сквад</b>

    Выберите, какая внешняя группа будет присвоена этому плану.


# Notifications
msg-notifications-main = <b>🔔 Настройка уведомлений</b>
msg-notifications-user = <b>👥 Пользовательские уведомления</b>
msg-notifications-system = <b>⚙️ Системные уведомления</b>


# Subscription
msg-subscription-main = <b>💳 Подписка</b>
msg-subscription-plans = <b>📦 Выберите план</b>
msg-subscription-new-success = Чтобы начать пользоваться нашим сервисом, нажмите кнопку <code>`{ btn-subscription.connect }`</code> и следуйте инструкциям!
msg-subscription-renew-success = Ваша подписка продлена на { $added_duration }.

msg-subscription-plan = 
    <b>📦 Доступный план по ссылке</b>
    
    Вам доступен план <b>{ $name }</b> по ссылке. Нажмите кнопку ниже чтобы перейти к выбору длительности и способа оплаты.

    { $description ->
    [0] { space }
    *[HAS]
    <blockquote>
    { $description }
    </blockquote>
    }

    { $purchase_type ->
    [RENEW] <i>⚠️ Текущая подписка будет <u>продлена</u> на выбранный срок.</i>
    [CHANGE] <i>⚠️ Текущая подписка будет <u>заменена</u> данным планом без пересчета оставшегося срока.</i>
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

    • <b>Лимит трафика</b>: { $traffic }
    • <b>Лимит устройств</b>: { $devices }
    { $period ->
    [0] { empty }
    *[HAS] • <b>Длительность</b>: { $period }
    }
    { $final_amount ->
    [0] { empty }
    *[HAS] • <b>Стоимость</b>: { frg-payment-amount }
    }
    </blockquote>

msg-subscription-duration = 
    <b>⏳ Выберите длительность</b>

    { msg-subscription-details }

msg-subscription-payment-method =
    <b>💳 Выберите способ оплаты</b>

    { msg-subscription-details }

msg-subscription-confirm =
    <b>🛒 Подтверждение { $purchase_type ->
    [RENEW] продления
    [CHANGE] изменения
    *[OTHER] покупки
    } подписки</b>

    { msg-subscription-details }

    { $purchase_type ->
    [RENEW] <i>⚠️ Текущая подписка будет <u>продлена</u> на выбранный срок.</i>
    [CHANGE] <i>⚠️ Текущая подписка будет <u>заменена</u> выбранной без пересчета оставшегося срока.</i>
    *[OTHER] { empty }
    }

msg-subscription-trial =
    <b>✅ Пробная подписка успешно получена!</b>

    { msg-subscription-new-success }

msg-subscription-success =
    <b>✅ Оплата прошла успешно!</b>

    { $purchase_type ->
    [NEW] { msg-subscription-new-success }
    [RENEW] { msg-subscription-renew-success }
    [CHANGE] { msg-subscription-change-success }
    *[OTHER] { $purchase_type }
    }

msg-subscription-change-success = 
    Ваша подписка была изменена.

    <b>{ $plan_name }</b>
    { frg-subscription }

msg-subscription-failed = 
    <b>❌ Произошла ошибка!</b>

    Не волнуйтесь, техподдержка уже уведомлена и свяжется с вами в ближайшее время. Приносим извинения за неудобства.


# Importer
msg-importer-main =
    <b>📥 Импорт пользователей</b>

    Запуск синхронизации: проверка всех пользователей в RemnaWave. Если пользователя нет в базе бота, он будет создан и получит временную подписку. Если данные пользователя отличаются, они будут автоматически обновлены (приоритет на данные из панели).

msg-importer-from-xui =
    <b>📥 Импорт пользователей (3X-UI)</b>
    
    { $has_exported -> 
    [1]
    <b>🔍 Найдено:</b>
    <blockquote>
    Всего пользователей: { $total }
    С активной подпиской: { $active }
    С истекшей подпиской: { $expired }
    </blockquote>
    *[0]
    Импортируются все <b>активные</b> пользователи с <b>числовым</b> email.

    Рекомендуется заранее отключить пользователей, у которых в поле email отсутствует Telegram ID. Операция может занять значительное время в зависимости от количества пользователей.

    Отправьте файл базы данных (в формате .db).
    }

msg-importer-squads =
    <b>🔗 Список внутренних сквадов</b>

    Выберите, какие внутренние группы будут доступны импортированным пользователям.

msg-importer-import-completed =
    <b>📥 Импорт пользователей завершен</b>
    
    <b>📃 Информация:</b>
    <blockquote>
    • <b>Всего пользователей</b>: { $total_count }
    • <b>Успешно импортированы</b>: { $success_count }
    • <b>Не удалось импортировать</b>: { $failed_count }
    </blockquote>

msg-importer-sync-completed =
    <b>📥 Синхронизация пользователей завершена</b>

    <b>📃 Информация:</b>
    <blockquote>
    Всего пользователей в панели: { $total_panel_users }
    Всего пользователей в боте: { $total_bot_users }

    Новые пользователи: { $added_users }
    Добавлены подписки: { $added_subscription }
    Обновлены подписки: { $updated}
    
    Пользователи без Telegram ID: { $missing_telegram }
    Ошибки при синхронизации: { $errors }
    </blockquote>


# Promocodes
msg-promocodes-main = <b>🎟 Промокоды</b>
msg-promocode-configurator =
    <b>🎟 Конфигуратор промокода</b>

    <blockquote>
    • <b>Код</b>: { $code }
    • <b>Тип</b>: { promocode-type }
    • <b>Доступ</b>: { availability-type }
    • <b>Статус</b>: { $is_active -> 
        [1] 🟢 Включен
        *[0] 🔴 Выключен
        }
    </blockquote>

    <blockquote>
    { $promocode_type ->
    [DURATION] • <b>Длительность</b>: { $reward }
    [TRAFFIC] • <b>Трафик</b>: { $reward }
    [DEVICES] • <b>Устройства</b>: { $reward }
    [SUBSCRIPTION] • <b>Подписка</b>: { frg-plan-snapshot }
    [PERSONAL_DISCOUNT] • <b>Персональная скидка</b>: { $reward }%
    [PURCHASE_DISCOUNT] • <b>Скидка на покупку</b>: { $reward }%
    *[OTHER] { $promocode_type }
    }
    • <b>Срок действия</b>: { $lifetime }
    • <b>Лимит активаций</b>: { $max_activations }
    </blockquote>

    Выберите пункт для изменения.