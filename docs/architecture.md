# Shop_ePower — Current Architecture

## 1. Purpose

Shop_ePower is a modular Django e-commerce platform for electrical products.

The core business workflow:

```text
                              CUSTOMER
                                  │
                                  ▼
                         PRODUCT CATALOG
                                  │
                                  ▼
                          SHOPPING CART
                                  │
                                  ▼
                       PROFILE VALIDATION
                                  │
                                  ▼
                          ORDER CREATION
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
      STOCK RESERVATION     MANAGER WORKFLOW     CUSTOMER CHAT
              │                   │
              ▼                   ▼
       SUPPLIER STOCK       PAYMENT PROCESSING
                                  │
                         ┌────────┴────────┐
                         ▼                 ▼
                    INVOICE PDF       NOTIFICATIONS
                         │                 │
                         └────────┬────────┘
                                  ▼
                           ORDER HISTORY
```

---

## 2. Technology Stack

- Python 3.14
- Django 6
- Django REST Framework
- Simple JWT
- PostgreSQL
- Redis
- Celery
- django-celery-beat
- Flower
- ReportLab
- Docker Compose
- Django Templates
- Bootstrap
- drf-spectacular / Swagger

---

## 3. Project Applications

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

---

## 4. Project Layers

```text
Browser
    │
    ▼
Templates / REST API
    │
    ▼
Views / ViewSets
    │
    ▼
Services
    │
    ├───────────────┐
    ▼               ▼
Selectors        Models
        │         │
        └────┬────┘
             ▼
        PostgreSQL
```

Business rules live in the service layer. Selectors are responsible for complex read operations. Views remain thin and orchestrate requests.

---

## 5. Domain Responsibilities

### Accounts

- custom User
- CLIENT / MANAGER / ADMIN roles
- profile management
- LegalProfile
- profile completeness
- authentication

### Catalog

- categories
- brands
- products
- product images
- variants
- pricing
- public inventory

### Suppliers

- internal warehouse
- external suppliers
- supplier prices
- stock quantities
- lead time calculation

### Cart

- shopping cart
- snapshots
- guest/user cart merge

### Orders

- checkout
- order lifecycle
- reservations
- delivery
- manager workflow
- cancellations

Order creation is independent from payment processing.

### Payments

- Payment
- PaymentHistory
- payment actions
- Invoice
- PDF generation with ReportLab

Orders and Payments remain independent business domains.

### Notifications

Celery → Notification Service → Email Backend

Tasks are scheduled after transaction.on_commit() and receive only primitive identifiers.

### Chat

- rooms
- manager assignment
- attachments
- unread counters
- room closing

---

## 6. REST API

- JWT Authentication
- OpenAPI / Swagger
- client endpoints
- manager endpoints
- administrator actions

```text
api/accounts
api/catalog
api/orders
api/payments
api/suppliers
```

---

## 7. Infrastructure

```text
Browser
    │
    ▼
Django Web (:8000)
    │
 ┌──┴───────────────┐
 ▼                  ▼
PostgreSQL      Redis
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
   Celery Worker  Celery Beat Flower
```

Services:

- postgres
- redis
- web
- celery_worker
- celery_beat
- flower

One Docker image is reused by web, worker, beat and Flower.

---

## 8. Startup Dependencies

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```

Principle:

```text
Container started ≠ Service ready
```

---

## 9. Persistence

Named Docker volumes:

```text
postgres_data
redis_data
```

Development bind mount:

```text
./src:/app/src
```

---

## 10. Security

Implemented:

- dedicated PostgreSQL role (`shop_epower`)
- application never uses `postgres`
- `.env` excluded from Git
- secrets are not baked into images

Production roadmap:

- DEBUG=False
- ALLOWED_HOSTS
- HTTPS
- CSRF_TRUSTED_ORIGINS
- secured Flower
- production ASGI server
- secrets management

---

## 11. Engineering Principles

1. Thin Views.
2. Business logic belongs to Services.
3. Selectors encapsulate complex queries.
4. Celery tasks stay thin.
5. Only primitive IDs are sent to task queues.
6. Background tasks are started via `transaction.on_commit()`.
7. Orders and Payments remain separate domains.
8. Snapshot entities preserve historical integrity.
9. Every discovered regression receives an automated test.
10. Technical debt is documented explicitly.

---

## 12. Current Infrastructure Status

Current Docker Compose environment:

```text
Docker Compose
      │
      ▼
 PostgreSQL
      │
      ▼
    Redis
      │
      ├── Celery Worker
      ├── Celery Beat
      └── Flower
```

The architecture is intentionally designed for future scaling, production deployment, WebSocket communication, Redis caching, and external integrations without major restructuring.