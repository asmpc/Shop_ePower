# Shop_ePower — Current Architecture

## 1. Purpose

Shop_ePower is an enterprise-oriented Django platform for wholesale and retail
electrical equipment sales.

The architecture is organized around independent business domains that
cooperate through explicit services and interfaces. The project evolves
incrementally: stable components are extended rather than replaced without a
clear business or technical reason.

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

## 11. Design and Engineering Principles

1. **Business First** — business requirements drive architectural decisions.
2. **Evolution over Revolution** — working components are extended
   incrementally instead of being rewritten without necessity.
3. **Test Driven Development** — new functionality and discovered regressions
   are protected by automated tests.
4. **Clean Architecture** — business rules belong to services and domain
   layers rather than views or transport code.
5. **Domain Separation** — each Django application owns a clear business
   responsibility.
6. **Thin Views** — frontend and API views validate input, call domain
   services, and prepare responses.
7. **Selectors for Reads** — complex and optimized queries are encapsulated in
   selector functions.
8. **Historical Integrity** — snapshots and immutable history records preserve
   business state over time.
9. **Reliable Background Processing** — Celery tasks remain thin, receive
   primitive identifiers, and are scheduled through `transaction.on_commit()`
   when required.
10. **Documentation First** — architecture and operational documentation evolve
    together with the codebase.
11. **CI Before Merge** — important changes must pass automated validation
    before integration.
12. **One Logical Sprint = One Commit** — completed work is recorded in
    meaningful, focused Git commits.
13. **Explicit Technical Debt** — postponed improvements are documented in the
    roadmap or backlog instead of being hidden.

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

---

## 13. Future Architecture Direction

The current architecture is intended to support further development without a
large-scale rewrite.

Planned architectural extensions include:

- customer financial accounts and an immutable transaction ledger;
- deposits and order-payment allocation;
- returns, refunds and reverse logistics;
- withdrawal workflows and financial operations;
- Redis caching and performance optimization;
- WebSocket-based chat and real-time notifications;
- invoice revisions and document versioning;
- 1C and external supplier integrations;
- internationalization;
- production deployment, observability and release automation.

The planned financial flow is:

```text
External Payment
       │
       ▼
Account Transaction
       │
       ▼
Customer Balance
       │
       ▼
Order Payment Allocation
```

These additions will extend the existing `payments`, `orders`, `suppliers`,
`notifications` and `chat` domains while preserving their current
responsibilities.

For implementation order and phase status, see
[`roadmap.md`](roadmap.md).

