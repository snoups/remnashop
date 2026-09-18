msg-main-menu = Main menu, { $name }!
msg-window-gone = This screen is no longer available.
msg-menu-devices = Your devices ({ $current_count }/{ $max_count })
msg-menu-devices-confirm-delete = Delete this device?
msg-menu-devices-confirm-delete-all = Delete ALL devices?
msg-menu-devices-confirm-reissue = Reissue the connection link? The old link will stop working.

btn-menu =
    .connect = Connect
    .connect-not-available = Connection unavailable
    .trial = Try for free
    .trial-paid = Trial — { $trial_price }
    .devices = 📱 Devices
    .subscription = 💳 Subscription
    .support = 🆘 Support
    .web-cabinet = 🌐 Web cabinet

btn-devices =
    .item = { $platform_icon } { $platform } ({ $device_model }) — { $created_at }
    .empty = No connected devices
    .delete-all = Delete all devices
    .reissue = Reissue link
    .confirm-delete = Yes, delete
    .confirm-reissue = Yes, reissue
    .cancel-reissue = Cancel

btn-back =
    .general = ⬅️ Back

ntf-devices =
    .deleted = Device deleted.
    .all-deleted = All devices deleted.
    .reissued = Connection link reissued.

ntf-common =
    .cooldown-active = Please wait until { $available_at } before repeating this action.
    .trial-unavailable = Trial is not available.
    .connect-not-available = Connection is not available.
    .access-restricted = Access is restricted.

ntf-promocode =
    .not-found = Promocode not found.
    .expired = This promocode has expired.
    .already-activated = You've already activated this promocode.
    .not-available = This promocode isn't available to you.
    .no-target-subscription = You have no active subscription to apply this promocode to.
    .activated = Promocode activated!
    .activation-failed = Failed to activate the promocode. Please try again later.

msg-promocode-input = Enter your promocode:
msg-promocode-target = Choose which subscription to apply the promocode to:
msg-promocode-confirm = Code: { $promo_code }
    Reward: { $promo_reward_type } { $promo_reward }
msg-promocode-confirm-will-replace = ⚠️ This will replace your current subscription.

btn-promocode =
    .confirm = ✅ Apply
    .cancel = ❌ Cancel

msg-subscription-main = The subscription purchase section is coming soon. Promocode activation is available now.

btn-subscription =
    .promocode = 🎟 Activate promocode

platform-icon =
    .ios = 📱
    .android = 🤖
    .windows = 🖥
    .macos = 💻
    .linux = 🐧
    .default = ❓
