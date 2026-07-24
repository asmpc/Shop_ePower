# Shop_ePower — Deployment Plan

> **Статус: DRAFT / NOT IMPLEMENTED**  
> Production deployment запланирован после дипломной защиты.

## 1. Цель

Развернуть Shop_ePower на Linux-сервере с:

- production application server;
- reverse proxy;
- HTTPS;
- PostgreSQL;
- Redis;
- Celery Worker;
- Celery Beat;
- persistent storage;
- backups;
- controlled migrations.

## 2. Предполагаемая схема

```text
Internet
  ↓
Nginx / HTTPS
  ↓
Gunicorn
  ↓
Django
  ├── PostgreSQL
  ├── Redis
  └── Celery

Celery Beat → Redis → Worker
```

## 3. Важно

`python manage.py runserver` используется только в development.

Production-вариант должен использовать production WSGI server, например:

```text
gunicorn config.wsgi:application
```

## 4. План

### Production settings

- DEBUG=False;
- SECRET_KEY только из environment;
- ALLOWED_HOSTS;
- CSRF_TRUSTED_ORIGINS;
- secure cookies;
- logging;
- email backend;
- static/media settings.

### Compose profiles

Возможное разделение:

```text
compose.yaml
compose.production.yaml
```

Или settings:

```text
config/settings/base.py
config/settings/development.py
config/settings/production.py
```

Решение будет принято после защиты.

### Reverse proxy

Nginx:

- TLS termination;
- proxy to Gunicorn;
- static/media;
- security headers;
- request size limits.

### Static

```powershell
python manage.py collectstatic --noinput
```

### Media

Не хранить пользовательские файлы внутри immutable image.

Варианты:

- Docker volume;
- S3-compatible storage;
- managed object storage.

### Migrations

```text
build
  ↓
backup
  ↓
migrate
  ↓
restart
  ↓
healthcheck
```

Не запускать миграции параллельно из каждого web instance.

### Backups

- ежедневный PostgreSQL backup;
- retention;
- отдельное хранение;
- периодическая проверка восстановления.

### Celery

- один Beat;
- worker concurrency по ресурсам;
- time limits;
- retries;
- monitoring;
- graceful shutdown.

### Flower

- не публиковать без защиты;
- Basic Auth / VPN / private network;
- возможно не держать постоянно включённым.

## 5. Definition of Done

- HTTPS;
- безопасные миграции;
- static/media доступны;
- backup и restore проверены;
- Redis/Celery стабильны;
- один Beat;
- logging;
- secrets вне Git;
- smoke test основного сценария;
- rollback documented.
