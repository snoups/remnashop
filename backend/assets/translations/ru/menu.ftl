msg-main-menu =
    <b>👤 Профиль</b>:
    <blockquote>• <b>ID</b>: <code>{ $user_id }</code>
    • <b>Имя</b>: { $user_name }
    • <b>Скидка</b>: { $user_discount }%</blockquote>

    { $subscription_block }
frg-menu-subscription =
    { $is_trial ->
        [1] <b>🎁 Пробная подписка</b>:
       *[0] <b>💳 Подписка</b>:
    }
    { $status ->
        [ACTIVE]
            <blockquote>• <b>Лимит трафика</b>: { $traffic_limit }
            • <b>Лимит устройств</b>: { $device_limit }
            • <b>Действует до</b>: { $expire_at }</blockquote>
        [EXPIRED]
            <blockquote>• Срок действия истёк.

            <i>{ $is_trial ->
                [0] Ваша подписка истекла. Продлите её, чтобы продолжить пользоваться сервисом!
               *[1] Ваш бесплатный пробный период закончился. Оформите подписку, чтобы продолжить пользоваться сервисом!
            }</i></blockquote>
        [LIMITED]
            <blockquote>• Ваш трафик израсходован.

            <i>{ $is_trial ->
                [0] { $traffic_strategy ->
                    [NO_RESET] Продлите подписку, чтобы сбросить трафик и продолжить пользоваться сервисом!
                   *[RESET] Трафик восстановится в начале следующего периода. Вы также можете продлить подписку, чтобы сбросить трафик.
                }
               *[1] { $traffic_strategy ->
                    [NO_RESET] Оформите подписку, чтобы продолжить пользоваться сервисом!
                   *[RESET] Трафик восстановится в начале следующего периода. Вы также можете оформить подписку, чтобы пользоваться сервисом без ограничений.
                }
            }</i></blockquote>
        [DISABLED]
            <blockquote>• Ваша подписка отключена.

            <i>Свяжитесь с поддержкой для выяснения причины!</i></blockquote>
       *[NONE]
            <blockquote>• У вас нет оформленной подписки.

            <i>{ $trial_available ->
                [1] 🎁 Для вас доступен бесплатный пробник — нажмите кнопку ниже, чтобы его получить.
               *[0] ↘️ Чтобы купить доступ, нажмите «Купить подписку».
            }</i></blockquote>
    }

    Ещё подписок: { $extra_count } — смотрите «Мои подписки».
frg-subscription-status = { $status ->
        [ACTIVE] Активна
        [LIMITED] Трафик исчерпан
        [EXPIRED] Истекла
        [DISABLED] Отключена
        [DELETED] Удалена
       *[other] { $status }
    }
frg-subscription-unlimited = Безлимит
frg-subscription-traffic-limit = { $traffic_limit } ГБ
msg-window-gone = Этот экран больше недоступен.
msg-paysupport = Чтобы запросить возврат средств, напишите в поддержку.
msg-menu-devices = Ваши устройства ({ $devices_current }/{ $devices_max })
msg-menu-devices-confirm-delete = Удалить это устройство?
msg-menu-devices-confirm-delete-all = Удалить все устройства? Каждое придётся подключать заново.
msg-menu-devices-confirm-reissue = Перевыпустить ссылку подключения? Старая ссылка перестанет работать.

btn-menu =
    .connect = Подключиться
    .connect-not-available = Подключение недоступно
    .trial = Попробовать бесплатно
    .trial-paid = Пробный период — { $trial_price }
    .devices = Устройства
    .devices-icon = 📱
    .support = Поддержка
    .support-icon = 🆘
    .web-cabinet = Веб-кабинет
    .web-cabinet-icon = 🌐
    .subscriptions = Мои подписки
    .purchase = Купить подписку
    .promocode = Промокод
    .referrals = Рефералы

btn-devices =
    .item = { $platform_icon } { $platform } ({ $device_model }) — { $created_at }
    .empty = Нет подключённых устройств
    .delete-all = Удалить все устройства
    .reissue = Перевыпустить ссылку
    .confirm-delete = Да, удалить
    .confirm-reissue = Да, перевыпустить
    .cancel-reissue = Отмена

msg-subscriptions-list = Ваши подписки. Выберите одну, чтобы увидеть подробности.
msg-subscription-card =
    План: { $plan_name }
    Статус: { $status ->
        [ACTIVE] Активна
        [LIMITED] Трафик исчерпан
        [EXPIRED] Истекла
        [DISABLED] Отключена
        [DELETED] Удалена
       *[other] { $status }
    }
    Действует до: { $expire_at }
    Трафик: { $traffic_limit ->
        [0] Безлимит
       *[other] { $traffic_limit } ГБ
    }
    Устройства: { $device_limit ->
        [0] Безлимит
       *[other] { $device_limit }
    }
msg-referrals =
    Приглашайте друзей и получайте награды.

    1 уровень: { $referrals_level_1 }
    2 уровень: { $referrals_level_2 }
    Баллы: { $points }
    Бонусные дни: { $bonus_days }

    { $referral_url }

btn-subscriptions =
    .purchase = Купить подписку

btn-subscription =
    .renew = Продлить
    .change = Сменить план

msg-referrals-withdraw = Баллов на счёте: { $points }. Введите, сколько вывести:
msg-referrals-redeem-target = Бонусных дней: { $bonus_days }. Выберите подписку, к которой их добавить:

btn-referrals =
    .copy = Скопировать ссылку
    .share = Поделиться ссылкой
    .withdraw = Вывести баллы
    .redeem = Обменять бонусные дни

btn-back =
    .general = Назад
    .general-icon = ⬅️

ntf-subscription =
    .gone = Эта подписка больше недоступна.

ntf-devices =
    .deleted = Устройство удалено.
    .all-deleted = Все устройства удалены.
    .reissued = Ссылка подключения перевыпущена.
    .reset-disabled = Это действие сейчас отключено.
    .failed = Что-то пошло не так. Попробуйте позже.

ntf-access =
    .restricted = Сервис временно закрыт на техработы. Загляните позже.
    .registration-disabled = Регистрация сейчас закрыта.
    .invite-only = Регистрация только по приглашению. Попросите у друга реферальную ссылку.
    .payments-disabled = Оплата временно недоступна. Мы напишем, когда она вернётся.
    .payments-restored = Оплата снова доступна — можно завершить покупку.

ntf-common =
    .lost-context = Меню обновлено, продолжите отсюда.
    .unknown-error = Что-то пошло не так. Попробуйте ещё раз.
    .cooldown-active = Повторить это действие можно после { $available_at }.
    .trial-unavailable = Пробный период недоступен.
    .connect-not-available = Подключение недоступно.
    .access-restricted = Доступ ограничен.

ntf-purchase =
    .stars-rejected = Этот заказ уже нельзя оплатить. Начните покупку заново.
    .payments-disabled = Платежи временно недоступны.
    .plan-unavailable = Этот тариф больше недоступен — выберите другой.
    .limit-reached = Достигнут лимит подписок.
    .method-unavailable = Этот способ оплаты сейчас недоступен.
    .retry = Попробуйте ещё раз.
    .failed = Не удалось создать платёж. Попробуйте позже.
    .no-plans = Нет доступных тарифов.
    .no-methods = Нет доступных способов оплаты.
    .done = Готово! Подписка скоро появится.

msg-purchase-plan = Выберите тариф:
msg-purchase-duration = { $plan_name }: выберите срок:
msg-purchase-method = Выберите способ оплаты:
msg-purchase-confirm = { $plan_name } · { $duration_days } дн. · { $price } { $currency_symbol } · { $method }
msg-purchase-pay = Заказ создан. Нажмите кнопку ниже, чтобы оплатить.
msg-purchase-link-choice = У вас уже есть подписка { $plan_name }. Продлить её или купить ещё одну?

btn-purchase =
    .duration = { $days } дн. — { $price } { $currency_symbol }
    .method = { $gateway } — { $price } { $currency_symbol }
    .pay = Оплатить
    .go-to-payment = Перейти к оплате
    .menu = Главное меню
    .link-renew = Продлить: { $subscription }
    .link-new = Купить новую

gateway-name =
    .TELEGRAM_STARS = Telegram Stars
    .YOOKASSA = YooKassa
    .YOOMONEY = YooMoney
    .VALUTIX = Valutix
    .CRYPTOMUS = Cryptomus
    .HELEKET = Heleket
    .CRYPTOPAY = CryptoPay
    .FREEKASSA = FreeKassa
    .MULENPAY = MulenPay
    .PAYMASTER = PayMaster
    .PLATEGA = Platega
    .ROBOKASSA = RoboKassa
    .URLPAY = UrlPay
    .WATA = Wata
    .ROLLYPAY = RollyPay
    .ANTILOPAY = Antilopay
    .PAYPALYCH = Paypalych
    .RIOPAY = RioPay
    .AURAPAY = AuraPay
    .SEVERPAY = SeverPay
    .LAVA = Lava
    .CLOUDPAYMENTS = CloudPayments
    .PAYPEAR = PayPear

ntf-referrals =
    .invalid-amount = Введите положительное число баллов.
    .too-many-attempts = Слишком много запросов. Попробуйте через час.
    .withdraw-failed = Не удалось вывести такую сумму.
    .withdraw-requested = Запрос на вывод отправлен. Мы свяжемся с вами.
    .no-subscription = У вас нет активной подписки, к которой можно добавить дни.
    .days-redeemed = Бонусные дни добавлены к подписке: { $days }.
    .redeem-failed = Бонусные дни нельзя добавить к этой подписке.

ntf-promocode =
    .not-found = Промокод не найден.
    .expired = Срок действия промокода истёк.
    .already-activated = Вы уже активировали этот промокод.
    .discount-not-better = У вас уже есть скидка не меньше этой — промокод не применён.
    .not-available = Этот промокод вам недоступен.
    .no-target-subscription = У вас нет активной подписки, к которой можно применить этот промокод.
    .activated = Промокод активирован!
    .activation-failed = Не удалось активировать промокод. Попробуйте позже.
    .too-many-attempts = Слишком много попыток. Попробуйте через минуту.

msg-promocode-input = Введите промокод:
msg-promocode-target = Выберите подписку, к которой применить промокод:
msg-promocode-confirm = Промокод: { $promo_code }
    Награда: { $promo_reward_type } { $promo_reward }
msg-promocode-confirm-will-replace = ⚠️ Это заменит вашу текущую подписку.

btn-promocode =
    .confirm = Применить
    .confirm-icon = ✅
    .cancel = Отмена
    .cancel-icon = ❌

platform-icon =
    .ios = 📱
    .android = 🤖
    .windows = 🖥
    .macos = 💻
    .linux = 🐧
    .default = ❓

btn-broadcast =
    .unsubscribe = Отписаться от акций
    .resubscribe = Снова получать акции

ntf-broadcast =
    .unsubscribed = Вы больше не будете получать акции. Сервисные сообщения продолжат приходить.
    .resubscribed = Вы снова будете получать акции.
    .promo-gone = Это предложение больше недоступно.
    .start-required = Нажмите /start, чтобы продолжить.

ntf-requirements =
    .rules = Чтобы продолжить, прочитайте и примите правила.
    .channel = Чтобы продолжить, подпишитесь на наш канал.
    .channel-not-found = Пока не видим подписку. Подпишитесь и попробуйте ещё раз.

btn-requirements =
    .rules = Читать правила
    .accept = Принимаю
    .subscribe = Подписаться
    .check = Я подписался

ntf-cabinet-login =
    .link = Нажмите кнопку, чтобы войти в веб-кабинет. Ссылка одноразовая и действует 5 минут.
    .expired = Ссылка для входа устарела. Запросите новую в кабинете.

btn-cabinet-login =
    .open = Войти в кабинет

ntf-cabinet-link =
    .link = Нажмите кнопку, чтобы привязать этот Telegram к аккаунту в веб-кабинете. Ссылка одноразовая и действует 5 минут.
    .expired = Ссылка для привязки устарела. Запросите новую в кабинете.

btn-cabinet-link =
    .open = Привязать к кабинету
