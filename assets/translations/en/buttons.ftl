btn-back = 
    .general = ⬅️ Back
    .menu = ↩️ Main menu
    .menu-return = ↩️ Return to main menu
    .dashboard = ↩️ Return to dashboard

btn-common =
    .notification-close = ❌ Close
    .devices-empty = ⚠️ You have no connected devices
    .cancel = Cancel

    .squad-choice = { $selected -> 
    [1] 🔘
    *[0] ⚪
    } { $name }

    .duration = ⌛ { $value ->
    [0] { unlimited }
    *[other] { unit-day }
    }

btn-devices =
    .delete-all = 🗑 Delete all devices
    .reissue = 🔄 Reissue subscription
    .confirm-delete = ✅ Yes, delete
    .confirm-reissue = ✅ Yes, reset
    .cancel-reissue = ❌ No

btn-remnashop-info =
    .release-latest = 👀 View
    .how-upgrade = ❓ How to upgrade
    .github = ⭐ GitHub
    .telegram = 👪 Telegram
    .donate = 💰 Support developer
    .guide = ❓ Guide

btn-requirement =
    .rules-accept = ✅ Accept rules
    .channel-join = ❤️ Join channel
    .channel-confirm = ✅ Confirm

btn-menu =
    .trial = 🎁 TRY FOR FREE
    .connect = 🚀 Connect
    .devices = 📱 Devices
    .subscription = 💳 Subscription
    .invite = 👥 Invite
    .support = 🆘 Support
    .dashboard = 🛠 Dashboard

    .connect-not-available =
    ⚠️ { $status -> 
    [LIMITED] TRAFFIC LIMIT EXCEEDED
    [EXPIRED] SUBSCRIPTION EXPIRED
    *[OTHER] YOUR SUBSCRIPTION DOES NOT WORK
    } ⚠️

btn-invite =
    .about = ❓ More about reward
    .copy = 📋 Copy link
    .send = 📩 Invite
    .qr = 🧾 QR code
    .withdraw-points = 💎 Exchange points

btn-dashboard =
    .statistics = 📊 Statistics
    .users = 👥 Users
    .broadcast = 📢 Broadcast
    .promocodes = 🎟 Promo codes
    .access = 🔓 Access mode
    .remnawave = 🌊 RemnaWave
    .remnashop = 🛍 RemnaShop
    .importer = 📥 Import users

btn-statistics =
    .users = 👥 Users
    .subscriptions = 💳 Subscriptions
    .transactions = 🧾 Transactions
    .promocodes = 🎁 Promo codes
    .referrals = 👪 Referrals

    .subscription-page =
    { $page ->
        [0] { $is_current ->
            [1] [ General statistics ]
            *[0] General statistics
        }
        *[other] { $is_current ->
            [1] [ { $plan_name } ]
            *[0] { $plan_name }
        }
    }

    .transaction-page =
    { $page ->
        [0] { $is_current ->
            [1] [ General statistics ]
            *[0] General statistics
        }
        *[other] { $is_current ->
            [1] [ { gateway-type } ]
            *[0] { gateway-type }
        }
    }

btn-users =
    .search = 🔍 Search user
    .recent-registered = 🆕 Recently registered
    .recent-activity = 📝 Recently active
    .blacklist = 🚫 Blacklist
    .unblock-all = 🔓 Unblock all

btn-user =
    .discount = 💸 Discount
    .discount-personal = 👤 Personal discount
    .discount-purchase = 🎟 Next purchase discount
    .points = 💎 Points
    .statistics = 📊 Statistics
    .referrals = 👪 Referrals
    .message = 📩 Message
    .role = 👮‍♂️ Role
    .transactions = 🧾 Transactions
    .give-access = 🔑 Access to plans
    .current-subscription = 💳 Current subscription
    .subscription-traffic-limit = 🌐 Traffic limit
    .subscription-device-limit = 📱 Device limit
    .subscription-expire-time = ⏳ Expire time
    .subscription-squads = 🔗 Squads
    .subscription-traffic-reset = 🔄 Reset traffic
    .subscription-devices = 🧾 Device list
    .subscription-url = 📋 Copy link
    .subscription-set = ✅ Set subscription
    .subscription-delete = ❌ Delete
    .message-preview = 👀 Preview
    .message-confirm = ✅ Send
    .sync = 🌀 Sync
    .sync-remnawave = 🌊 Use Remnawave data
    .sync-remnashop = 🛍 Use Remnashop data
    .give-subscription = 🎁 Give subscription
    .subscription-internal-squads = ⏺️ Internal squads
    .subscription-external-squads = ⏹️ External squad

    .allowed-plan-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $plan_name }

    .subscription-active-toggle = { $is_active ->
    [1] 🔴 Disable
    *[0] 🟢 Enable
    }

    .transaction = { $status ->
    [PENDING] 🕓
    [COMPLETED] ✅
    [CANCELED] ❌
    [REFUNDED] 💸
    [FAILED] ⚠️
    *[OTHER] { $status }
    } { $created_at }
    
    .trial-toggle = { $is_trial_available ->
    [1] 🧪 Trial: available
    *[0] 🧪 Trial: not available
    }

    .block = { $is_blocked ->
    [1] 🔓 Unblock
    *[0] 🔒 Block
    }

btn-broadcast =
    .list = 📄 All broadcasts
    .all = 👥 Everyone
    .plan = 📦 By plan
    .subscribed = ✅ With subscription
    .unsubscribed = ❌ Without subscription
    .expired = ⌛ Expired
    .trial = ✳️ With trial
    .content = ✉️ Edit content
    .buttons = ✳️ Edit buttons
    .preview = 👀 Preview
    .confirm = ✅ Start broadcast
    .refresh = 🔄 Refresh data
    .viewing = 👀 Viewing
    .cancel = ⛔ Stop broadcast
    .delete = ❌ Delete sent

    .plan-title = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }
    
    .button-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    }
    
    .title = { $status ->
    [PROCESSING] ⏳
    [COMPLETED] ✅
    [CANCELED] ⛔
    [DELETED] ❌
    [ERROR] ⚠️
    *[OTHER] { $status }
    } { $created_at }
    
btn-goto =
    .subscription = 💳 Buy subscription
    .promocode = 🎟 Activate promo code
    .invite = 👥 Invite
    .subscription-renew = 🔄 Renew subscription
    .user-profile = 👤 Go to user
    .referrer-profile = 🤝 Go to referrer
    .contact-support = 📩 Go to support

btn-promocodes =
    .list = 📃 List of promo codes
    .search = 🔍 Search promo code
    .create = 🆕 Create
    .delete = 🗑️ Delete
    .edit = ✏️ Edit

btn-access =
    .mode = { access-mode }
    .conditions = ⚙️ Access conditions
    .rules = ✳️ Accept rules
    .channel = ❇️ Channel subscription

    .payments-toggle = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } Payments

    .registration-toggle = { $enabled ->
    [1] 🔘
    *[0] ⚪
    } Registration

    .condition-toggle = { $enabled ->
    [1] 🔘 Enabled
    *[0] ⚪ Disabled
    }

btn-remnashop =
    .admins = 👮‍♂️ Admins
    .gateways = 🌐 Payment systems
    .referral = 👥 Referral system
    .advertising = 🎯 Advertising
    .plans = 📦 Plans
    .notifications = 🔔 Notifications
    .logs = 📄 Logs
    .menu-editor = 🎛 Extra buttons

btn-menu-editor =
    .text = 🏷️ Text
    .availability = ✴️ Availability
    .type = 🔖 Type
    .payload = 📄 Data
    .confirm = ✅ Save

    .button = { $is_active -> 
        [1] 🟢 
        *[0] 🔴 
    } { $text }
    
    .active = { $is_active -> 
        [1] 🟢 Enabled
        *[0] 🔴 Disabled
    }
    
btn-gateway =
    .title = { gateway-type }
    .setting = { $field }
    .webhook-copy = 📋 Copy webhook
    .test = 🐞 Test
    .default-currency = 💸 Default currency
    .placement = 🔢 Change position

    .active = { $is_active ->
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }

    .default-currency-choice = { $enabled -> 
    [1] 🔘
    *[0] ⚪
    } { $symbol } { $currency }

btn-referral =
    .level = 🔢 Level
    .reward-type = 🎀 Reward type
    .accrual-strategy = 📍 Accrual condition
    .reward-strategy = ⚖️ Accrual form
    .reward = 🎁 Reward
    
    .enable = { $is_enable -> 
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }

    .level-choice = { $type -> 
    [1] 1️⃣
    [2] 2️⃣
    [3] 3️⃣
    *[OTHER] { $type }
    }

    .reward-choice = { $type -> 
    [POINTS] 💎 Points
    [EXTRA_DAYS] ⏳ Days
    *[OTHER] { $type }
    }

    .accrual-strategy-choice = { $type -> 
    [ON_FIRST_PAYMENT] 💳 First payment
    [ON_EACH_PAYMENT] 💸 Each payment
    *[OTHER] { $type }
    }

    .reward-strategy-choice = { $type -> 
    [AMOUNT] 🔸 Fixed
    [PERCENT] 🔹 Percentage
    *[OTHER] { $type }
    }

btn-notifications =
    .user = 👥 User
    .system = ⚙️ System
    
    .user-choice = { $enabled ->
    [1] 🔘
    [0] ⚪
    } { $type ->
    [EXPIRES_IN_3_DAYS] Subscription expires (3 days)
    [EXPIRES_IN_2_DAYS] Subscription expires (2 days)
    [EXPIRES_IN_1_DAY] Subscription expires (1 day)
    [EXPIRED] Subscription expired
    [EXPIRED_1_DAY_AGO] Subscription expired (1 day ago)
    [LIMITED] Traffic exhausted
    [REFERRAL_ATTACHED] Referral attached
    [REFERRAL_REWARD_RECEIVED] Referral reward received
    *[OTHER] { $type }
    }

    .system-choice = { $enabled -> 
    [1] 🔘
    [0] ⚪
    } { $type ->
    [BOT_LIFECYCLE] Bot lifecycle
    [BOT_UPDATE] Bot updates
    [USER_REGISTERED] User registered
    [SUBSCRIPTION] Subscription purchased
    [PROMOCODE_ACTIVATED] Promo code activated
    [TRIAL_ACTIVATED] Trial activated
    [NODE_STATUS_CHANGED] Node status
    [NODE_TRAFFIC_REACHED] Node traffic
    [USER_FIRST_CONNECTION] First connection
    [USER_DEVICES_UPDATED] User devices
    [USER_REVOKED_SUBSCRIPTION] Subscription revoked
    *[OTHER] { $type }
    }

btn-plans =
    .statistics = 📊 Statistics
    .create = 🆕 Create
    .save = ✅ Save
    .create = ✅ Create plan
    .delete = ❌ Delete
    .name = 🏷️ Name
    .description = 💬 Description
    .description-remove = ❌ Remove current description
    .tag = 📌 Tag
    .tag-remove = ❌ Remove current tag
    .type = 🔖 Type
    .availability = ✴️ Availability
    .durations-prices = ⏳ Durations and 💰 Prices
    .traffic = 🌐 Traffic
    .devices = 📱 Devices
    .allowed = 👥 Allowed users
    .squads = 🔗 Squads
    .internal-squads = ⏺️ Internal squads
    .external-squads = ⏹️ External squad
    .allowed-user = { $id }
    .duration-add = 🆕 Add duration
    .price-choice = 💸 { $price } { $currency }
    .export = 📤 Export
    .import = 📥 Import
    .exporting = 📤 Exporting
    .importing = 📥 Importing
    .url = 📋 Copy plan link

    .trial = { $is_trial ->
    [1] 🔘
    *[0] ⚪
    } Trial 

    .export-choice = { $selected ->
    [1] 🔘
    *[0] ⚪
    } { $name }

    .title = { $is_active ->
    [1] 🟢
    *[0] 🔴 
    } { $name }

    .active = { $is_active -> 
    [1] 🟢 Enabled
    *[0] 🔴 Disabled
    }
    
    .type-choice = { $type -> 
    [TRAFFIC] 🌐 Traffic
    [DEVICES] 📱 Devices
    [BOTH] 🔗 Traffic + Devices
    [UNLIMITED] ♾️ Unlimited
    *[OTHER] { $type }
    }

    .availability-choice = { $type -> 
    [ALL] 🌍 For everyone
    [NEW] 🌱 For new
    [EXISTING] 👥 For clients
    [INVITED] ✉️ For invited
    [ALLOWED] 🔐 For allowed
    [LINK] 🔗 By link
    *[OTHER] { $type }
    }

    .traffic-strategy-choice = { $selected ->
    [1] 🔘 { traffic-strategy }
    *[0] ⚪ { traffic-strategy }
    }

    
btn-remnawave =
    .users = 👥 Users
    .hosts = 🌐 Hosts
    .nodes = 🖥️ Nodes
    .inbounds = 🔌 Inbounds

btn-importer =
    .from-xui = 💩 Import from 3X-UI
    .from-xui-shop = 🛒 Bot 3xui-shop
    .sync = 🌀 Start sync
    .squads = 🔗 Internal squads
    .import-all = ✅ Import all
    .import-active = ❇️ Import active

btn-subscription =
    .plan = 💳 Go to subscription
    .new = 💸 Buy subscription
    .renew = 🔄 Renew
    .change = 🔃 Change
    .promocode = 🎟 Activate promo code
    .payment-method = { gateway-type } | { $final_amount ->
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }
    .pay = 💳 Pay
    .get = 🎁 Get for free
    .back-plans = ⬅️ Back to plan selection
    .back-duration = ⬅️ Change duration
    .back-payment-method = ⬅️ Change payment method
    .connect = 🚀 Connect

    .duration = { $period } | { $final_amount -> 
    [0] 🎁
    *[HAS] { $final_amount }{ $currency }
    }

btn-promocode =
    .code = 🏷️ Code
    .type = 🔖 Reward type
    .availability = ✴️ Availability
    .reward = 🎁 Reward
    .lifetime = ⌛ Lifetime
    .allowed = 👥 Allowed users
    .confirm = ✅ Confirm
    
    .active = { $is_active -> 
    [1] 🟢
    *[0] 🔴
    } Status