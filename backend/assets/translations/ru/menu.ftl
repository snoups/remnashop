msg-main-menu = Главное меню, { $user_name }!
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
    .subscription = Подписка
    .subscription-icon = 💳
    .support = Поддержка
    .support-icon = 🆘
    .web-cabinet = Веб-кабинет
    .web-cabinet-icon = 🌐

btn-devices =
    .item = { $platform_icon } { $platform } ({ $device_model }) — { $created_at }
    .empty = Нет подключённых устройств
    .delete-all = Удалить все устройства
    .reissue = Перевыпустить ссылку
    .confirm-delete = Да, удалить
    .confirm-reissue = Да, перевыпустить
    .cancel-reissue = Отмена

btn-back =
    .general = Назад
    .general-icon = ⬅️

ntf-devices =
    .deleted = Устройство удалено.
    .all-deleted = Все устройства удалены.
    .reissued = Ссылка подключения перевыпущена.

ntf-access =
    .restricted = Сервис временно закрыт на техработы. Загляните позже.
    .registration-disabled = Регистрация сейчас закрыта.
    .invite-only = Регистрация только по приглашению. Попросите у друга реферальную ссылку.
    .payments-disabled = Оплата временно недоступна. Мы напишем, когда она вернётся.
    .payments-restored = Оплата снова доступна — можно завершить покупку.

ntf-common =
    .cooldown-active = Повторить это действие можно после { $available_at }.
    .trial-unavailable = Пробный период недоступен.
    .connect-not-available = Подключение недоступно.
    .access-restricted = Доступ ограничен.

ntf-promocode =
    .not-found = Промокод не найден.
    .expired = Срок действия промокода истёк.
    .already-activated = Вы уже активировали этот промокод.
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

msg-subscription-main = Раздел покупки подписки скоро появится. Пока доступна активация промокодов.

btn-subscription =
    .promocode = Активировать промокод
    .promocode-icon = 🎟

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
    .confirmed = Вход подтверждён. Вернитесь в браузер.
    .expired = Ссылка для входа устарела. Запросите новую в кабинете.

ntf-cabinet-login-ask = Войти в веб-кабинет? Запрос с IP { $ip }, { $agent }. Если это не вы, проигнорируйте сообщение.

btn-cabinet-login =
    .confirm = Подтвердить
