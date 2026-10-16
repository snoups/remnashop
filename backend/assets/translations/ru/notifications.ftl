ntf-test = Пуш-уведомления на этом устройстве работают.
    .title = Тестовое уведомление
ntf-session-theft-detected = Повторное использование refresh-токена завершило сессию #{ $session_id } пользователя #{ $user_id }. IP: { $ip }
    .title = Кража сессии
ntf-login-failed = Неверный пароль для «{ $login }». IP: { $ip }
    .title = Неудачная авторизация
ntf-passkey-login-failed = Вход по Passkey отклонён. IP: { $ip }
    .title = Неудачная авторизация Passkey
ntf-oauth-login-failed = Вход через { $provider } отклонён. IP: { $ip }
    .title = Неудачная авторизация OAuth
ntf-backup-failed = Резервная копия { $kind } не создана: { $error }
    .title = Ошибка резервного копирования
ntf-bonus-days-renewal-stuck = Бонус-дни ({ $days }) пользователя #{ $user_id } не применены к подписке #{ $subscription_id }: { $error }. Примените вручную.
    .title = Бонус-дни не применены
ntf-points-withdrawal-requested = { $user } просит вывести { $amount } баллов
    .title = Запрос на вывод баллов
ntf-subscription-purchased = { $user } купил подписку ({ $purchase_type })
    .title = Подписка куплена
ntf-subscription-renewed = { $user } продлил подписку на { $duration_days } дн.
    .title = Подписка продлена
ntf-transaction-refunded = Заказ #{ $order_id }: возврат { $amount } { $currency } через { $gateway_type }
    .title = Возврат транзакции
ntf-transaction-partially-refunded = Заказ #{ $order_id }: частичный возврат { $amount } { $currency } через { $gateway_type }, проверьте вручную
    .title = Частичный возврат
ntf-transaction-fulfilled-manually = { $actor } вручную выдал заказ #{ $order_id } пользователю { $target }
    .title = Ручная выдача подписки
ntf-admin-created = { $actor } создал администратора { $target }
    .title = Администратор создан
ntf-admin-deleted = { $actor } удалил администратора { $target }
    .title = Администратор удалён
ntf-admin-promoted = { $actor } назначил { $target } администратором
    .title = Администратор назначен
ntf-admin-demoted = { $actor } понизил { $target }
    .title = Администратор понижен
ntf-admin-permissions-updated = { $actor } изменил права { $target }
    .title = Права администратора изменены
ntf-broadcast-completed = Рассылка #{ $broadcast_id } завершена: доставлено { $sent }, ошибок { $failed }, заблокировали бота { $blocked }.
    .title = Рассылка отправлена
ntf-broadcast-failed = Рассылка #{ $broadcast_id } остановлена: { $error }
    .title = Ошибка рассылки
ntf-suppressed = Не отправлено похожих уведомлений с прошлого раза: { $count }.
ntf-sources-merged = Уведомления из нескольких источников объединены; показан последний источник.
ntf-customer-open-cabinet = Открыть кабинет
ntf-customer-subscription-purchased = Подписка активна. Данные для подключения — в кабинете и в боте.
    .title = Подписка активирована
ntf-customer-subscription-renewed = Подписка продлена на { $duration_days ->
        [one] { $duration_days } день
        [few] { $duration_days } дня
       *[other] { $duration_days } дней
    }.
    .title = Подписка продлена
ntf-customer-subscription-changed = Тариф изменён. Данные для подключения — в кабинете и в боте.
    .title = Тариф изменён
ntf-customer-subscription-add-on-granted = К подписке добавлено дополнение.
    .title = Дополнение активировано
ntf-customer-subscription-granted = Вам выдана подписка на { $duration_days ->
        [one] { $duration_days } день
        [few] { $duration_days } дня
       *[other] { $duration_days } дней
    }.
    .title = Подписка выдана
ntf-customer-transaction-refunded = Платёж на { $amount } { $currency } возвращён.
    .title = Платёж возвращён
ntf-customer-transaction-partially-refunded = Возвращено { $amount } { $currency } от суммы платежа.
    .title = Частичный возврат
ntf-customer-subscription-expiring = Подписка закончится через { $hours } ч.
    .title = Подписка скоро закончится
ntf-customer-subscription-expired = Подписка закончилась.
    .title = Подписка закончилась
ntf-customer-subscription-traffic-limited = Лимит трафика исчерпан.
    .title = Трафик закончился
ntf-customer-subscription-traffic-threshold = Трафик подходит к концу.
    .title = Трафик на исходе
ntf-customer-cabinet-new-device-sign-in = Новый вход в кабинет с { $ip } ({ $browser }). Если это были не вы — выйдите со всех устройств в кабинете и напишите в поддержку.
    .title = Новый вход
ntf-customer-accounts-merged = Аккаунты объединены: подписки, платежи и способы входа другого аккаунта теперь здесь. Если это были не вы — напишите в поддержку.
    .title = Аккаунты объединены
ntf-customer-referral-reward-issued = Вам начислено { $amount } { $reward_type ->
        [EXTRA_DAYS] { $amount ->
            [one] бонусный день
            [few] бонусных дня
           *[other] бонусных дней
        }
        [POINTS] { $amount ->
            [one] балл
            [few] балла
           *[other] баллов
        }
       *[other] вознаграждение
    } за приглашённого друга.
    .title = Награда за приглашение
ntf-customer-invitee-reward-issued = Вам начислено { $amount } { $reward_type ->
        [EXTRA_DAYS] { $amount ->
            [one] бонусный день
            [few] бонусных дня
           *[other] бонусных дней
        }
        [POINTS] { $amount ->
            [one] балл
            [few] балла
           *[other] баллов
        }
       *[other] вознаграждение
    } за регистрацию по приглашению.
    .title = Бонус за приглашение
ntf-panel-login-failed = Неудачный вход в панель Remnawave под «{ $username }». IP: { $ip }
    .title = Неудачный вход в панель
ntf-panel-login-succeeded = Вход в панель Remnawave под «{ $username }». IP: { $ip }
    .title = Вход в панель
ntf-required-channel-check-failed = Бот не может проверить подписку на канал { $channel_id }: { $error }. Пока проблема не решена, клиенты проходят без проверки.
    .title = Ошибка проверки канала
ntf-telegram-webhook-failed = Ошибка webhook Telegram: { $error }
    .title = Ошибка webhook
ntf-node-connection-lost = Нода «{ $node_name }» потеряла связь.
    .title = Нода недоступна
ntf-node-connection-restored = Нода «{ $node_name }» снова на связи.
    .title = Нода доступна
ntf-node-traffic-reached = Нода «{ $node_name }» достигла лимита трафика.
    .title = Лимит трафика ноды
ntf-node-billing-due = Оплата ноды «{ $node_name }» у { $provider } — { $next_billing_at }.
    .title = Оплата ноды
ntf-remnawave-unavailable = Панель Remnawave не отвечает ({ $error }).
    .title = Панель недоступна
ntf-remnawave-restored = Панель Remnawave снова отвечает.
    .title = Панель доступна
ntf-remnawave-version-mismatch = Remnawave { $version } вне поддерживаемого диапазона { $supported }.
    .title = Неподдерживаемая версия панели
ntf-panel-started = Панель Remnawave перезапущена.
    .title = Панель запущена
ntf-bot-started = Бот @{ $username } запущен.
    .title = Бот запущен
ntf-bot-stopped = Бот остановлен.
    .title = Бот остановлен
ntf-telegram-user-registered = Новый клиент { $user } пришёл через бота.
    .title = Новый клиент
ntf-cabinet-user-registered = Новый клиент { $user } пришёл через веб-кабинет ({ $method }).
    .title = Новый клиент
ntf-telegram-registration-blocked = Регистрация { $user } через бота заблокирована.
    .title = Регистрация заблокирована
ntf-cabinet-registration-blocked = Регистрация { $user } через веб-кабинет заблокирована.
    .title = Регистрация заблокирована
ntf-subscription-first-connected = { $user } впервые подключился к VPN.
    .title = Первое подключение
ntf-torrent-blocker-report = Торрент-трафик { $user } заблокирован на «{ $node_name }» ({ $destination }).
    .title = Торрент заблокирован
ntf-subscription-expired = Подписка { $user } истекла.
    .title = Подписка истекла
ntf-subscription-traffic-limited = У { $user } закончился трафик.
    .title = Трафик исчерпан
ntf-subscription-revoked = { $user } перевыпустил ссылку подписки.
    .title = Ссылка перевыпущена
ntf-subscription-not-connected = { $user } не подключился через { $hours } ч после оформления.
    .title = Не подключился
ntf-customer-subscription-not-connected = Вы оформили подписку { $hours } ч назад, но ещё не подключились. Инструкция по настройке — в кабинете.
    .title = Пора подключиться
ntf-customer-subscription-expired-ago = Подписка закончилась { $hours } ч назад. Продлите её, чтобы снова быть на связи.
    .title = Подписка закончилась
ntf-customer-torrent-blocker-report = Использовать торренты с включённым VPN запрещено. Торрент-трафик заблокирован; при повторных нарушениях доступ может быть ограничен.
    .title = Торренты запрещены
