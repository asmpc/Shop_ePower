# Shop_ePower — Docker Manual

## 1. Назначение

Рабочая шпаргалка по локальному Docker Compose-окружению Shop_ePower.

| Service | Назначение | Порт Windows |
|---|---|---:|
| `web` | Django Web | `8000` |
| `postgres` | PostgreSQL | `5433` |
| `redis` | Redis broker/cache | `6380` |
| `celery_worker` | Фоновые задачи | — |
| `celery_beat` | Периодические задачи | — |
| `flower` | Мониторинг Celery | `5555` |

Внутри Docker-сети используются `postgres:5432`, `redis:6379`, `web:8000`, `flower:5555`.



## 🐳 Docker Philosophy

Shop_ePower uses **one Docker image** for the application layer.

```text
                One Docker Image
                       │
      ┌────────────────┼────────────────┐
      ▼                ▼                ▼
     web        celery_worker     celery_beat
                                        │
                                        ▼
                                     flower
```

Each service runs the same application image with a different startup command. This keeps the environment consistent and simplifies maintenance.

## 🏗 Infrastructure Overview

```text
                 Docker Compose
                       │
      ┌────────────────┼────────────────┐
      ▼                ▼                ▼
 PostgreSQL         Redis          Django Web
                       │
            ┌──────────┼───────────┐
            ▼          ▼           ▼
     Celery Worker  Celery Beat  Flower
```


## 2. Где выполнять команды

Из корня проекта:

```powershell
D:\Shop_ePower
```

## 3. Запуск и остановка

Запустить весь стек:

```powershell
docker compose up -d
```

Запустить с пересборкой после изменения Dockerfile, pyproject.toml или poetry.lock`:

```powershell
docker compose up -d --build
```

Запустить отдельный сервис:

```powershell
docker compose up -d web
docker compose up -d celery_worker
```

Остановить контейнеры, сохранив volumes:

```powershell
docker compose down
```

Полностью удалить контейнеры и данные:

```powershell
docker compose down -v
```

> Осторожно: `-v` удаляет контейнерную PostgreSQL database и Redis data.

Перезапустить весь стек:

```powershell
docker compose restart
```

Перезапустить сервис:

```powershell
docker compose restart web
docker compose restart celery_worker
docker compose restart celery_beat
```

## 4. Состояние

```powershell
docker compose ps
```

Ожидаемо:

- `postgres` — healthy;
- `redis` — healthy;
- `web` — healthy;
- `celery_worker` — running;
- `celery_beat` — running;
- `flower` — healthy.

Все контейнеры Docker:

```powershell
docker ps
docker ps -a
```

Проверить итоговую Compose-конфигурацию:

```powershell
docker compose config
```

> Не публикуй полный вывод, если он содержит секреты из `.env`.

## 5. Адреса и порты

Shop_ePower:

```text
http://127.0.0.1:8000/shop/
```

Django Admin:

```text
http://127.0.0.1:8000/admin/
```

Flower:

```text
http://127.0.0.1:5555
```

Проверка проброса портов:

```powershell
docker compose port web 8000
docker compose port flower 5555
docker compose port postgres 5432
docker compose port redis 6379
```

Ожидаемо:

```text
web        -> 0.0.0.0:8000
flower     -> 0.0.0.0:5555
postgres   -> 0.0.0.0:5433
redis      -> 0.0.0.0:6380
```

## 6. Логи

Все логи:

```powershell
docker compose logs
docker compose logs -f
docker compose logs --tail=100
```

По сервисам:

```powershell
docker compose logs -f web
docker compose logs -f postgres
docker compose logs -f redis
docker compose logs -f celery_worker
docker compose logs -f celery_beat
docker compose logs -f flower
```

`Ctrl+C` завершает просмотр, но не останавливает контейнер.

## 7. Сборка image

```powershell
docker compose build
docker compose build web
docker compose build --no-cache web
docker images
```

Один image `shop-epower-web` используется сервисами `web`, `celery_worker`, `celery_beat`, `flower`.

## 8. Django-команды

Проверка:

```powershell
docker compose exec web python manage.py check
```

Миграции:

```powershell
docker compose exec web python manage.py showmigrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
```

Суперпользователь:

```powershell
docker compose exec web python manage.py createsuperuser
```

Shell:

```powershell
docker compose exec web python manage.py shell
```

Все тесты:

```powershell
docker compose exec web python manage.py test
```

Тесты приложения:

```powershell
docker compose exec web python manage.py test shop_epower.orders.tests
```

Одноразовая команда во временном контейнере:

```powershell
docker compose run --rm web python manage.py check
```

`exec` использует уже работающий контейнер; `run --rm` создаёт временный.

## 9. PostgreSQL

Готовность:

```powershell
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Подключение:

```powershell
docker compose exec postgres psql -U shop_epower -d shop_epower
```

Полезные команды `psql`:

```text
\dt
\du
\l
\q
```

Проверка через Django:

```powershell
docker compose exec web python manage.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.settings_dict['HOST']); print('Database connection OK')"
```

Ожидаемо:

```text
postgres
Database connection OK
```

## 10. Redis

```powershell
docker compose exec redis redis-cli ping
```

Ожидаемо:

```text
PONG
```

Redis CLI:

```powershell
docker compose exec redis redis-cli
```

Полезные команды:

```text
PING
INFO
DBSIZE
SELECT 2
SELECT 3
QUIT
```

Не выполняй `FLUSHALL`/`FLUSHDB`, если данные нельзя удалить.

## 11. Celery Worker

Проверка:

```powershell
docker compose exec celery_worker celery -A config inspect ping
```

Зарегистрированные задачи:

```powershell
docker compose exec celery_worker celery -A config inspect registered
```

Состояние очереди:

```powershell
docker compose exec celery_worker celery -A config inspect active
docker compose exec celery_worker celery -A config inspect reserved
docker compose exec celery_worker celery -A config inspect scheduled
```

Контрольная задача:

```powershell
docker compose exec web python manage.py shell -c "from shop_epower.core.tasks import check_celery_connection; result = check_celery_connection.delay(); print(result.get(timeout=10))"
```

Ожидаемо:

```text
Celery is working
```

## 12. Celery Beat

```powershell
docker compose logs -f celery_beat
```

Корректный запуск содержит:

```text
scheduler -> django_celery_beat.schedulers.DatabaseScheduler
beat: Starting...
```

Расписание управляется через Django Admin. В нормальной конфигурации работает только один Beat.

## 13. Flower

```text
http://127.0.0.1:5555
```

```powershell
docker compose logs -f flower
docker compose port flower 5555
```

Flower показывает workers, tasks, SUCCESS/FAILURE, runtime и retries.

## 14. Вход в контейнер

```powershell
docker compose exec web sh
docker compose exec celery_worker sh
docker compose exec celery_beat sh
docker compose exec flower sh
```

Выход:

```text
exit
```

## 15. Рабочий цикл

Начало:

```powershell
docker compose up -d
docker compose ps
```

После изменения Python-кода и шаблонов пересборка обычно не нужна благодаря `./src:/app/src`.

После изменения pyproject.toml или poetry.lock:

```powershell
docker compose up -d --build
```

После изменения моделей:

```powershell
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py test
```

После изменения Celery tasks:

```powershell
docker compose restart celery_worker
```

После изменения Beat:

```powershell
docker compose restart celery_beat
```

Завершение:

```powershell
docker compose down
```



## 🚀 Development Workflow

Typical development scenarios:

### Python code or templates

```text
Change code
      │
      ▼
No rebuild required
      │
      ▼
Refresh browser
```

### pyproject.toml / poetry.lock

```text
Change pyproject.toml / poetry.lock
      │
      ▼
docker compose up -d --build
```

### Dockerfile

```text
Change Dockerfile
      │
      ▼
docker compose up -d --build
```


## 16. Диагностика

Контейнер падает:

```powershell
docker compose ps
docker compose logs --tail=200 SERVICE_NAME
```

Проблема PostgreSQL:

```powershell
docker compose exec postgres sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose exec web python manage.py check
```

Проблема Redis/Worker:

```powershell
docker compose exec redis redis-cli ping
docker compose logs --tail=200 celery_worker
```

Порт занят:

```powershell
netstat -ano | findstr :8000
netstat -ano | findstr :5555
```

Compose неправильно прочитал `.env`:

```powershell
docker compose config
```

Если секрет содержит `$`, используй одинарные кавычки:

```env
SECRET_KEY='значение_с_$'
```



## ❤️ Health Checks

Docker Compose waits for dependent services to become healthy before starting
application services.

Current checks:

- PostgreSQL → `pg_isready`
- Redis → `redis-cli ping`

These checks are used together with `depends_on: condition: service_healthy`.


## 17. Volumes и место

```powershell
docker volume ls
docker system df
docker system prune
```

Перед `prune` внимательно проверяй список удаления.

## 18. Краткая шпаргалка

```powershell
docker compose up -d
docker compose ps
docker compose logs -f web
docker compose logs -f celery_worker
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate
docker compose exec web python manage.py test
docker compose down
```


---

<div align="center">

**Happy Dockering! 🐳**

This document is intended as the daily operational guide for the Shop_ePower
development environment.

</div>
