# Shop_ePower — Current Architecture

## 1. Назначение

Shop_ePower — Django e-commerce приложение для продажи электротехнических товаров.

Основной сценарий:

```text
Клиент
  ↓
Каталог и корзина
  ↓
Проверка профиля
  ↓
Создание заказа
  ↓
Резервирование остатков
  ↓
Создание платежа
  ↓
Менеджерская обработка
  ↓
Invoice / PDF
  ↓
Оплата и история
  ↓
Чат и уведомления
```

## 2. Стек

- Python 3.14;
- Django 6;
- Django REST Framework;
- JWT / Simple JWT;
- PostgreSQL;
- Redis;
- Celery;
- django-celery-beat;
- Flower;
- WeasyPrint;
- Docker Compose;
- Django templates;
- drf-spectacular / Swagger.

## 3. Приложения

```text
accounts
core
catalog
suppliers
cart
orders
payments
notifications
chat
api
```

## 4. Доменные границы

### Accounts

- кастомный User;
- роли CLIENT / MANAGER / ADMIN;
- профиль;
- LegalProfile;
- полнота профиля;
- регистрация и аутентификация.

### Catalog

- категории;
- бренды;
- товары;
- изображения;
- варианты;
- фильтрация;
- цены и публичные остатки.

### Suppliers

- поставщики;
- собственный склад;
- внешние остатки;
- закупочные цены;
- сроки поставки.

### Cart

- активная корзина;
- позиции;
- price snapshot;
- merge гостевой и пользовательской корзины.

### Orders

- создание заказа;
- snapshot клиента;
- OrderItem;
- резервирование;
- доставка;
- статусы;
- отмена;
- manager workflow.

Событие `Order Created` принадлежит домену заказов и не зависит от платежа.

### Payments

- Payment;
- способы оплаты;
- статусы;
- PaymentHistory;
- manager/admin actions;
- Invoice;
- PDF.

Orders и Payments — отдельные домены. Уведомления об оплате будут отдельными событиями.

### Notifications

```text
Celery Task
  ↓
Notification Service
  ↓
Email backend
```

Задачи запускаются после `transaction.on_commit()` и получают только примитивные ID.

### Chat

- комнаты;
- сообщения;
- вложения;
- свободный пул;
- взятие комнаты менеджером;
- закрытие;
- unread counters.

## 5. API

- JWT;
- DRF permissions;
- OpenAPI / Swagger;
- client endpoints;
- manager endpoints;
- admin-only actions.

```text
api/accounts
api/catalog
api/suppliers
api/orders
api/payments
```

## 6. Docker Compose

```text
Browser
  ↓
web :8000
  ├── postgres:5432
  ├── redis:6379
  └── Celery tasks

redis
  ├── celery_worker
  ├── celery_beat
  └── flower :5555

celery_beat
  └── DatabaseScheduler в PostgreSQL
```

Сервисы:

```text
postgres
redis
web
celery_worker
celery_beat
flower
```

Один image приложения используется для `web`, `celery_worker`, `celery_beat`, `flower`.

## 7. Startup dependencies

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```

Принцип:

```text
container started != service ready
```

## 8. Persistence

Named volumes:

```text
postgres_data
redis_data
```

Development bind mount:

```text
./src:/app/src
```

## 9. Безопасность

Реализовано:

- отдельная PostgreSQL-роль `shop_epower`;
- приложение не использует суперпользователя `postgres`;
- `.env` не должен попадать в Git;
- секреты не копируются в image.

До production:

- DEBUG=False;
- ALLOWED_HOSTS;
- CSRF_TRUSTED_ORIGINS;
- HTTPS;
- защищённый Flower;
- production server;
- secrets management;
- ограничение портов.

## 10. Архитектурные правила

1. Views не содержат сложную бизнес-логику.
2. Бизнес-правила находятся в services.
3. Selectors отвечают за чтение и queryset.
4. Celery tasks остаются тонкими.
5. Django-объекты не передаются в очередь.
6. Задачи после записи в БД используют `transaction.on_commit()`.
7. Orders и Payments не смешиваются.
8. Snapshots и исторические документы сохраняют историческое состояние.
9. Technical debt фиксируется явно.
