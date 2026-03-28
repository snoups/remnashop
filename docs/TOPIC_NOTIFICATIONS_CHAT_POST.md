You can install Telegram topic routing for admin notifications in your own `remnashop` without using my Docker image.

What it gives:

- registrations -> one forum topic
- trials -> another topic
- paid subscriptions -> another topic
- system messages -> another topic
- errors -> another topic

How to install:

1. Take these files from `https://github.com/corequadz/remnashopthreads`:
- `src/modules/__init__.py`
- `src/modules/topic_notifications/__init__.py`
- `src/modules/topic_notifications/config.py`
- `src/modules/topic_notifications/service.py`
- `src/application/services/notification.py`
- `src/infrastructure/di/providers/services.py`

2. Put them into the same paths in your current `remnashop`.

3. Add this to `.env`:

```env
TELEGRAM_TOPICS_MODE=1
TELEGRAM_TOPICS_GROUP_ID=-1003825796895
TELEGRAM_TOPICS_ROUTES=BOT_LIFECYCLE:15,BOT_UPDATE:15,SYSTEM:15,USER_REGISTERED:6,TRIAL_ACTIVATED:19,SUBSCRIPTION:22,ERROR:24,REMNAWAVE_ERROR:24,WEBHOOK_ERROR:24
```

4. Build your own local image:

```bash
docker build -t remnashop:threads .
```

5. In your `docker-compose` replace:

```yaml
image: ghcr.io/snoups/remnashop:latest
```

with:

```yaml
image: remnashop:threads
```

6. Restart:

```bash
docker compose up -d --build
```

Important:

- do not set `TELEGRAM_TOPICS_DEFAULT_TOPIC_ID` unless you are sure it exists
- no database migration is required
- if you see `message thread not found`, one of the topic ids is wrong
