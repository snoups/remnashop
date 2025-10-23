# Errors
ntf-error-dialog-unknown = <i>⚠️ Произошла ошибка. Диалог перезапущен</i>
ntf-error-connect-remnawave = <i>⚠️ Ошибка: Не удалось подключиться к Remnawave</i>
ntf-error-log-not-found = <i>⚠️ Ошибка: Лог файл не найден</i>


# Events
ntf-event-error =
    #EventError

    <b>🔅 Событие: Произошла ошибка!</b>

    <blockquote>
    { $user -> 
        [1]
        • <b>Пользователь</b>: <code>{ $id }</code> ({ $name })
        • <b>Ошибка</b>: { $error }
        *[0] 
        • <b>Ошибка</b>: { $error }
    }
    </blockquote>

ntf-event-error-webhook =
    #EventError

    <b>🔅 Событие: Зафиксирована ошибка вебхука!</b>

    <blockquote>
    • <b>Ошибка</b>: { $error }
    </blockquote>

ntf-event-bot-startup =
    #EventBotStarted

    <b>🔅 Событие: Бот запущен!</b>

    <blockquote>
    • <b>Режим доступа</b>: { access-mode }
    </blockquote>

ntf-event-bot-shutdown =
    #EventBotShutdown

    <b>🔅 Событие: Бот остановлен!</b>

ntf-event-new-user =
    #EventNewUser

    <b>🔅 Событие: Новый пользователь!</b>

    <blockquote>
    • <b>ID</b>: <code>{ $id }</code>
    • <b>Имя</b>: { $name } { $username -> 
        [0] { space }
        *[has] (<a href="tg://user?id={ $id }">@{ $username }</a>)
    }
    </blockquote>

ntf-event-payment-info-amount =
    { $final_amount } { $currency } { $discount_percent -> 
    [0] { space }
    *[more] <strike>{ $original_amount } { $currency }</strike> ({ $discount_percent }%)
    }

ntf-event-payment-info =
    <blockquote>
    • <b>ID</b>: <code>{ $payment_id }</code>
    • <b>Способ оплаты</b>: { gateway-type }
    • <b>Сумма</b>: { ntf-event-payment-info-amount }
    </blockquote>

    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Имя</b>: { $user_name } { $user_username -> 
        [0] { space }
        *[has] (<a href="tg://user?id={ $user_id }">@{ $user_username }</a>)
    }
    </blockquote>

ntf-event-payment-info-plan =
    <blockquote>
    • <b>План</b>: <code>{ $plan_name }</code>
    • <b>Тип</b>: { plan-type }
    • <b>Лимит трафика</b>: { $plan_traffic_limit }
    • <b>Лимит устройств</b>: { $plan_device_limit }
    • <b>Длительность</b>: { $plan_duration }
    </blockquote>

ntf-event-payment-info-previous-plan =
    <blockquote>
    • <b>План</b>: <code>{ $previous_plan_name }</code> -> <code>{ $plan_name }</code>
    • <b>Тип</b>: { $previous_plan_type } -> { plan-type }
    • <b>Лимит трафика</b>: { $previous_plan_traffic_limit } -> { $plan_traffic_limit }
    • <b>Лимит устройств</b>: { $previous_plan_device_limit } -> { $plan_device_limit }
    • <b>Длительность</b>: { $previous_plan_duration } -> { $plan_duration }
    </blockquote>

ntf-event-subscription-new =
    #EventSubscriptionNew

    <b>🔅 Событие: Покупка подписки!</b>

    { ntf-event-payment-info }

    { ntf-event-payment-info-plan }

ntf-event-subscription-renew =
    #EventSubscriptionRenew

    <b>🔅 Событие: Продление подписки!</b>

    { ntf-event-payment-info }

    { ntf-event-payment-info-plan }

ntf-event-subscription-change =
    #EventSubscriptionChange

    <b>🔅 Событие: Изменение подписки!</b>

    { ntf-event-payment-info }

    { ntf-event-payment-info-previous-plan }

ntf-event-node-info =
    <blockquote>
    • <b>Название</b>: { $country } { $name }
    • <b>Адрес</b>: <code>{ $address }:{ $port }</code>
    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    • <b>Последний статус</b>: { $last_status_message }
    • <b>Статус изменен</b>: { $last_status_change }
    </blockquote>

ntf-event-node-connection-lost =
    #EventNode

    <b>🔅 Событие: Соединение с узлом потеряно!</b>

    { ntf-event-node-info }

ntf-event-node-connection-restored =
    #EventNode

    <b>🔅 Событие: Cоединение с узлом восстановлено!</b>

    { ntf-event-node-info }

ntf-event-node-traffic =
    #EventNode

    <b>🔅 Событие: Узел достиг порога лимита трафика!</b>

    { ntf-event-node-info }

ntf-event-user-info =
    <blockquote>
    • <b>UUID</b>: <code>{ $uuid }</code>
    • <b>ID</b>: <code>{ $telegram_id }</code>
    • <b>Статус</b>: { $status }

    • <b>Трафик</b>: { $traffic_used } / { $traffic_limit }
    • <b>Лимит устройств</b>: { $device_limit }
    • <b>Заканчивается</b>: { $expire_at }
    </blockquote>

ntf-event-user-sync =
    #EventUser

    <b>🔅 Событие: Синхронизация пользователя!</b>

    { ntf-event-user-info }

ntf-event-user-deleted =
    #EventUser

    <b>🔅 Событие: Пользователь удален из панели!</b>

    { ntf-event-user-info }

ntf-event-user-first-connected =
    #EventUser

    <b>🔅 Событие: Первое подключение пользователя!</b>

    { ntf-event-user-info }

ntf-event-user-expiring =
    <b>⚠️ Внимание! Ваша подписка истекает через { unit-day }.</b>

ntf-event-user-expired =
    <b>⛔ Внимание! Доступ приостановлен — VPN не работает.</b>

    Ваша подписка истекла, продлите её, чтобы продолжить пользоваться VPN!

ntf-event-user-limited =
    <b>⛔ Внимание! Доступ приостановлен — VPN не работает.</b>

    Вы исчерпали лимит трафика, продлите подписку, чтобы продолжить пользоваться VPN!

ntf-event-user-hwid =
    <blockquote>
    • <b>UUID</b>: <code>{ $user_uuid }</code>
    • <b>HWID</b>: <code>{ $hwid }</code>

    • <b>Платформа</b>: { $platform }
    • <b>Модель</b>: { $device_model }
    • <b>Версия ОС</b>: { $os_version }
    • <b>Агент</b>: { $user_agent }
    </blockquote>

ntf-event-user-hwid-added =
    #EventUserHwid

    <b>🔅 Событие: Добавлено устройство пользователя!</b>

    { ntf-event-user-hwid }

ntf-event-user-hwid-deleted =
    #EventUserHwid

    <b>🔅 Событие: Удалено устройство пользователя!</b>

    { ntf-event-user-hwid }


# Notifications
ntf-channel-join-required = ❇️ Подпишитесь на наш канал и получайте <b>бесплатные дни, акции и новости</b>! После подписки нажмите кнопку «Подтвердить».
ntf-channel-join-error = <i>⚠️ Мы не видим вашу подписку на канал. Проверьте, что вы подписались, и попробуйте ещё раз.</i>
ntf-rules-accept-required = ⚠️ <b>Перед использованием сервиса, пожалуйста, ознакомьтесь и примите <a href="{ $url }">Условия использования</a> сервиса.</b>
ntf-throttling-many-requests = <i>⚠️ Вы отправляете слишком много запросов, пожалуйста, подождите немного</i>

ntf-user-block-self = <i>❌ Нельзя заблокировать самого себя</i>
ntf-user-block-equal = <i>❌ Нельзя заблокировать равноправного пользователя</i>
ntf-user-switch-role-self = <i>❌ Нельзя сменить роль самому себе</i>
ntf-user-switch-role-equal = <i>❌ Нельзя сменить роль равноправному пользователю</i>
ntf-user-not-found = <i>❌ Пользователь не найден</i>

ntf-user-block-dev =
    ⚠️ Разработчик <code>{ $id }</code> ({ $name }) попытался вас заблокировать!

    <i>Он был разжалован и заблокирован</i>

ntf-user-switch-role-dev =
    ⚠️ Разработчик <code>{ $id }</code> ({ $name }) попытался сменить вам роль!

    <i>Он был разжалован и заблокирован</i>

ntf-access-denied = <i>🚧 Бот в режиме обслуживания, попробуйте позже</i>
ntf-access-denied-purchasing = <i>🚧 Бот в режиме обслуживания, Вам придет уведомление когда бот снова будет доступен</i>
ntf-access-allowed = <i>❇️ Весь функционал бота снова доступен, спасибо за ожидание</i>
ntf-access-invalid-link = <i>❌ Некорректная ссылка</i>
ntf-access-link-saved = <i>✅ Ссылка успешно обновлена</i>

ntf-plan-invalid-name = <i>❌ Некорректное имя</i>
ntf-plan-invalid-number = <i>❌ Некорректное число</i>
ntf-plan-trial-once-duration = <i>❌ Пробный план может иметь только одну длительность</i>
ntf-plan-trial-already-exists = <i>❌ Пробный план уже существует</i>
ntf-plan-duration-already-exists = <i>❌ Такая длительность уже существует</i>
ntf-plan-duration-last = <i>❌ Нельзя удалить последнюю длительность</i>
ntf-plan-save-error = <i>❌ Ошибка сохранения плана</i>
ntf-plan-name-already-exists = <i>❌ План с таким именем уже существует</i>
ntf-plan-invalid-user-id = <i>❌ Некорректный ID пользователя</i>
ntf-plan-no-user-found = <i>❌ Пользователь не найден</i>
ntf-plan-user-already-allowed = <i>❌ Пользователь уже добавлен в список разрешенных</i>
ntf-plan-confirm-delete = <i>⚠️ Нажмите еще раз, чтобы удалить</i>
ntf-plan-updated-success = <i>✅ План успешно обновлен</i>
ntf-plan-created-success = <i>✅ План успешно создан</i>
ntf-plan-deleted-success = <i>✅ План успешно удален</i>

ntf-gateway-not-configured = <i>❌ Платежный шлюз не настроен</i>
ntf-gateway-not-configurable = <i>❌ Платежный шлюз не имеет настроек</i>
ntf-gateway-field-wrong-value = <i>❌ Некорректное значение</i>
ntf-gateway-test-payment-created = <i>✅ <a href="{ $url }">Тестовый платеж</a> успешно создан</i>
ntf-gateway-test-payment-error = <i>❌ Произошла ошибка при создании тестового платежа</i>
ntf-gateway-test-payment-confirmed = <i>✅ Тестовый платеж успешно обработан</i>

ntf-subscription-plans-not-available = <i>❌ Нет доступных планов</i>
ntf-subscription-gateways-not-available = <i>❌ Нет доступных платежных систем</i>
ntf-subscription-renew-plan-unavailable = <i>❌ Ваш план устарел и не доступен для продления</i>
ntf-subscription-payment-creation-failed = <i>❌ Произошла ошибка при создании платежа, попробуйте позже</i>

ntf-broadcast-list-empty = <i>❌ Список рассылок пуст</i>
ntf-broadcast-audience-not-available = <i>❌ Нет доступных пользователей для выбранной аудитории</i>
ntf-broadcast-audience-not-active = <i>❌ Нет пользователей у которых есть АКТИВНАЯ подписка с данным планом</i>
ntf-broadcast-plans-not-available = <i>❌ Нет доступных планов</i>
ntf-broadcast-empty-content = <i>❌ Контент пустой.</i>
ntf-broadcast-wrong-content = <i>❌ Некорректный контент</i>
ntf-broadcast-content-saved = <i>✅ Контент сообщения успешно сохранен</i>
ntf-broadcast-preview = { $content }
ntf-broadcast-click-for-confirm = <i>⚠️ Нажмите еще раз, чтобы подтвердить рассылку</i>
ntf-broadcast-not-cancelable = <i>❌ Рассылка не может быть отменена</i>
ntf-broadcast-canceled = <i>✅ Рассылка успешно отменена</i>
ntf-broadcast-deleting = <i>⚠️ Идет удаление всех отправленных сообщений</i>
ntf-broadcast-already-deleted = <i>❌ Рассылка находится в процессе удаления или уже удалена</i>

ntf-broadcast-deleted-success =
    ✅ Рассылка <code>{ $task_id }</code> успешно удалена.

    <blockquote>
    • <b>Всего сообщений</b>: { $total_count }
    • <b>Успешно удалено</b>: { $deleted_count }
    • <b>Не удалось удалить</b>: { $failed_count }
    </blockquote>

ntf-trial-unavailable = <i>❌ Пробная подписка временно недоступна</i>