ntf-test = Push-уведомления на этом устройстве работают.
    .title = Тестовое уведомление
ntf-session-theft-detected = Повторное использование refresh-токена завершило сессию #{ $session_id } пользователя #{ $user_id }. IP: { $ip }
    .title = Обнаружена кража сессии!
    .emoji = ⚠️
ntf-login-failed = Неверный пароль для «{ $login }». IP: { $ip }
    .title = Неудачная попытка входа!
    .emoji = ⚠️
ntf-passkey-login-failed = Вход по Passkey отклонён. IP: { $ip }
    .title = Неудачная попытка входа!
    .emoji = ⚠️
ntf-oauth-login-failed = Вход через { $provider } отклонён. IP: { $ip }
    .title = Неудачная попытка входа!
    .emoji = ⚠️
ntf-backup-failed = Резервная копия { $kind } не создана: { $error }
    .title = Ошибка резервного копирования!
    .emoji = ⚠️
ntf-bonus-days-renewal-stuck = Бонус-дни ({ $days }) пользователя #{ $user_id } не применены к подписке #{ $subscription_id }: { $error }. Примените вручную.
    .title = Бонус-дни не применены!
    .emoji = ⚠️
ntf-subscription-purchased = { $user } купил подписку ({ $purchase_type })
    .title = { $is_trial ->
        [yes] Получение пробной подписки!
       *[no] { $purchase_type ->
            [CHANGE] Изменение подписки!
            [RENEW] Продление подписки!
           *[other] Покупка подписки!
        }
    }
ntf-subscription-renewed = { $user } продлил подписку на { $duration_days } дн.
    .title = Продление подписки!
ntf-transaction-refunded = Заказ #{ $order_id }: возврат { $amount } { $currency } через { $gateway_type }
    .title = Платёж возвращён!
    .emoji = ⚠️
ntf-transaction-partially-refunded = Заказ #{ $order_id }: частичный возврат { $amount } { $currency } через { $gateway_type }, проверьте вручную
    .title = Платёж возвращён!
    .emoji = ⚠️
ntf-transaction-fulfilled-manually = { $actor } вручную выдал заказ #{ $order_id } пользователю { $target }
    .title = Ручная выдача подписки!
ntf-paid-order-not-fulfilled = Заказ #{ $order_id }: { $amount } { $currency } через { $gateway_type } оплачен, но подписка ещё не выдана. Попытки продолжаются, проверьте заказ.
    .title = Ошибка обработки платежа!
    .emoji = ⚠️
ntf-broadcast-completed = Рассылка #{ $broadcast_id } завершена: доставлено { $sent }, ошибок { $failed }, заблокировали бота { $blocked }.
    .title = Рассылка завершена!
ntf-broadcast-failed = Рассылка #{ $broadcast_id } остановлена: { $error }
    .title = Ошибка рассылки!
    .emoji = ⚠️
ntf-suppressed = Не отправлено похожих уведомлений с прошлого раза: { $count }.
ntf-sources-merged = Уведомления из нескольких источников объединены; показан последний источник.
ntf-customer-open-cabinet = Открыть кабинет
ntf-customer-button-renew = 🔄 Продлить подписку
ntf-customer-button-buy = 💳 Купить подписку
ntf-customer-button-close = ❌ Закрыть
ntf-customer-button-connect = 🚀 Подключиться
ntf-customer-button-support = 📩 Перейти в поддержку
ntf-customer-button-revoke-sessions = 🔒 Завершить все сессии
ntf-customer-sessions-revoked = ✅ Мы завершили все сеансы в личном кабинете. Если это были не вы, напишите в поддержку — разберёмся вместе.
ntf-customer-subscription-purchased = Чтобы начать пользоваться сервисом, подключите устройство и следуйте инструкциям — это займёт пару минут.
    .title = { $is_trial ->
        [yes] Пробная подписка активирована
       *[no] { $paid ->
            [yes] Оплата прошла успешно!
           *[no] Подписка активирована
        }
    }
    .emoji = { $is_trial ->
        [yes] 🎁
       *[no] ✅
    }
ntf-customer-subscription-renewed = Ваша подписка продлена на { $duration_days ->
        [one] { $duration_days } день
        [few] { $duration_days } дня
       *[other] { $duration_days } дней
    }.
    .title = { $paid ->
        [yes] Оплата прошла успешно!
       *[no] Подписка продлена
    }
    .emoji = ✅
ntf-customer-subscription-changed = Ваша подписка изменена. Подключение остаётся прежним, ничего настраивать не нужно.
    .title = { $paid ->
        [yes] Оплата прошла успешно!
       *[no] Тариф изменён
    }
    .emoji = ✅
ntf-customer-subscription-add-on-granted = { $addon_type ->
        [TRAFFIC] К подписке добавлено { $amount } ГБ трафика.
       *[DEVICES] К подписке добавлено { $amount ->
            [one] { $amount } устройство
            [few] { $amount } устройства
           *[other] { $amount } устройств
        }.
    }
    .title = Дополнение активировано
    .emoji = 🎁
ntf-customer-subscription-granted = Доступ открыт на { $duration_days ->
        [one] { $duration_days } день
        [few] { $duration_days } дня
       *[other] { $duration_days } дней
    }. Подключите устройство, чтобы начать пользоваться.
    .title = Подписка выдана
    .emoji = 🎁
ntf-customer-transaction-refunded = { $money } вернутся тем же способом, которым вы платили.
    .title = Платёж возвращён
    .emoji = 💸
ntf-customer-transaction-partially-refunded = Часть платежа, { $money }, вернётся тем же способом, которым вы платили.
    .title = Частичный возврат
    .emoji = 💸
ntf-customer-paid-order-not-fulfilled = Оплата { $money } получена, но подписка выдаётся дольше обычного. Не волнуйтесь: мы уже разбираемся. Если она скоро не появится, напишите в поддержку.
    .title = Выдача задерживается
    .emoji = ⏳
ntf-customer-subscription-expiring = { $is_trial ->
        [yes] Ваш пробный период закончится через { $span_unit ->
        [day] { $span ->
            [one] { $span } день
            [few] { $span } дня
           *[other] { $span } дней
        }
       *[hour] { $span } ч
    }. Оформите подписку, чтобы не терять доступ к сервису.
       *[no] Ваша подписка закончится через { $span_unit ->
        [day] { $span ->
            [one] { $span } день
            [few] { $span } дня
           *[other] { $span } дней
        }
       *[hour] { $span } ч
    }. Продлите её заранее, чтобы не терять доступ к сервису.
    }
    .title = Подписка скоро закончится
    .emoji = ⚠️
ntf-customer-subscription-expired = { $is_trial ->
        [yes] Ваш пробный период закончился. Оформите подписку, чтобы продолжить пользоваться VPN.
       *[no] Ваша подписка истекла. Продлите её, чтобы продолжить пользоваться VPN.
    }
    .title = Доступ приостановлен — VPN не работает
    .emoji = ⛔
ntf-customer-subscription-traffic-limited = Ваш трафик израсходован. { $is_trial ->
        [yes] Оформите подписку, чтобы продолжить пользоваться сервисом.
       *[no] { $traffic_strategy ->
            [DAY] Он восстановится завтра, или продлите подписку, чтобы сбросить его сейчас.
            [WEEK] Он восстановится в начале следующей недели, или продлите подписку, чтобы сбросить его сейчас.
            [MONTH] Он восстановится в начале следующего месяца, или продлите подписку, чтобы сбросить его сейчас.
            [MONTH_ROLLING] Он восстановится в день ежемесячного сброса, или продлите подписку, чтобы сбросить его сейчас.
           *[NO_RESET] Продлите подписку, чтобы сбросить трафик и продолжить пользоваться сервисом.
        }
    }
    .title = Доступ приостановлен — VPN не работает
    .emoji = ⛔
ntf-customer-subscription-traffic-threshold = { $is_trial ->
        [yes] Оформите подписку, чтобы не потерять доступ.
       *[no] Продлите подписку, чтобы не потерять доступ.
    }
    .title = Трафик на исходе
    .emoji = ⚠️
ntf-customer-cabinet-new-device-sign-in = Кто-то вошёл в ваш личный кабинет с IP-адресом { $ip } ({ $browser }). Если это были не вы — завершите сессии на всех устройствах и напишите в поддержку.
    .title = Вход с нового устройства
    .emoji = 🔐
ntf-customer-accounts-merged = Подписки, платежи и способы входа другого аккаунта теперь здесь. Если это были не вы — напишите в поддержку.
    .title = Аккаунты объединены
    .emoji = 🔗
ntf-customer-referral-reward-issued = { $has_name ->
        [yes] Пользователь { $name } совершил платёж —{" "}
       *[no] {""}
    }вам начислено { $amount } { $reward_type ->
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
    }. Спасибо, что пригласили!
    .title = Вам начислена награда!
    .emoji = 💰
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
    .title = Приветственный бонус
    .emoji = 🎁
ntf-panel-login-failed = Неудачный вход в панель Remnawave под «{ $username }». IP: { $ip }
    .title = Неудачный вход в панель Remnawave!
    .emoji = ⚠️
ntf-panel-login-succeeded = Вход в панель Remnawave под «{ $username }». IP: { $ip }
    .title = Вход в панель Remnawave!
ntf-rescue-cli-used = { $action ->
        [reset_owner_access] Сброшен доступ владельца: новый пароль, очищен IP-allowlist, удалены сессии, passkey и привязки.
        [enable_password_login] Включён вход по паролю.
        [reset_encrypted_secrets] Стёрты все секреты из базы: заново введите токен бота, ключи шлюзов, OAuth, SMTP и капчи.
       *[restore_backup] База восстановлена из резервной копии.
    }
    .title = Использована консоль восстановления!
    .emoji = ⚠️
ntf-required-channel-check-failed = Бот не может проверить подписку на канал { $channel_id }: { $error }. Пока проблема не решена, клиенты проходят без проверки.
    .title = Ошибка проверки подписки на канал/группу!
    .emoji = ⚠️
    .hint = Пока проблема не решена, клиенты проходят без проверки.
ntf-telegram-webhook-failed = Ошибка webhook Telegram: { $error }
    .title = Зафиксирована ошибка вебхука!
ntf-node-connection-lost = Соединение с узлом «{ $node_name }» потеряно.
    .title = Соединение с узлом потеряно!
ntf-node-connection-restored = Соединение с узлом «{ $node_name }» восстановлено.
    .title = Соединение с узлом восстановлено!
ntf-node-traffic-reached = Узел «{ $node_name }» достиг лимита трафика.
    .title = Узел достиг порога лимита трафика!
ntf-node-billing-due = Оплата узла «{ $node_name }» у { $provider } — { $next_billing_at }.
    .title = Приближается оплата узла!
ntf-remnawave-unavailable = Соединение с Remnawave потеряно ({ $error }).
    .title = Ошибка при подключении к Remnawave!
ntf-remnawave-restored = Соединение с Remnawave восстановлено.
    .title = Соединение с Remnawave восстановлено!
ntf-system-health-degraded = { $kind ->
        [process_down] Процесс { $subject } не отвечает.
        [host_disk_full] Диск сервера заполнен на { $value }%.
        [host_memory_high] Память сервера занята на { $value }%.
       *[event_loop_lag] Процесс { $subject } работает с задержкой: p99 event loop — { $value } мс.
    }
    .title = Критическое состояние системы!
ntf-system-health-restored = { $kind ->
        [process_down] Процесс { $subject } снова работает.
        [host_disk_full] Заполненность диска сервера вернулась к норме.
        [host_memory_high] Использование памяти сервера вернулось к норме.
       *[event_loop_lag] Задержка процесса { $subject } вернулась к норме.
    }
    .title = Состояние системы восстановлено!
ntf-remnawave-version-mismatch = Remnawave { $version } вне поддерживаемого диапазона { $supported }.
    .title = Возможная несовместимость с Remnawave!
    .emoji = ⚠️
ntf-panel-started = Панель Remnawave перезапущена.
    .title = Панель Remnawave запущена!
ntf-bot-started = Бот @{ $username } запущен.
    .title = Бот запущен!
ntf-bot-stopped = Бот остановлен.
    .title = Бот остановлен!
ntf-telegram-user-registered = Новый клиент { $user } пришёл через бота.
    .title = Новый пользователь!
ntf-cabinet-user-registered = Новый клиент { $user } пришёл через веб-кабинет ({ $method }).
    .title = Новый пользователь!
ntf-telegram-registration-blocked = Регистрация { $user } через бота заблокирована.
    .title = Регистрация заблокирована!
ntf-cabinet-registration-blocked = Регистрация { $user } через веб-кабинет заблокирована.
    .title = Регистрация заблокирована!
ntf-subscription-first-connected = { $user } впервые подключился к VPN.
    .title = Первое подключение пользователя!
ntf-torrent-blocker-report = Торрент-трафик { $user } заблокирован на «{ $node_name }» ({ $destination }).
    .title = Обнаружен BitTorrent-трафик!
    .emoji = ⚠️
ntf-subscription-expired = Подписка { $user } истекла.
    .title = Подписка истекла!
ntf-subscription-traffic-limited = У { $user } закончился трафик.
    .title = Трафик исчерпан!
ntf-subscription-revoked = { $user } перевыпустил ссылку подписки.
    .title = Пользователь перевыпустил подписку!
ntf-subscription-not-connected = { $user } не подключился через { $hours } ч после оформления.
    .title = Пользователь не подключился!
ntf-customer-subscription-not-connected = Вы оформили подписку { $span_unit ->
        [day] { $span ->
            [one] { $span } день
            [few] { $span } дня
           *[other] { $span } дней
        }
       *[hour] { $span } ч
    } назад, но ещё ни разу ею не воспользовались. Если с настройкой возникли сложности, напишите в поддержку — разберёмся вместе.
    .title = Не получилось подключиться?
    .emoji = 🔌
ntf-customer-subscription-expired-ago = { $is_trial ->
        [yes] Ваш пробный период закончился { $span_unit ->
        [day] { $span ->
            [one] { $span } день
            [few] { $span } дня
           *[other] { $span } дней
        }
       *[hour] { $span } ч
    } назад. Оформите подписку, чтобы снова пользоваться VPN.
       *[no] Ваша подписка истекла { $span_unit ->
        [day] { $span ->
            [one] { $span } день
            [few] { $span } дня
           *[other] { $span } дней
        }
       *[hour] { $span } ч
    } назад. Продлите её, чтобы снова пользоваться VPN.
    }
    .title = Доступ приостановлен — VPN не работает
    .emoji = ⛔
ntf-customer-torrent-blocker-report = Мы заметили торрент-трафик через VPN. Торренты запрещены правилами сервиса, поэтому подключение ограничено{ $block_unit ->
        [minute] { " " }на { $block_span ->
            [one] { $block_span } минуту
            [few] { $block_span } минуты
           *[other] { $block_span } минут
        }
        [hour] { " " }на { $block_span } ч
       *[none] {""}
    }. Отключите торрент-клиент или исключите его из VPN, чтобы это не повторялось. При повторных нарушениях доступ может быть ограничен надолго.
    .title = Подключение временно ограничено
    .emoji = ⛔
ntf-customer-promocode-discount-expiring = { $percent }% по промокоду { $code } действуют ещё { $span_unit ->
        [day] { $span ->
            [one] { $span } день
            [few] { $span } дня
           *[other] { $span } дней
        }
       *[hour] { $span } ч
    }. Успейте оформить покупку.
    .title = Скидка скоро сгорит
    .emoji = ⏳
ntf-customer-payments-restored = Возможность оплаты восстановлена! Теперь вы можете купить или продлить подписку. Спасибо за ожидание.
    .title = Оплата снова доступна
    .emoji = ❇️
ntf-telegram-label =
    .event = Событие
    .user = Пользователь
    .id = ID
    .telegram-id = Telegram ID
    .name = Имя
    .username = Username
    .email = Почта
    .details = Детали
    .payment = Платёж
    .subscription = Подписка
    .trial-subscription = Пробная подписка
    .plan = План
    .trial-plan = Пробный план
    .promocode = Промокод
    .device = Устройство
    .build = Сборка
    .access = Доступность
    .session = Сессия
    .order = Заказ
    .ip = IP
    .login = Логин
    .method = Способ
    .provider = Провайдер
    .user-agent = User-Agent
    .kind = Тип
    .run = Запуск
    .bonus-days = Бонус-дни
    .channel = Канал
    .error = Ошибка
    .node = Узел
    .reason = Причина
    .billing-date = Дата оплаты
    .version = Версия
    .supported = Поддерживается
    .bot = Бот
    .broadcast = Рассылка
    .sent = Доставлено
    .failed = Ошибок
    .blocked = Заблокировали бота
    .admin = Администратор
    .previous-status = Прежний статус
    .ad-link = Рекламная ссылка
    .referral-code = Реферальный код
    .sign-in-method = Способ входа
    .hours = Прошло часов
    .destination = Адрес
    .payment-method = Способ оплаты
    .amount = Сумма
    .refund = Возврат
    .status = Статус
    .traffic = Трафик
    .traffic-limit = Лимит трафика
    .device-limit = Лимит устройств
    .left = Осталось
    .duration = Длительность
    .type = Тип
    .code = Код
    .reward = Награда
    .branch = Ветка
    .commit = Коммит
    .build-time = Время сборки
    .mode = Режим
    .payments = Платежи
    .registration = Регистрация
    .uptime = Аптайм
    .hwid = HWID
    .platform = Платформа
    .model = Модель
    .os-version = Версия ОС
    .channel-bot = Бот
    .channel-cabinet = Веб-кабинет
    .method-password = Пароль
    .method-passkey = Passkey
    .method-oauth = OAuth
    .refund-full = полный
    .refund-partial = частичный
    .unlimited = Безлимит
ntf-telegram-subscription-status = { $value ->
        [ACTIVE] Активна
        [LIMITED] Исчерпан трафик
        [EXPIRED] Истекла
        [DISABLED] Отключена
        [DELETED] Удалена
       *[other] { $value }
    }
ntf-telegram-plan-type = { $value ->
        [TRAFFIC] Трафик
        [DEVICES] Устройства
        [BOTH] Трафик + устройства
       *[UNLIMITED] Безлимитный
    }
ntf-telegram-transaction-status = { $value ->
        [PENDING] Ожидает оплаты
        [PAID] Оплачен
        [FAILED] Ошибка выдачи
        [CANCELED] Отменён
        [REFUNDED] Возвращён
       *[other] { $value }
    }
ntf-telegram-backup-kind = { $value ->
        [DATABASE] База данных
        [ASSETS] Файлы
       *[other] { $value }
    }
ntf-telegram-sign-in-method = { $value ->
        [TELEGRAM] Telegram
        [EMAIL] Почта
        [GOOGLE] Google
        [YANDEX] Яндекс
       *[other] { $value }
    }
ntf-telegram-oauth-provider = { $value ->
        [GITHUB] GitHub
        [TELEGRAM] Telegram
        [OIDC] OIDC
        [GOOGLE] Google
        [YANDEX] Яндекс
       *[other] { $value }
    }
ntf-telegram-access-mode = { $value ->
        [PUBLIC] разрешён для всех
        [INVITED] разрешён для приглашённых
        [RESTRICTED] запрещён для всех
       *[other] { $value }
    }
ntf-telegram-payments = { $value ->
        [yes] разрешены
       *[no] запрещены
    }
ntf-telegram-registration = { $value ->
        [yes] разрешена
       *[no] запрещена
    }
ntf-telegram-promocode-type = { $value ->
        [DURATION] Длительность
        [TRAFFIC] Трафик
        [DEVICES] Устройства
        [SUBSCRIPTION] Подписка
        [PERSONAL_DISCOUNT] Персональная скидка
        [PURCHASE_DISCOUNT] Скидка на покупку
       *[other] { $value }
    }
ntf-telegram-days = { $count ->
        [one] { $count } день
        [few] { $count } дня
       *[other] { $count } дней
    }
ntf-telegram-uptime = { $days ->
        [0] { $hours } ч { $minutes } мин
       *[other] { $days } д { $hours } ч
    }
ntf-telegram-traffic = { $unit ->
        [MB] { $amount } МБ
        [TB] { $amount } ТБ
       *[GB] { $amount } ГБ
    }
ntf-subscription-changed = { $user } сменил тариф подписки.
    .title = Изменение подписки!
ntf-subscription-device-added = { $user } добавил новое устройство.
    .title = Пользователь добавил новое устройство!
ntf-subscription-device-removed = { $user } удалил устройство.
    .title = Пользователь удалил устройство!
ntf-promocode-activated = { $user } активировал промокод.
    .title = Активация промокода!
ntf-customer-referral-attached = Пользователь { $name } присоединился по вашей пригласительной ссылке.{ $rewarded ->
        [yes] { " " }Награду вы получите, когда он оплатит подписку.
       *[no] {""}
    }
    .title = Вы пригласили друга!
    .emoji = 🎉
