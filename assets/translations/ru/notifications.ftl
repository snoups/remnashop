# Errors
ntf-error-unknown-state = <i>⚠️ Произошла ошибка. Диалог перезапущен</i>
ntf-error-unknown-intent = <i>⚠️ Произошла ошибка. Диалог перезапущен</i>
ntf-error-connect-remnawave = <i>⚠️ Ошибка: Не удалось подключиться к Remnawave</i>
ntf-error-log-not-found = <i>⚠️ Ошибка: Лог файл не найден</i>


# Events
ntf-event-error =
    #EventError
    
    <b>🔅 Событие: Произошла ошибка!</b>

    <blockquote>
    { $user -> 
        [1]
        • Пользователь: <code>{ $id }</code> ({ $name })
        • Ошибка: { $error }
        *[0] 
        • Ошибка: { $error }
    }
    </blockquote>
    
ntf-event-error-webhook =
    #EventError

    <b>🔅 Событие: Зафиксирована ошибка вебхука!</b>

    <blockquote>
    • Ошибка: { $error }
    </blockquote>

ntf-event-bot-startup =
    #EventBotStarted

    <b>🔅 Событие: Бот запущен!</b>

    <blockquote>
    • Режим обслуживания: <b>{ $mode ->
        [GLOBAL] включен (глобальный)
        [PURCHASE] включен (платежи)
        *[OFF] выключен
    }</b>
    </blockquote>

ntf-event-bot-shutdown =
    #EventBotShutdown

    <b>🔅 Событие: Бот остановлен!</b>

ntf-event-new-user =
    #EventNewUser

    <b>🔅 Событие: Новый пользователь!</b>

    <blockquote>
    • ID: <code>{ $id }</code>
    • Имя: <b>{ $name }</b> { $username -> 
        [0] { space }
        *[has] (<a href="tg://user?id={ $id }">@{ $username }</a>)
    }
    </blockquote>

ntf-event-payment-info-amount =
    <b>{ $final_amount } { $currency }</b> { $discount_percent -> 
    [0] { space }
    *[more] <strike>{ $original_amount } { $currency }</strike> ({ $discount_percent }%)
    }

ntf-event-payment-info =
    <blockquote>
    • ID: <code>{ $payment_id }</code>
    • Способ оплаты: <b>{ gateway-type }</b>
    • Сумма: { ntf-event-payment-info-amount }
    </blockquote>

    <blockquote>
    • ID: <code>{ $user_id }</code>
    • Имя: <b>{ $user_name }</b> { $user_username -> 
        [0] { space }
        *[has] (<a href="tg://user?id={ $user_id }">@{ $user_username }</a>)
    }
    </blockquote>
    
ntf-event-payment-info-plan =
    <blockquote>
    • План: <code>{ $plan_name }</code>
    • Тип: <b>{ plan-type }</b>
    • Лимит трафика: <b>{ $plan_traffic_limit } { unit-gigabyte }</b>
    • Лимит устройств: <b>{ $plan_device_limit }</b>
    • Длительность: <b>{ $plan_duration }</b>
    </blockquote>

ntf-event-payment-info-previous-plan =
    <blockquote>
    • План: <code>{ $previous_plan_name }</code> -> <code>{ $plan_name }</code> 
    • Тип: <b>{ $previous_plan_type }</b> -> <b>{ plan-type }</b>
    • Лимит трафика: <b>{ $previous_plan_traffic_limit } { unit-gigabyte }</b> -> <b>{ $plan_traffic_limit } { unit-gigabyte }</b>
    • Лимит устройств: <b>{ $previous_plan_device_limit }</b> -> <b>{ $plan_device_limit }</b>
    • Длительность: <b>{ $previous_plan_duration }</b> -> <b>{ $plan_duration }</b>
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


# Notifications
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

ntf-maintenance-denied-global = <i>🚧 Бот в режиме обслуживания, попробуйте позже</i>
ntf-maintenance-denied-purchase = <i>🚧 Бот в режиме обслуживания, Вам придет уведомление когда бот снова будет доступен</i>

ntf-plan-wrong-name = <i>❌ Некорректное имя</i>
ntf-plan-wrong-number = <i>❌ Некорректное число</i>
ntf-plan-duration-already-exists = <i>❌ Такая длительность уже существует</i>
ntf-plan-save-error = <i>❌ Ошибка сохранения плана</i>
ntf-plan-name-already-exists = <i>❌ План с таким именем уже существует</i>
ntf-plan-wrong-allowed-id = <i>❌ Некорректный ID пользователя</i>
ntf-plan-no-user-found = <i>❌ Пользователь не найден</i>
ntf-plan-user-already-allowed = <i>❌ Пользователь уже добавлен в список разрешенных</i>
ntf-plan-updated-success = <i>✅ План успешно обновлен</i>
ntf-plan-created-success = <i>✅ План успешно создан</i>

ntf-gateway-not-configured = <i>❌ Платежный шлюз не настроен</i>
ntf-gateway-not-configurable = <i>❌ Платежный шлюз не имеет настроек</i>
ntf-gateway-field-wrong-value = <i>❌ Некорректное значение</i>
ntf-gateway-test-payment-success = <i>✅ <a href="{ $url }">Тестовый платеж</a> успешно создан</i>
ntf-gateway-test-payment-error = <i>❌ Произошла ошибка при создании тестового платежа</i>

ntf-subscription-plans-not-available = <i>❌ Нет доступных планов</i>
ntf-subscription-gateways-not-available = <i>❌ Нет доступных платежных систем</i>