<div align="center" markdown>

<p align="center">
    <u><b>ENGLISH</b></u> •
    <a href="https://github.com/snoups/remnashop/blob/main/README.ru_RU.md"><b>РУССКИЙ</b></a>
</p>


![remnashop](https://github.com/user-attachments/assets/9c974da1-db66-4fc7-a1e5-0d4a77ad6d09)

**This project is a Telegram bot for selling VPN subscriptions, integrated with Remnawave.**

[![Static Badge](https://img.shields.io/badge/public_group-white?style=social&logo=Telegram&logoColor=blue&logoSize=auto&labelColor=white&link=https%3A%2F%2Ft.me%2Fsn0ups)](https://t.me/remna_shop)
[![Static Badge](https://img.shields.io/badge/remnawave-white?style=social&logo=Telegram&logoColor=blue&logoSize=auto&labelColor=white&link=https%3A%2F%2Ft.me%2Fsnoups)](https://t.me/+xQs17zMzwCY1NzYy)
![GitHub Repo stars](https://img.shields.io/github/stars/snoups/remnashop)
</div>

# ✨ Features

- **📦 Plans**
    > Unique architecture that allows flexible plan creation and precise availability control.
    
    > Supports any limits — by traffic, devices, both, or unlimited.

    > Control plan availability for specific user types or individual users.

    > Link internal and external squads to specific plans.

    > Support for any subscription duration.

    > Ability to make any duration free of charge.

    > Multi-currency pricing for each duration.

    > Customizable plan display order.

    > Built-in plan configurator directly in the bot interface.

- **🎟️ Promocodes**
    > Multiple reward types: extra days, traffic, subscription activation for a chosen plan, personal discount, or discount for the next purchase.

    > Configurable lifetime: by time or number of activations.

    > Convenient promocode configurator.

- **📢 Broadcasts**
    > View all previously sent messages with content preview.

    > Send by user category: all users, by plan, with subscription, without subscription, expired, or trial.

    > Supports photos, videos, GIFs, and stickers.

    > Supports HTML tags for message formatting.

    > Preview messages before sending.

    > Option to stop an active broadcast.

    > Option to delete sent messages.

- **🔔 Notifications**
    > Configurable notification system directly in the bot interface.

    > User notifications: subscription expiring, expired, traffic exhausted.

    > System notifications: bot lifecycle, bot update, new user registration, subscription activation, promocode activation, get trial, node status, first user connection, device add/remove events.

- **🧪 Trial**
    > Configurable trial setup through the plan configurator.

    > Supports any limits.

    > Supports multiple trial plans.

    > Separate internal and external squad assignments.

    > Availability settings for users who joined via referral or ad links.

- **👥 Referral System**
    > Detailed referral statistics.

    > Referral system configurator.
    
    > Reward customization: money, extra days, or automatically generated promocodes.

    > Two-level referral support.

- **💳 Flexible Payment System**
    > Supports multiple payment gateways: Telegram Stars, YooKassa, YooMoney, Cryptomus, Heleket, CryptoPay, RoboKassa.

    > Payment gateway configurator.

    > Default currency setup.

    > Ability to run test payments for selected gateways.

    > Customizable display order for payment methods.

- **📱 Device Management**
    > Allows users to manage their connected devices (only with active subscriptions and within device limits).

    > Configurable cooldown for device reset actions.

- **🏷️ Discount System**
    > Two discount types: personal and next purchase.

    > Discounts do not stack — the largest discount is applied.

    > Discount display on purchase buttons.

- **🔐 Access Mode**
    > Five access modes: full restriction, open for all, invite-only, purchase restricted, and register restricted.

    > Automatic notifications for users who attempted to purchase during restricted mode.

    > Conditional access support: rule acceptance and channel subscription.

- **📈 Ad Links**
    > Create links to track traffic sources and user acquisition.

    > Built-in link configurator.

    > View detailed analytics for each link.

- **📊 Statistics**
    > Detailed analytics by category: users, transactions, subscriptions, plans, promocodes, referrals.

- **👤 User Editor**
    > Complete user information: profile data, stats, subscription, transactions.

    > Edit personal discounts.

    > Manage roles: developer, admin, user.

    > Block users.

    > Grant plan access for purchase.

    > Full subscription editor: modify limits, reset traffic, manage devices, squads, expiration date, toggle subscription status, delete, or get connection link.

    > View all banned users.

    > Search by name, username and id.

    > View recent registrations and active users.

    > Quick access via forwarded messages, system notifications, or main menu search.

- **🔄 User Synchronization**
    > Automatic synchronization with the panel.

    > Edit user data both from the bot and the panel.

- **🔍 User Audit**
    > View full user activity history.
    
- **🌐 Internationalization**
    > Ability to set unique banners for each locale.

    > Support for interface translations into multiple languages.

    > Automatic language detection on the user's first launch and after subsequent changes.

- **🧭 Migration**
    > Seamless migration from other bots.
  
- **🪄 MiniApp Support (maposia)**


# ⚙️ Installation and configuration

Install Docker if not installed yet.
```
sudo curl -fsSL https://get.docker.com | sh
```


## Step 1 – Download required files

Create the project directory
```
mkdir /opt/remnashop && cd /opt/remnashop
```

Download `docker-compose.yml` compose-file and `.env` by running these commands:

- Get `docker-compose.yml` file:

    - For external panel **(the bot is hosted on a separate server from the panel)**:
    ```
    curl -o docker-compose.yml https://raw.githubusercontent.com/snoups/remnashop/refs/heads/main/docker-compose.prod.external.yml
    ```
    - For internal panel **(the bot and panel are hosted on the same server)**:
    ```
    curl -o docker-compose.yml https://raw.githubusercontent.com/snoups/remnashop/refs/heads/main/docker-compose.prod.internal.yml
    ```

- Get `.env` file
    ```
    curl -o .env https://raw.githubusercontent.com/snoups/remnashop/refs/heads/main/.env.example
    ```


## Step 2 – Configure the .env file

Generate secret keys by running the following commands:

- Generate secure keys
```
sed -i "s|^APP_CRYPT_KEY=.*|APP_CRYPT_KEY=$(openssl rand -base64 32 | tr -d '\n')|" .env && sed -i "s|^BOT_SECRET_TOKEN=.*|BOT_SECRET_TOKEN=$(openssl rand -hex 64 | tr -d '\n')|" .env
```

- Generate passwords
```
sed -i "s|^DATABASE_PASSWORD=.*|DATABASE_PASSWORD=$(openssl rand -hex 24 | tr -d '\n')|" .env && sed -i "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(openssl rand -hex 24 | tr -d '\n')|" .env
```

Now, open the .env file and update the variables:

- **`APP_DOMAIN`** : The domain used by Telegram and Remnawave to reach your bot.
- **`BOT_TOKEN`** : Your bot token from BotFather.
- **`BOT_DEV_ID`** : Telegram ID of the main developer.
- **`BOT_SUPPORT_USERNAME`** : Support username without the `@` symbol.
- **`REMNAWAVE_HOST`** : The domain or Docker container name.
- **`REMNAWAVE_TOKEN`** : Remnawave API token, created in the panel.
- **`REMNAWAVE_WEBHOOK_SECRET`** : Must match the value of `WEBHOOK_SECRET_HEADER` from `.env` the panel.

> [!WARNING]
> Depending on your configuration, also pay attention to the following variables: **`BOT_MINI_APP_URL`**, **`REMNAWAVE_CADDY_TOKEN`**, **`REMNAWAVE_COOKIE`**.

> [!IMPORTANT]
> The bot requires a properly configured webhook to function.  
> In the Remnawave Panel `.env` file, set:
> 
> ```
> WEBHOOK_ENABLED=true
> WEBHOOK_URL=https://bot.domain.com/api/v1/remnawave
> ```
> Replace `bot.domain.com` with your actual domain.  
> This step is critically important for the bot to receive events correctly.


## Step 3 – Start the containers

Start the containers by running the following command:

```
docker compose up -d && docker compose logs -f -t
```

After a few seconds, you should see the bot successfully start.


## Step 4 - Reverse proxies

A reverse proxy is required to run Remnashop properly.  
It is needed to receive webhooks from Telegram, the Remnawave panel, and payment systems.

**This guide does not cover how to install or configure a reverse proxy.**  
You can use any proxy solution, similar to how it is done for [**Remnawave**](https://remna.st/docs/install/reverse-proxies/).

> If you are installing the bot on the same server as the panel, you probably already have a proxy configured.  
> In this case, you only need to add a forwarding rule to route traffic to the bot container.

**Configure the following path to forward requests to the bot container:**

`https://your-domain/api/v1` -> `http://remnashop:5000`


## Step 5 – How to upgrade

To update and restart the bot, run the following command:
```
cd /opt/remnashop && docker compose pull && docker compose down && RESET_ASSETS=true docker compose up -d && docker compose logs -f
```

When using `RESET_ASSETS=true`, the following actions are performed:
  - All current assets are backed up with a timestamp (`/opt/remnashop/assets/*.bak`).
  - New assets from the image are downloaded and unpacked.
  - After the update, the bot will use the latest files.

> [!CAUTION]
> If you do not use `RESET_ASSETS=true`, the old assets will remain unchanged.  
> This may cause the bot to work incorrectly after the update.


# 🖼️ Banners

The bot supports custom banners for each page category and locale: `menu`, `dashboard`, `subscription`, `promocode`, `referral`. 

To set a custom banner, name it according to the target page and ensure it uses one of the supported formats: `jpg`, `jpeg`, `png`, `gif`, `webp`.

Banners should be placed in: `/opt/remnashop/assets/banners/(locale)/`  
Example: `/opt/remnashop/assets/banners/en/menu.gif`

> [!IMPORTANT]
> Do not delete the `default.jpg` file — it is required for proper operation.


# 🌐 Translations
You can edit any translation file located in:
`/opt/remnashop/assets/translations/(locale)/`

After making changes, you need to restart the container for the updates to take effect.

> [!IMPORTANT]
> Currently, translation persistence during bot updates is not supported.  
> When updating, your previous assets will be archived in: `/opt/remnashop/assets/*.bak`


# 💸 Project Support

Any support helps me dedicate more time to development and accelerate project progress!

> Russian and international cards - [**Tribute**](https://t.me/tribute/app?startapp=drsi)

> SBP, ЮMoney, SberPay, T-Pay - [**ЮKassa**](https://yookassa.ru/my/i/Z8AkHJ_F9sO_/l)

> USDT TRC-20 - **`TPnpmwD4P9znKs3Hp4Hrh9rhJ7u1m6UA1B`**

