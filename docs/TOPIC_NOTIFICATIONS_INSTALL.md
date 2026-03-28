# Topic Notifications Install Guide

This guide explains how to add Telegram forum topic routing for admin/system notifications to an existing `remnashop` installation without using a custom remote Docker image.

## What this feature does

It routes admin/system notifications into Telegram forum topics inside a group:

- registrations
- trial activations
- paid subscriptions
- system events
- errors

It does not require database migrations.

## Files added or changed

Copy these files from this repository into your existing `remnashop` project:

- `src/modules/__init__.py`
- `src/modules/topic_notifications/__init__.py`
- `src/modules/topic_notifications/config.py`
- `src/modules/topic_notifications/service.py`
- `src/application/services/notification.py`
- `src/infrastructure/di/providers/services.py`

## Fast install with git

If your project is a git checkout, the easiest way is:

```bash
git remote add remnashopthreads https://github.com/corequadz/remnashopthreads.git
git fetch remnashopthreads
git checkout remnashopthreads/main -- \
  src/modules/__init__.py \
  src/modules/topic_notifications/__init__.py \
  src/modules/topic_notifications/config.py \
  src/modules/topic_notifications/service.py \
  src/application/services/notification.py \
  src/infrastructure/di/providers/services.py
```

If `remnashopthreads` remote already exists:

```bash
git fetch remnashopthreads
git checkout remnashopthreads/main -- \
  src/modules/__init__.py \
  src/modules/topic_notifications/__init__.py \
  src/modules/topic_notifications/config.py \
  src/modules/topic_notifications/service.py \
  src/application/services/notification.py \
  src/infrastructure/di/providers/services.py
```

## If you do not use git

Download the files listed above from:

- `https://github.com/corequadz/remnashopthreads`

Then place them into the same paths inside your current project.

## Environment variables

Add this to your `.env`:

```env
TELEGRAM_TOPICS_MODE=1
TELEGRAM_TOPICS_GROUP_ID=-1003825796895
TELEGRAM_TOPICS_ROUTES=BOT_LIFECYCLE:15,BOT_UPDATE:15,SYSTEM:15,USER_REGISTERED:6,TRIAL_ACTIVATED:19,SUBSCRIPTION:22,ERROR:24,REMNAWAVE_ERROR:24,WEBHOOK_ERROR:24
```

Notes:

- `TELEGRAM_TOPICS_GROUP_ID` is the Telegram supergroup id.
- `TELEGRAM_TOPICS_MODE=1` sends notifications only to the group.
- `TELEGRAM_TOPICS_MODE=2` sends notifications both to the group and to admin DMs.
- `TELEGRAM_TOPICS_DEFAULT_TOPIC_ID` is optional. If you are not sure about the topic id, do not set it.

## Build your own local Docker image

Build a local image from your modified project:

```bash
docker build -t remnashop:threads .
```

Then change the image line in your production compose file:

```yaml
x-build: &build
  image: remnashop:threads
```

Because the compose file uses the same image anchor, the app, worker, and scheduler will all use your local build.

## Restart

Run:

```bash
docker compose pull
docker compose up -d --build
```

If your compose file still points to `image:` and not `build:`, the `--build` flag is harmless. The important part is that the image name must be your local `remnashop:threads`.

## How to verify

After startup:

- bot startup messages should go to topic `15`
- new registrations should go to topic `6`
- trial activations should go to topic `19`
- paid subscriptions should go to topic `22`
- errors should go to topic `24`

## Troubleshooting

### `message thread not found`

This means the topic id is wrong. Remove `TELEGRAM_TOPICS_DEFAULT_TOPIC_ID` unless you are sure it exists.

### `Cannot find factory for (bool | None, component='')`

You are missing the updated `src/modules/topic_notifications/config.py` and/or `src/infrastructure/di/providers/services.py`.

### The bot still uses the official image

Your compose file still contains:

```yaml
image: ghcr.io/snoups/remnashop:latest
```

Replace it with:

```yaml
image: remnashop:threads
```
