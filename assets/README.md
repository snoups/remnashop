# `Banners`

The `banners` folder contains all banner images.

## Banner configuration

You can configure how banners are displayed in the bot using an environment variable:

* **`BOT_USE_BANNERS`**: Set to true to enable banners, or false to disable them.

## Locale support

The banner system supports **localized versions**. A banner corresponding to the user's **locale** will be loaded for each user.

### How it works:

1.  **User's locale:** The system first attempts to find a banner in the folder corresponding to the current user's locale (e.g., `en`). Available locales are defined by the `APP_LOCALES` environment variable.
2.  **Fallback:** If a banner is not found in the user's locale (or the locale folder itself is missing), the system automatically searches for a banner in the **default locale**, specified by the `APP_DEFAULT_LOCALE` environment variable.
3.  **Placeholder banner:** If a banner is not found in either the user's locale or the default locale, a placeholder banner named `default.jpg` will be used. This file must be located directly in the root `banners` directory.

This ensures that even if a specific banner or locale is not found, some banner will always be displayed, preventing empty or missing images.

## Supported formats

The following file formats are supported, as defined in `/remnashop/src/core/enums.py` as `BannerFormat`:

* **JPG**
* **JPEG**
* **PNG**
* **GIF**
* **WEBP**

## Banner names

Banner filenames must correspond to the following predefined names, specified in `/remnashop/src/core/enums.py` as `BannerName`:

* **`DEFAULT`**: The default banner, used when a specific banner is not found.
* **`MENU`**: The main menu banner.
* **`DASHBOARD`**: The dashboard banner.

## Example file structure

```
banners/
├── en/
│   ├── MENU.jpg
│   └── DASHBOARD.jpg
├── ru/
│   ├── MENU.gif
│   └── DASHBOARD.gif
└── default.jpg
```


# `Translations`

The `translations` folder contains all localization text files.

## Translation configuration

Supported locales are defined in environment variables:

* **`APP_LOCALES`**: A list of supported locales. A full list of available locales can be found in `remnashop/src/core/enums.py` as `Locale`.
* **`APP_DEFAULT_LOCALE`**: The default locale to be used if a user's language preference is not specified or not supported.


## Key naming convention

All translation keys must follow a unified structure:
```
{category}-{scope}-{entity}-{action-or-state}
```

## Components

| Part                | Description                   | Example                                                                            |
| ------------------- | ----------------------------- | ---------------------------------------------------------------------------------- |
| `{category}`        | Top-level type of text        | `btn`, `msg`, `ntf`                                                                |
| `{scope}`           | Logical group or subsystem    | `user`, `plan`, `broadcast`, `gateway`, `subscription`, `access`, `error`, `event` |
| `{entity}`          | Specific object or sub-entity | `content`, `payment`, `link`, `node`                                               |
| `{action-or-state}` | Action or state, in lowercase | `created`, `deleted`, `empty`, `invalid`, `failed`, `not-found`                    |

## Naming rules

1. Use lowercase with hyphens (-) — no underscores or spaces.
2. Follow the order:
    ```
    category → scope → entity → action/state
    ```
    - ✅ ntf-broadcast-content-empty
    - ✅ btn-user-create
    - ✅ msg-plan-deleted-success

    - ❌ ntf-content-empty-broadcast
    - ❌ btn-create-user
    - ❌ msg-plan-success-deleted
3. Actions — past tense verbs (created, updated, deleted, canceled, failed).
4. States — adjectives (empty, invalid, not-found, expired, not-available).
5. Limit to 5 segments maximum.

## Examples

| Purpose                               | Key                               |
| ------------------------------------- | --------------------------------- |
| Notification: user expired            | `ntf-user-expired`                |
| Notification: broadcast empty content | `ntf-broadcast-content-empty`     |
| Button: confirm deletion              | `btn-plan-confirm-delete`         |
| Message: plan created successfully    | `msg-plan-created-success`        |
| Notification: gateway test failed     | `ntf-gateway-test-payment-failed` |
