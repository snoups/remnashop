msg-main-menu = Главное меню, { $name }!
msg-window-gone = Этот экран больше недоступен.
msg-menu-devices = Ваши устройства ({ $current_count }/{ $max_count })
msg-menu-devices-confirm-delete = Удалить это устройство?
msg-menu-devices-confirm-delete-all = Удалить ВСЕ устройства?
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

ntf-common =
    .cooldown-active = Подождите до { $available_at }, прежде чем повторить это действие.
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
