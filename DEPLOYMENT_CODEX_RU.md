# Передача проекта Codex для развёртывания на новом сервере

Этот документ предназначен для пользователя и для нового агента Codex. Он описывает
развёртывание именно изменённой версии Remnashop с розыгрышами, расширенными промокодами
и управлением пользователями.

## 1. Что разворачивать

- Репозиторий пользователя: `https://github.com/Mandalorec95/remnashop.git`
- Рабочая ветка: `codex/giveaways-user-management`
- Последний основной коммит при создании документа: `6ba19b9`
- Upstream PR для истории: `https://github.com/snoups/remnashop/pull/123`
- Python: 3.12 внутри Docker
- PostgreSQL: 17
- Redis-совместимое хранилище: Valkey 9
- Remnawave: версия от `2.7.0` включительно и ниже `2.8.0`

Перед развёртыванием Codex обязан проверить фактический commit:

```bash
git branch --show-current
git log -1 --oneline
git status --short
```

Ожидается ветка `codex/giveaways-user-management`. Рабочее дерево перед запуском должно
быть чистым.

## 2. Важное отличие от стандартного Remnashop

Файлы `docker-compose.prod.*.yml` по умолчанию используют готовый образ:

```text
ghcr.io/snoups/remnashop:latest
```

В этом образе может не быть изменений из пользовательской ветки. Поэтому при запуске
обязательно добавлять `docker-compose.custom.yml`. Он собирает образ из текущего checkout:

```bash
docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  up -d --build
```

Без `docker-compose.custom.yml` развёртывание пользовательской версии считать неверным.

## 3. Что Codex должен уточнить у пользователя

До изменения сервера нужно получить ответы:

1. Это чистая установка или перенос действующего бота?
2. Remnawave уже запущен на этом же сервере?
3. Какой домен будет использовать бот?
4. Где настроен HTTPS/reverse proxy: Caddy, Nginx, Traefik или панель Remnawave?
5. Нужно ли переносить текущую PostgreSQL-базу и каталог `assets`?
6. Где лежит старый `.env`, и доступен ли старый `APP_CRYPT_KEY`?

Не просить пользователя отправлять токены и пароли в чат. Секреты вводятся непосредственно
на сервере в `.env`.

## 4. Требования к серверу

Рекомендуется Ubuntu 22.04/24.04 или другой современный Linux:

- Docker Engine;
- Docker Compose v2 (`docker compose`);
- Git;
- минимум 2 ГБ RAM, предпочтительно 4 ГБ;
- свободные порты 80/443 для reverse proxy;
- DNS-запись домена, указывающая на сервер;
- исходящие соединения к Telegram и Remnawave;
- корректное системное время и NTP.

Быстрая проверка:

```bash
docker --version
docker compose version
git --version
timedatectl status
df -h
free -h
```

Codex не должен отключать firewall или публиковать PostgreSQL/Valkey наружу. В compose
PostgreSQL привязан к `127.0.0.1`, а Valkey не публикует порт на хост.

## 5. Клонирование

```bash
sudo mkdir -p /opt/remnashop
sudo chown "$USER":"$USER" /opt/remnashop
git clone --branch codex/giveaways-user-management \
  https://github.com/Mandalorec95/remnashop.git /opt/remnashop
cd /opt/remnashop
git status -sb
git log -1 --oneline
```

Если репозиторий уже клонирован:

```bash
cd /opt/remnashop
git fetch origin
git switch codex/giveaways-user-management
git pull --ff-only
```

Не выполнять `git reset --hard`, если на сервере есть непроверенные локальные изменения.

## 6. Выбор production-compose

### Remnawave находится на том же сервере и уже использует сеть `remnawave-network`

Использовать:

```text
docker-compose.prod.internal.yml
```

В нём сеть объявлена как `external: true`. До запуска проверить:

```bash
docker network inspect remnawave-network
```

Если Remnawave работает, но сеть называется иначе, сначала изучить его compose. Не создавать
параллельную сеть наугад: контейнер бота должен видеть API Remnawave по имени из
`REMNAWAVE_HOST`.

### Remnawave удалённый или сети `remnawave-network` ещё нет

Использовать:

```text
docker-compose.prod.external.yml
```

Несмотря на имя файла, он сам создаёт локальную Docker-сеть (`external: false`).
`REMNAWAVE_HOST` в этом случае должен быть доступным URL/hostname API Remnawave.

## 7. Настройка `.env`

Создать файл с закрытыми правами:

```bash
cd /opt/remnashop
cp .env.example .env
chmod 600 .env
nano .env
```

Обязательные значения:

```dotenv
APP_DOMAIN=bot.example.com
APP_CRYPT_KEY=<base64-ключ длиной 44 символа>

BOT_TOKEN=<токен BotFather>
BOT_SECRET_TOKEN=<случайный секрет>
BOT_OWNER_ID=<числовой Telegram ID владельца>
BOT_SUPPORT_USERNAME=<username без @>
BOT_MINI_APP=false

REMNAWAVE_HOST=remnawave
REMNAWAVE_TOKEN=<API-токен Remnawave>
REMNAWAVE_WEBHOOK_SECRET=<секрет webhook Remnawave>

DATABASE_PASSWORD=<случайный пароль>
REDIS_PASSWORD=<случайный пароль>
```

Полезные команды генерации для новой установки:

```bash
openssl rand -base64 32
openssl rand -hex 64
openssl rand -hex 24
```

Правила:

- `APP_DOMAIN` указывается без `https://` и без завершающего `/`;
- `BOT_SUPPORT_USERNAME` указывается без `@`;
- `APP_CRYPT_KEY` должен быть Base64-строкой длиной 44 символа;
- `BOT_OWNER_ID` — число, не username;
- не оставлять ни одного обязательного значения `change_me`;
- `.env` нельзя добавлять в Git.

### Критично при переносе существующей базы

Нужно сохранить прежний `APP_CRYPT_KEY`. Новый ключ сделает ранее зашифрованные платёжные
настройки и другие секреты в базе нечитаемыми.

Также желательно перенести прежние:

- `BOT_TOKEN`;
- `BOT_SECRET_TOKEN`;
- `DATABASE_PASSWORD`, если переносится Docker volume целиком;
- `REMNAWAVE_TOKEN`;
- секреты платёжных шлюзов;
- `REMNAWAVE_WEBHOOK_SECRET`.

## 8. HTTPS и reverse proxy

Приложение слушает только:

```text
127.0.0.1:5000
```

Перед ним нужен HTTPS reverse proxy для `APP_DOMAIN`, направляющий весь трафик на
`http://127.0.0.1:5000`.

Основные webhook URL:

- Telegram: `https://APP_DOMAIN/api/v1/telegram`
- Remnawave: `https://APP_DOMAIN/api/v1/remnawave`
- платежи: `https://APP_DOMAIN/api/v1/payments/<gateway>`

Не открывать порт 5000 всему интернету, если используется локальный reverse proxy.
После настройки проверить:

```bash
curl -I https://bot.example.com/
```

Ответ может быть не `200` для корневого URL, но TLS, DNS и соединение должны работать.

## 9. Чистая установка

Проверить итоговую конфигурацию без вывода секретов:

```bash
cd /opt/remnashop
docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  config --services
```

Для варианта с удалённым Remnawave заменить `internal` на `external`.

Собрать и запустить:

```bash
docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  up -d --build
```

Миграции Alembic запускаются автоматически в `docker-entrypoint.sh` контейнера
`remnashop`. Если миграция не прошла, основной контейнер завершится с ошибкой.

## 10. Перенос существующей установки

Перед любыми действиями на старом сервере сделать резервные копии.

### 10.1 Дамп PostgreSQL на старом сервере

```bash
mkdir -p /opt/backups/remnashop-migration
docker exec remnashop-db sh -lc \
  'pg_dump -U "${POSTGRES_USER:-remnashop}" \
  -d "${POSTGRES_DB:-remnashop}" \
  --format=custom --no-owner --no-privileges' \
  > /opt/backups/remnashop-migration/remnashop.dump
```

Проверить, что файл не пустой:

```bash
ls -lh /opt/backups/remnashop-migration/remnashop.dump
pg_restore --list /opt/backups/remnashop-migration/remnashop.dump | tail
```

Если `pg_restore` отсутствует на хосте, список можно проверить контейнером PostgreSQL.

### 10.2 Сохранить конфигурацию и assets

```bash
cp /opt/remnashop/.env /opt/backups/remnashop-migration/env.backup
tar -C /opt/remnashop -czf \
  /opt/backups/remnashop-migration/assets.tar.gz assets
```

Файлы резервной копии содержат секреты. Передавать их только защищённым способом,
установить права `600`, после миграции удалить лишние копии.

### 10.3 Восстановление на новом сервере

Сначала запустить только PostgreSQL:

```bash
cd /opt/remnashop
docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  up -d remnashop-db
```

Дождаться состояния healthy:

```bash
docker inspect --format '{{.State.Health.Status}}' remnashop-db
```

Восстановление рекомендуется выполнять в пустую базу до первого полного запуска:

```bash
docker exec -i remnashop-db sh -lc \
  'pg_restore -U "${POSTGRES_USER:-remnashop}" \
  -d "${POSTGRES_DB:-remnashop}" \
  --no-owner --no-privileges --clean --if-exists' \
  < /opt/backups/remnashop-migration/remnashop.dump
```

Для новой пустой базы предупреждения `--clean` об отсутствующих объектах могут быть
нормальными. Любые другие ошибки нужно изучить до запуска приложения.

Восстановить assets:

```bash
cd /opt/remnashop
tar -xzf /opt/backups/remnashop-migration/assets.tar.gz
```

Затем запустить весь стек. При старте Alembic обновит перенесённую базу до новой схемы.

## 11. Проверка после запуска

```bash
cd /opt/remnashop
docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  ps

docker inspect --format \
  '{{.Name}} status={{.State.Status}} restarts={{.RestartCount}}' \
  remnashop remnashop-taskiq-worker remnashop-taskiq-scheduler

docker logs --since 10m remnashop
docker logs --since 10m remnashop-taskiq-worker
docker logs --since 10m remnashop-taskiq-scheduler
```

Искать:

```bash
docker logs --since 10m remnashop 2>&1 | \
  grep -E 'ERROR|CRITICAL|Traceback|migration failed'
```

Успешное состояние:

- PostgreSQL и Valkey healthy;
- три контейнера приложения имеют статус running;
- restart count не растёт;
- в логе есть успешное применение миграций;
- Telegram-бот отвечает владельцу;
- открывается админ-панель;
- виден раздел розыгрышей;
- Remnawave API доступен;
- Telegram webhook указывает на новый домен;
- тестовая операция не создаёт ошибок в worker.

Проверка текущего Telegram webhook без публикации токена в истории shell:

```bash
set -a
. ./.env
set +a
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
unset BOT_TOKEN
```

Не вставлять вывод с токеном или секретами в публичные логи и чаты.

## 12. Обновление в будущем

Перед обновлением:

1. сделать дамп PostgreSQL;
2. сохранить `.env` и `assets`;
3. проверить `git status`;
4. получить изменения только fast-forward;
5. пересобрать образ.

```bash
cd /opt/remnashop
git fetch origin
git switch codex/giveaways-user-management
git pull --ff-only

docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  up -d --build
```

После обновления повторить проверки контейнеров и логов.

## 13. Откат

Откат кода без отката базы может быть несовместим с уже применёнными миграциями.
Самый безопасный откат:

1. остановить приложение;
2. восстановить дамп базы, сделанный до обновления;
3. checkout проверенного старого commit;
4. пересобрать и запустить контейнеры;
5. проверить логи и Telegram webhook.

Команда остановки без удаления данных:

```bash
docker compose \
  -f docker-compose.prod.internal.yml \
  -f docker-compose.custom.yml \
  down
```

Никогда не добавлять `-v` при обычной остановке или откате: этот флаг удалит Docker volumes
PostgreSQL и Valkey.

## 14. Ограничения и известные замечания ветки

- Новые файлы розыгрышей, удаления пользователей и миграций прошли Ruff.
- В полном дереве ветки на момент публикации оставались style-замечания Ruff.
- Python compile check для `src` проходил.
- В ветке есть миграции `0022`, `0023`, `0024`.
- При первом старте после переноса нужно особенно внимательно проверить миграционные логи.
- `assets` смонтирован с хоста. Entrypoint не перезаписывает непустой каталог, если
  `RESET_ASSETS` не равен `true`.
- Не устанавливать `RESET_ASSETS=true` на перенесённой установке без резервной копии:
  существующие assets будут архивированы и заменены defaults.

## 15. Готовый запрос новому Codex

Можно передать агенту следующий текст:

> Разверни Remnashop по инструкции `DEPLOYMENT_CODEX_RU.md`. Работай в
> `/opt/remnashop`, используй репозиторий `Mandalorec95/remnashop` и ветку
> `codex/giveaways-user-management`. Сначала проведи read-only аудит сервера, Docker,
> DNS, reverse proxy, сети Remnawave, текущих контейнеров и резервных копий. Не печатай
> секреты из `.env`. Перед миграциями обязательно создай и проверь дамп PostgreSQL.
> Используй production-compose вместе с `docker-compose.custom.yml`, иначе запустится
> upstream-образ без пользовательских изменений. Не удаляй volumes и не применяй
> разрушительные команды без моего явного подтверждения. После запуска проверь health,
> restart count, миграции, ошибки в логах, Telegram webhook, Remnawave и раздел
> розыгрышей. Продолжай до рабочего результата или чётко названного внешнего блокера.
