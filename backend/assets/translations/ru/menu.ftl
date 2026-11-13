msg-main-menu =
    <b>👤 Профиль</b>:
    <blockquote>
    • <b>ID</b>: <code>{ $user_id }</code>
    • <b>Имя</b>: { $user_name }
    • <b>Скидка</b>: { $user_discount }%
    </blockquote>

    { $subscription_block }
frg-menu-subscription =
    { $is_trial ->
        [1] <b>🎁 Пробная подписка</b>:
       *[0] <b>💳 Подписка</b>:
    }
    { $status ->
        [ACTIVE]
            <blockquote>
            • <b>Лимит трафика</b>: { $traffic_limit }
            • <b>Лимит устройств</b>: { $device_limit }
            • <b>Действует до</b>: { $expire_at }
            </blockquote>
        [EXPIRED]
            <blockquote>
            • Срок действия истёк.

            <i>{ $is_trial ->
                [0] Ваша подписка истекла. Продлите её, чтобы продолжить пользоваться сервисом!
               *[1] Ваш бесплатный пробный период закончился. Оформите подписку, чтобы продолжить пользоваться сервисом!
            }</i>
            </blockquote>
        [LIMITED]
            <blockquote>
            • Ваш трафик израсходован.

            <i>{ $is_trial ->
                [0] { $traffic_strategy ->
                    [NO_RESET] Продлите подписку, чтобы сбросить трафик и продолжить пользоваться сервисом!
                   *[RESET] Трафик восстановится в начале следующего периода. Вы также можете продлить подписку, чтобы сбросить трафик.
                }
               *[1] { $traffic_strategy ->
                    [NO_RESET] Оформите подписку, чтобы продолжить пользоваться сервисом!
                   *[RESET] Трафик восстановится в начале следующего периода. Вы также можете оформить подписку, чтобы пользоваться сервисом без ограничений.
                }
            }</i>
            </blockquote>
       *[DISABLED]
            <blockquote>
            • Ваша подписка отключена.

            <i>Свяжитесь с поддержкой для выяснения причины!</i>
            </blockquote>
    }

    Ещё подписок: { $extra_count } — смотрите «Мои подписки».
frg-menu-no-subscription =
    <blockquote>
    У вас нет оформленной подписки.

    <i>{ $trial_available ->
        [1] 🎁 Для вас доступен бесплатный пробник — нажмите кнопку ниже, чтобы его получить.
       *[0] ↘️ Чтобы купить доступ, нажмите «Купить подписку».
    }</i>
    </blockquote>
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
msg-menu-devices-confirm-delete-all = Удалить все устройства? Ссылка подключения сменится, все устройства потеряют доступ — каждое придётся подключать заново по новой ссылке.
msg-menu-devices-confirm-reissue = Перевыпустить ссылку подключения? Старая ссылка перестанет работать.

btn-menu =
    .connect = Подключиться
    .connect-icon = 🚀
    .connect-not-available = { $subscription_problem ->
        [LIMITED] ПРЕВЫШЕН ЛИМИТ ТРАФИКА
        [EXPIRED] СРОК ДЕЙСТВИЯ ИСТЁК
       *[other] ВАША ПОДПИСКА НЕ РАБОТАЕТ
    }
    .connect-not-available-icon = ⚠️
    .trial = Попробовать бесплатно
    .trial-icon = 🎁
    .trial-paid = Пробный период — { $trial_price }
    .trial-paid-icon = 🚀
    .devices = Устройства
    .devices-icon = 📱
    .support = Поддержка
    .support-icon = 🆘
    .web-cabinet = Веб-кабинет
    .web-cabinet-icon = 🌐
    .subscription = Подписка
    .subscription-icon = 💳
    .subscriptions = Мои подписки
    .subscriptions-icon = 💳
    .purchase = Купить подписку
    .purchase-icon = 💸
    .promocode = Промокод
    .promocode-icon = 🎟
    .referrals = Рефералы
    .referrals-icon = 👥
    .legal = Документы
    .legal-icon = 📄

btn-legal =
    .OFFER = Публичная оферта
    .USER_AGREEMENT = Пользовательское соглашение
    .PRIVACY_POLICY = Политика конфиденциальности

msg-legal-list = Правовые документы. Выберите, какой прочитать.
msg-legal-gate =
    <b>Перед началом работы</b>
    Чтобы пользоваться ботом, ознакомьтесь с документами ниже и примите их.
msg-legal-gate-update =
    <b>Мы обновили документы</b>
    Посмотрите новую редакцию и примите её, чтобы продолжить.

btn-legal-gate =
    .accept = ✅ Принимаю

btn-devices =
    .item = { $platform_icon } { $platform } ({ $device_model }) — { $created_at }
    .delete-all = Удалить все устройства
    .delete-all-icon = 🗑
    .reissue = Перевыпустить ссылку
    .reissue-icon = 🔄
    .confirm-delete = Да, удалить
    .confirm-delete-icon = ✅
    .confirm-reissue = Да, перевыпустить
    .confirm-reissue-icon = ✅
    .cancel-reissue = Отмена
    .cancel-reissue-icon = ❌

msg-subscriptions-list =
    <b>💳 Мои подписки</b>

    <blockquote>
    Выберите подписку, чтобы подключиться, продлить её или сменить план.
    </blockquote>
msg-subscription-card =
    { $is_trial ->
        [1] <b>🎁 Пробная подписка · { $plan_name }</b>
       *[0] <b>💳 Подписка · { $plan_name }</b>
    }
    <blockquote>
    • <b>Статус</b>: { $status ->
        [ACTIVE] 🟢 Активна
        [LIMITED] 🟡 Трафик исчерпан
        [EXPIRED] 🔴 Истекла
        [DISABLED] ⚫ Отключена
        [DELETED] Удалена
       *[other] { $status }
    }
    • <b>Лимит трафика</b>: { $traffic_limit ->
        [0] Безлимит
       *[other] { $traffic_limit } ГБ
    }
    • <b>Лимит устройств</b>: { $device_limit ->
        [0] Безлимит
       *[other] { $device_limit }
    }
    • <b>Действует до</b>: { $expire_at }
    </blockquote>
msg-referrals =
    <b>👥 Пригласить друзей</b>

    Делитесь вашей уникальной ссылкой и получайте награды!

    <b>📊 Статистика</b>:
    <blockquote>
    • <b>Приглашено вами</b>: { $referrals_level_1 }
    • <b>Приглашено вашими друзьями</b>: { $referrals_level_2 }
    • <b>Баллы</b>: { $points }
    • <b>Бонусные дни</b>: { $bonus_days }
    </blockquote>

btn-subscriptions =
    .purchase = Купить подписку
    .purchase-icon = 💸
    .item = { $status ->
        [ACTIVE] 🟢 { $plan_name } · до { $expire_at }
        [LIMITED] 🟡 { $plan_name } · трафик исчерпан
        [EXPIRED] 🔴 { $plan_name } · истекла { $expire_at }
        [DISABLED] ⚫ { $plan_name } · отключена
       *[other] { $plan_name } · { $expire_at }
    }

btn-subscription =
    .renew = Продлить
    .renew-icon = 🔄
    .change = Сменить план
    .change-icon = 🔃

msg-referrals-about =
    <b>❓ Как это работает?</b>

    <b>1️⃣ Поделитесь ссылкой</b>
    <blockquote>
    Отправьте её другу или покажите QR-код.
    </blockquote>

    <b>2️⃣ Друг регистрируется по ссылке</b>
    <blockquote>
    { $invitee_reward_amount ->
        [0] И закрепляется за вами.
       *[other] И сразу получает +{ $invitee_reward_amount } { $invitee_reward_type ->
            [POINTS] { $invitee_reward_amount ->
                [one] балл
                [few] балла
               *[other] баллов
            }
           *[EXTRA_DAYS] { $invitee_reward_amount ->
                [one] бонусный день
                [few] бонусных дня
               *[other] бонусных дней
            }
        }.
    }
    </blockquote>

    <b>3️⃣ Друг оплачивает подписку</b>
    <blockquote>
    Вы получаете { $reward_terms }. { $accrual_strategy ->
        [EVERY_PAYMENT] За каждую его оплату: покупку, продление и смену тарифа.
       *[FIRST_PAYMENT] Только за его первую оплату.
    }
    { $reward_levels }
    </blockquote>

    { $reward_type ->
        [POINTS] <b>4️⃣ Обменивайте баллы</b>
        <blockquote>
        Нажмите «Вывести баллы» и напишите в поддержку — администратор проведёт обмен.
        </blockquote>
       *[EXTRA_DAYS] <b>4️⃣ Применяйте бонусные дни</b>
        <blockquote>
        Добавьте их к любой своей подписке.
        </blockquote>
    }

    <i>Пригласить можно только того, кто ещё не пользуется сервисом. Пробные подписки и подписки по промокоду наград не приносят. Если платёж вернут, награда за него аннулируется.</i>
frg-referral-terms = { $reward_strategy ->
        [PERCENT] { $reward_type ->
            [POINTS] { $amount }% от оплаты друга баллами
           *[EXTRA_DAYS] { $amount }% от купленных другом дней — бонусными днями
        }
       *[AMOUNT] { $reward_type ->
            [POINTS] +{ $amount } { $amount ->
                [one] балл
                [few] балла
               *[other] баллов
            } за оплату друга
           *[EXTRA_DAYS] +{ $amount } { $amount ->
                [one] день
                [few] дня
               *[other] дней
            } за оплату друга
        }
    }
frg-referral-levels = Друзья ваших друзей тоже приносят награду:
frg-referral-level = { $level } уровень — { $terms }
msg-referrals-redeem-target = Бонусных дней: { $bonus_days }. Выберите подписку, к которой их добавить:

btn-referrals =
    .about = Как это работает?
    .about-icon = ❓
    .copy = Скопировать ссылку
    .copy-icon = 📋
    .share = Поделиться ссылкой
    .share-icon = 📩
    .withdraw = Вывести баллы
    .withdraw-icon = 💎
    .redeem = Обменять бонусные дни
    .redeem-icon = 🎁
    .qr = QR-код
    .qr-icon = 🧾
    .reset-code = Новая реферальная ссылка
    .reset-code-icon = 🔄

btn-back =
    .general = Назад
    .general-icon = ⬅️

ntf-subscription =
    .gone = ❌ Эта подписка больше недоступна.

ntf-devices =
    .deleted = ✅ Устройство удалено.
    .all-deleted = ✅ Все устройства удалены.
    .reissued = ✅ Ссылка подключения перевыпущена.
    .failed = ❌ Что-то пошло не так. Попробуйте позже.
    .delete-cooldown = ⏳ Удалить устройство можно будет через { $wait }.
    .delete-all-cooldown = ⏳ Удалить все устройства можно будет через { $wait }.
    .reissue-cooldown = ⏳ Перевыпустить ссылку подключения можно будет через { $wait }.

ntf-access =
    .restricted = 🚧 Технические работы. Попробуйте позже.
    .registration-disabled = ❌ Сервис недоступен для новых пользователей.
    .invite-only = ❌ Сервис доступен только по приглашениям.
    .payments-disabled = 🚧 Оплата временно недоступна! Вы получите уведомление после восстановления.

ntf-common =
    .unknown-error = ❌ Что-то пошло не так. Попробуйте ещё раз.
    .trial-unavailable = ⚠️ Пробный период недоступен.
    .trial-activated = ✅ Пробная подписка активирована.
    .connect-not-available = ⚠️ { $status ->
        [LIMITED] Вы израсходовали весь доступный объём трафика. { $is_trial ->
            [1] { $reset_in ->
                [none] Оформите подписку, чтобы продолжить пользоваться сервисом!
               *[other] Трафик будет восстановлен через { $reset_in }. Вы также можете оформить подписку, чтобы пользоваться сервисом без ограничений.
            }
           *[0] { $reset_in ->
                [none] Продлите подписку, чтобы сбросить трафик и продолжить пользоваться сервисом!
               *[other] Трафик будет восстановлен через { $reset_in }. Вы также можете продлить подписку, чтобы сбросить трафик.
            }
        }
        [EXPIRED] { $is_trial ->
            [1] Бесплатный пробный период завершён. Оформите подписку, чтобы продолжить пользоваться сервисом.
           *[0] Срок действия вашей подписки истёк. Продлите подписку или оформите новую.
        }
       *[other] Произошла ошибка при проверке статуса или подписка была отключена. Обратитесь в поддержку.
    }
    .access-restricted = ❌ Доступ ограничен.

ntf-purchase =
    .stars-rejected = Этот заказ уже нельзя оплатить. Начните покупку заново.
    .plan-unavailable = ❌ Этот тариф больше недоступен — выберите другой.
    .renew-plan-unavailable = ❌ Текущий план устарел и недоступен для продления.
    .limit-reached = ❌ Достигнут лимит подписок.
    .method-unavailable = ❌ Этот способ оплаты сейчас недоступен.
    .discount-used = ⚠️ Скидка уже использована — проверьте новую цену.
    .failed = ❌ Не удалось создать платёж. Попробуйте позже.
    .no-plans = ❌ Нет доступных тарифов.
    .no-methods = ❌ Нет доступных способов оплаты.

msg-purchase-plan = <b>💳 Выберите тариф</b>
msg-purchase-duration =
    <b>⏳ Выберите длительность</b>

    { $plan_details }

    { $discount_notice }

    { $plan_changed_notice }
msg-purchase-method =
    <b>💳 Выберите способ оплаты</b>

    { $plan_details }

    { $discount_notice }
frg-purchase-plan =
    <b>{ $plan_name }</b>:
    <blockquote>
    { $description }
    • <b>Лимит трафика</b>: { $traffic_limit ->
        [0] Безлимит
       *[other] { $traffic_limit } ГБ
    }
    • <b>Лимит устройств</b>: { $device_limit ->
        [0] Безлимит
       *[other] { $device_limit }
    }
    • <b>Длительность</b>: { $period }
    </blockquote>
frg-purchase-discount = <i>Цены указаны с учётом вашей скидки { $percent }%</i>
frg-purchase-plan-changed = <i>ℹ️ Условия тарифа изменились с момента покупки. После продления подписка перейдёт на новые условия — они указаны выше.</i>
frg-purchase-type-notice = { $purchase_type ->
        [RENEW] <i>⚠️ Текущая подписка будет <u>продлена</u> на выбранный срок.</i>
       *[other] <i>⚠️ Текущая подписка будет <u>заменена</u> выбранным тарифом. Неиспользованная часть оплаты добавится к новому сроку.</i>
    }
msg-purchase-confirm =
    <b>🛒 { $purchase_type ->
        [RENEW] Подтверждение продления
        [CHANGE] Подтверждение смены тарифа
       *[other] Подтверждение покупки
    }</b>

    <blockquote>
    • <b>Тариф</b>: { $plan_name }
    • <b>Лимит трафика</b>: { $traffic_limit ->
        [0] Безлимит
       *[other] { $traffic_limit } ГБ
    }
    • <b>Лимит устройств</b>: { $device_limit ->
        [0] Безлимит
       *[other] { $device_limit }
    }
    • <b>Длительность</b>: { $period }
    • <b>Способ оплаты</b>: { $method }
    • <b>Без скидки</b>: <s>{ $original_price } { $currency_symbol }</s>
    • <b>К оплате</b>: { $price } { $currency_symbol }
    </blockquote>

    { $type_notice }

    { $plan_changed_notice }

    { $terms_notice }
frg-purchase-terms-notice = <i>Оплачивая, вы принимаете условия — /terms</i>
msg-purchase-pay = Заказ создан. Нажмите кнопку ниже, чтобы оплатить.
msg-purchase-link-choice = У вас уже есть подписка { $plan_name }. Продлить её или купить ещё одну?

btn-purchase =
    .duration = { $period } — { $price } { $currency_symbol }
    .back-plans = Назад к выбору тарифа
    .back-plans-icon = ⬅️
    .back-duration = Изменить длительность
    .back-duration-icon = ⬅️
    .back-method = Изменить способ оплаты
    .back-method-icon = ⬅️
    .method = { $gateway } — { $price } { $currency_symbol }
    .pay = Оплатить
    .pay-icon = 💳
    .go-to-payment = Перейти к оплате
    .go-to-payment-icon = 💳
    .menu = Главное меню
    .menu-icon = ↩️
    .link-renew = Продлить: { $subscription }
    .link-renew-icon = 🔄
    .link-new = Купить новую
    .link-new-icon = 💸

msg-payment-result-success =
    <b>✅ Оплата прошла успешно!</b>

    { $purchase_type ->
    [RENEW] Подписка { $plan_name } продлена.
    [CHANGE] Тариф изменён на { $plan_name }.
    *[NEW] Подписка { $plan_name } активирована. Чтобы начать пользоваться сервисом, нажмите «Подключиться» и следуйте инструкциям!
    }
msg-payment-result-failed =
    <b>❌ Произошла ошибка!</b>

    Не волнуйтесь, техподдержка уже уведомлена и свяжется с вами в ближайшее время. Приносим извинения за неудобства.
msg-payment-result-canceled = <b>Оплата отменена.</b> Заказ больше не действует — можно оформить его заново.

btn-payment-result =
    .subscription = Моя подписка
    .subscription-icon = 💳
    .retry = Попробовать снова
    .retry-icon = 🔄
    .menu = Главное меню
    .menu-icon = ↩️

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
    .no-subscription = ❌ У вас нет подписки, к которой можно добавить бонусные дни.
    .days-redeemed = ✅ Бонусные дни успешно добавлены к вашей подписке.
    .redeem-failed = ❌ Бонусные дни нельзя добавить к этой подписке.
    .code-reset = ✅ Ваша реферальная ссылка обновлена. Старая больше не будет работать.
    .reset-cooldown = ⏳ Обновить реферальную ссылку можно будет через { $wait }.

ntf-promocode =
    .not-found = ❌ Промокод не найден.
    .expired = ❌ Срок действия промокода истёк.
    .already-activated = ❌ Вы уже активировали этот промокод.
    .discount-not-better = ⚠️ Промокод не применён: ваша текущая скидка такая же или больше.
    .not-available = ❌ Этот промокод вам недоступен.
    .no-target-subscription = ❌ У вас нет активной подписки, к которой можно применить этот промокод.
    .activated = ✅ Промокод активирован!
    .activation-failed = ❌ Не удалось активировать промокод. Попробуйте позже.
    .too-many-attempts = ⏳ Слишком много попыток. Попробуйте через минуту.

msg-promocode-input =
    <b>🎟 Промокод</b>

    Отправьте промокод сообщением.
msg-promocode-target =
    <b>🎟 Промокод</b>

    Выберите подписку, к которой применить промокод.
msg-promocode-confirm =
    <b>🎟 Промокод <code>{ $promo_code }</code></b>

    🎁 Вы получите: { $promo_reward_type ->
        [DURATION] <b>+{ $promo_reward } { $promo_reward ->
            [one] день
            [few] дня
           *[other] дней
        }</b> к сроку подписки.
        [TRAFFIC] <b>+{ $promo_reward } ГБ</b> к лимиту трафика.
        [DEVICES] <b>+{ $promo_reward } { $promo_reward ->
            [one] устройство
            [few] устройства
           *[other] устройств
        }</b> к лимиту устройств.
        [SUBSCRIPTION] подписку <b>{ $promo_plan_name }</b> на <b>{ $promo_reward } { $promo_reward ->
            [one] день
            [few] дня
           *[other] дней
        }</b>.
        [PERSONAL_DISCOUNT] постоянную <b>скидку { $promo_reward }%</b> на все покупки.
        [PURCHASE_DISCOUNT] <b>скидку { $promo_reward }%</b> на следующую покупку.
       *[other] награду на ваш аккаунт.
    }

    { $promo_reward_type ->
        [TRAFFIC] ⚠️ <i>Бонус сохранится при продлении, но сгорит при смене тарифа.</i>
        [DEVICES] ⚠️ <i>Бонус сохранится при продлении, но сгорит при смене тарифа.</i>
       *[other] { "" }
    }

    Нажмите «Применить» для активации.
msg-promocode-confirm-will-replace = ⚠️ <i>Промокод заменит вашу текущую подписку.</i>

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
    .unsubscribe = Отписаться от рассылки
    .resubscribe = Снова получать акции
    .resubscribe-icon = 🔔

ntf-broadcast =
    .unsubscribed = Вы больше не будете получать акции. Сервисные сообщения продолжат приходить.
    .resubscribed = ✅ Вы снова будете получать акции.
    .promo-gone = ❌ Это предложение больше недоступно.
    .start-required = Нажмите /start, чтобы продолжить.

ntf-requirements =
    .channel = Чтобы продолжить, подпишитесь на наш канал.
    .channel-not-found = ⚠️ Пока не видим подписку. Подпишитесь и попробуйте ещё раз.
    .trial-paused = Вы отписались от канала, поэтому пробный период приостановлен. Подпишитесь снова, чтобы продолжить.
    .trial-resumed = Вы снова подписаны на канал — пробный период возобновлён.

btn-requirements =
    .subscribe = Подписаться
    .subscribe-icon = ❤️
    .check = Я подписался
    .check-icon = ✅

ntf-cabinet-login =
    .link = Нажмите кнопку, чтобы войти в веб-кабинет. Ссылка одноразовая и действует 5 минут.
    .expired = ⚠️ Ссылка для входа устарела. Запросите новую в кабинете.
    .unavailable = ⚠️ Вход в кабинет через Telegram сейчас недоступен. Попробуйте позже или войдите другим способом.

btn-cabinet-login =
    .open = Войти в кабинет
    .open-icon = 🌐

ntf-cabinet-link =
    .link = Нажмите кнопку, чтобы привязать этот Telegram к аккаунту в веб-кабинете. Ссылка одноразовая и действует 5 минут.
    .expired = Ссылка для привязки устарела. Запросите новую в кабинете.

btn-cabinet-link =
    .open = Привязать к кабинету
    .open-icon = 🔗

time-unit =
    .day = { $value ->
        [one] { $value } день
        [few] { $value } дня
       *[other] { $value } дней
    }
    .month = { $value ->
        [one] { $value } месяц
        [few] { $value } месяца
       *[other] { $value } месяцев
    }
    .year = { $value ->
        [one] { $value } год
        [few] { $value } года
       *[other] { $value } лет
    }
    .hour = { $value } ч
    .minute = { $value } мин

inline-invite =
    .title = Пригласить друга
    .description = Нажмите, чтобы отправить пригласительную ссылку!
    .message =
        🚀 Привет! Хочешь стабильный и быстрый VPN?

        { $bot_name } — поможет тебе с этим!

        ↘️ ЖМИ КНОПКУ И ПОПРОБУЙ БЕСПЛАТНО!
    .start = Присоединиться
    .start-icon = 🚀
