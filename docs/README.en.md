<div align="center">

# ⚡ Shop_ePower

**[Русский](../README.md) | English**

### A modular B2B/B2C platform for electrical equipment

A Django platform being developed for wholesale and retail workflows:
**catalog → cart → checkout → stock reservation → manager workflow → notifications → history**

<br>

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/Django_REST_Framework-API-A30000)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-5.6-37814A?logo=celery&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Automated_Tests-871-success)
[![Shop_ePower CI](https://github.com/asmpc/Shop_ePower/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/asmpc/Shop_ePower/actions/workflows/ci.yml)


</div>

---

## 🚀 Project Overview

**Shop_ePower** is a Django platform for wholesale and retail electrical equipment sales, developed through small, tested changes.

Rather than being a simple online store, Shop_ePower is evolving into a modular business platform. Independent business domains cooperate through well-defined services, allowing the system to grow without large-scale rewrites.

The platform includes catalog and supplier inventory, stock reservation, order processing, payment status and invoice workflows, customer support chat, REST APIs, customer financial accounts, asynchronous notifications and Docker infrastructure.

PHASE 22 established the financial core. PHASE 23 now includes order-to-account
linking, checkout without automatic payments, multiple receipts per order,
an atomic receipt-credit service, and order-based invoices with cancellation
and retained history. Pre-shipment fund-assignment services use FIFO deposit
sources and support whole-assignment release and automatic release on
authorized order cancellation. Atomic full-shipment settlement is now connected
to website/API completion. Post-shipment assignment/removal services are also
implemented. Staff website receipt registration, assignment and cancellation
forms and the corresponding API actions are connected. Customer balances,
the shipped-unpaid list and actual cash/bank refunds remain in progress.
The priority path is PHASE 23 → minimal
1C integration → a controlled online test pilot without real sales or live payments.

---

## 🎯 Project Vision

The long-term vision is to evolve Shop_ePower into a complete business platform combining:

- e-commerce;
- inventory management;
- customer financial accounts;
- reverse logistics;
- ERP integrations;
- real-time communication;
- scalable cloud-ready architecture.

See the [development roadmap](roadmap.md) for completed phases, current work and deferred capabilities.

---

## 🔥 Business Workflow

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
                              CHECKOUT
                                  │
                                  ▼
                          ORDER CREATION
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
      STOCK RESERVATION     MANAGER WORKFLOW     CUSTOMER CHAT
              │                   │
              ▼                   │
       SUPPLIER STOCK             │
                    ┌─────────────┼───────────────────┐
                    ▼             ▼                   ▼
            OPTIONAL INVOICE  RECEIPT SERVICE     NOTIFICATIONS
                    │             │
                    ▼             ▼
             PDF + HISTORY   PAYMENT + ACCOUNT CREDIT
```

Checkout records the customer's financial account and payment preference,
but creates no payment or invoice. An invoice is an optional document issued
from the order, not proof of payment. The implemented receipt service records
actual office or bank funds as a confirmed payment and account credit in one
atomic operation; staff website and API registration are connected.
The implemented pre-shipment assignment service separately reserves an
explicit amount for an order from eligible FIFO deposit portions, without
creating debt. Whole-assignment release and authorized order cancellation
restore available funds while preserving history. Staff assignment/cancellation
forms and receipt/assignment/cancellation API actions are connected.
Full shipment creates its obligation and applies only previously assigned funds;
receipt or invoice creation does not automatically assign funds or settle debt.

---

## ✨ Key Features

<table>
<tr>
<td width="50%" valign="top">

### 🛍️ Product Catalog

- Categories and brands
- Product image gallery
- Product variants
- Search, filtering and sorting
- Pagination with preserved filters
- Dynamic pricing
- BYN, RUB and USD display
- Public inventory information
- Own-stock and supplier-stock separation
- Supplier lead-time display

</td>
<td width="50%" valign="top">

### 👤 Customer Accounts

- Email-based authentication
- Customer, manager and administrator roles
- Customer profile management
- Individual customer support
- Legal entity profile support
- Explicit personal account creation during registration
- Legal account creation and tax-ID snapshot validation
- Profile completeness validation
- Secure redirect back to the original workflow
- JWT authentication for REST API

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 🛒 Shopping & Checkout

- Persistent shopping cart
- Cart merge after authentication
- Price snapshots
- Checkout validation
- Required existing personal or legal financial account
- Payment preference stored on the order; no automatic payment or invoice
- Pickup and shipping workflows
- Delivery provider and address
- Customer and delivery comments
- Guest checkout onboarding flow
- Temporary online-payment restriction

</td>
<td width="50%" valign="top">

### 📦 Order Management

- Order status workflow
- Persistent link to the owner's financial account
- Customer data snapshots
- Legal entity snapshots
- Automatic stock reservation
- Oversell protection
- Manager order processing
- Delivery updates
- Controlled cancellation workflow
- Reservation rollback after cancellation
- Pre-shipment fund-assignment services with traceable FIFO deposit portions
- Whole-assignment release and automatic fund release on authorized cancellation
- Customer and manager order views
- Paginated lists with preserved filters and return links
- New and processing orders shown by default; history through explicit filters

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 💳 Payments & Invoices

- Multiple payment receipts per order
- Service for confirmed office/bank receipts with atomic, idempotent account credits
- Separate checkout preference, actual receipt and invoice workflows
- Online method retained in the model; live provider integration deferred
- Pending, paid and cancelled statuses; legacy pending/mock flows retained
- Immutable payment history
- Manager payment actions
- Administrator-only legacy resets; credited receipts protected from reset
- Invoice issuance from an order without a payment
- One issued invoice per order, enforced by a database constraint
- Cancellation and reissue with retained documents and distinct numbers
- PDF generation with ReportLab
- Owner-checked client invoice data/PDF access without a payment
- Invoice issuance and cancellation by managers and administrators on the website and API
- Required cancellation reason, actor and time
- Staff invoice history: pages of 20, PDF links and preserved return context
- Staff payment search by order, transaction ID or customer email
- Paginated staff payment results loaded after a search or filter

</td>
<td width="50%" valign="top">

### 💬 Communication

- Order-created email notifications
- Asynchronous Celery delivery
- Automatic retry and backoff
- Customer–manager chat rooms
- Free-room manager workflow
- Manager assignment
- File attachments
- Unread counters
- Customer room closing
- Paginated room lists with preserved filters and return links
- Closed rooms with unread messages remain visible to the relevant recipient

</td>
</tr>

<tr>
<td width="50%" valign="top">

### 🏢 Suppliers & Inventory

- Internal warehouse support
- External supplier support
- Supplier products
- Supplier prices and currencies
- Active/inactive inventory records
- Public inventory aggregation
- Detailed manager inventory
- Minimum lead-time calculation
- Multi-source stock reservation

</td>
<td width="50%" valign="top">

### 🔌 REST API

- Django REST Framework
- JWT login, refresh and logout
- Swagger / OpenAPI documentation
- Catalog endpoints
- Supplier endpoints
- Client order endpoints
- Manager order endpoints
- Client payment endpoints
- Manager payment actions
- Payment history endpoints
- Invoice and PDF endpoints
- Order-based invoice creation and role-checked cancellation
- Client invoice data/PDF endpoints addressed by invoice ID, not payment ID

</td>
</tr>
<tr>
<td colspan="2" valign="top">

### 💰 Customer Financial Core

- Separate personal and legal customer accounts
- Available funds and debt balance projections
- Account status lifecycle with audit history
- Atomic ledger creation and balance updates with account locking
- Idempotent operation keys and conflicting-retry validation
- Core services for deposits, debt, fund assignment, allocations, refunds and reversals
- Order-assignment and deposit-source records with positive-amount/uniqueness constraints
- Pre-shipment assignment and reversal-based release without creating debt
- Validation of amounts, actor information and resulting balances
- Read-only Django admin and staff website finance pages
- Account search, transaction journal and paginated account history
- Explicit account creation and legal-profile updates through services

Confirmed manual receipts can credit the account through an atomic service.
Pre-shipment assignment and whole-release services retain source portions
and append-only reversal history; staff and customer order cancellation
release active assignments under their existing order permissions.
Full-shipment settlement is connected to the existing completion action.
Post-shipment assignment/removal services now settle and restore the selected
shipment's debt while preserving `COMPLETED`, receipts and audit history.
The staff website receipt form records actual office/bank funds without
automatic assignment. Assignment/cancellation forms and paginated history are
connected, together with the corresponding API actions. Actual manual cash/bank
refunds and customer-facing balances remain PHASE 23 work.
The core refund service is not a real money-out payout workflow.

</td>
</tr>
</table>

---

<a id="order-funds-models"></a>

## Order Funds and Shipment Models

Status as of 2026-10-28. The model links and settlement services below are
implemented. Staff receipt registration and assignment/cancellation are connected
to the website and API; customer balances and independent concurrency checks remain open.

### Receipts and assignment — implemented

Arrows point from the model holding a reference to the referenced model.
They are database links, not automatic money movements.

```mermaid
flowchart TB
    P["Payment<br/>Confirmed receipt workflow"]
    O["Order<br/>Customer order"]
    A["OrderFundAssignment<br/>Amount assigned to an order"]
    S["OrderFundAssignmentSource<br/>Deposit portion funding an assignment"]
    T["AccountTransaction<br/>Financial ledger entry"]
    C["CustomerAccount<br/>Available funds and debt"]

    P -->|"order"| O
    P -->|"deposit_transaction · 1:1, optional"| T
    A -->|"order"| O
    A -->|"account_transaction · 1:1"| T
    S -->|"assignment"| A
    S -->|"deposit_transaction"| T
    O -->|"customer_account"| C
    T -->|"account"| C
```

- `Payment` records a confirmed receipt in the new manual receipt workflow.
  Its deposit link is optional in the schema for legacy records; legacy
  pending payments are not proof that money was received.
- `OrderFundAssignment` records which amount was explicitly assigned to an
  order. `Payment.order` alone does not assign money or settle that order.
- `OrderFundAssignmentSource` records the deposit portions used. For deposits
  of 40 and 60, an assignment of 70 has two FIFO source rows: 40 and 30.
  Available funds become 30; debt remains zero before shipment.
- `AccountTransaction` is the ledger; `CustomerAccount` stores its current
  available/debt projections. Reversals append history rather than deleting
  assignments or their source records.

### Shipment and application — full-shipment workflow implemented

`OrderShipment`, `OrderShipmentItem` and `OrderFundApplication` exist.
The diagrams show implemented model links. Full-shipment orchestration is
connected to the existing website and API completion actions as of 2026-10-20.

```mermaid
flowchart TB
    F["OrderFundApplication<br/>Application of assigned funds"]
    A["OrderFundAssignment<br/>Assigned funds"]
    H["OrderShipment<br/>Shipment and full obligation"]
    T["AccountTransaction<br/>Financial ledger entry"]
    C["CustomerAccount<br/>Customer financial account"]
    O["Order<br/>Customer order"]
    I["OrderShipmentItem<br/>Shipped item snapshots"]
    OI["OrderItem<br/>Original order line"]

    F -->|"assignment"| A
    F -->|"shipment"| H
    F -->|"account_transaction · 1:1"| T
    H -->|"order"| O
    H -->|"customer_account"| C
    H -->|"debt_transaction · 1:1"| T
    I -->|"shipment"| H
    I -->|"order_item"| OI
    OI -->|"order"| O

```

`OrderShipment` retains the order, account, obligation transaction, full amount,
currency, actor and time. Currently a database constraint permits only one
shipment per order; the underlying foreign key leaves room for future partial
shipments. One debt transaction cannot be reused for multiple shipments.

`OrderShipmentItem` retains the original order-line link and independent name,
unit-price, quantity, total and currency snapshots. Quantity must be positive;
an order line cannot repeat within one shipment. Independent snapshot storage
is implemented, and the shipment service automatically copies the order lines.
It validates a non-empty order and the saved total against items and shop-paid
delivery. Snapshot storage alone does not prevent direct historical edits;
broader edit protection and independent concurrent-workflow coverage remain open.

`OrderFundApplication` stores `assignment`, `shipment`, `account_transaction`,
`amount` and `created_at`. Its three model tests and scoped Ruff checks pass;
amount must be positive and the financial entry cannot be reused.
Assignment and shipment use
foreign keys for future partial shipments; the financial entry is one-to-one.
The service must validate matching order, account and currency, active
assignment capacity and the shipment's outstanding obligation.

### Implemented full-shipment settlement example

For a 100 order, a receipt of 100 and an explicit assignment of 60:

| Action | AccountTransaction type | Available | Debt |
|---|---|---:|---:|
| Confirm receipt | `DEPOSIT` | 100 | 0 |
| Assign 60 to the order | `FUNDS_ASSIGNMENT` | 40 | 0 |
| Record full shipment of 100 | `DEBT_INCREASE` | 40 | 100 |
| Apply the assigned 60 | `FUNDS_APPLICATION` | 40 | 40 |

These are four entry types of the same `AccountTransaction` model.
The shipment obligation uses the saved `Order.total_price`: delivery paid to
the shop is included; delivery paid separately to the carrier is excluded.
The last two steps must commit atomically, so the intermediate debt of 100
is not exposed as a committed state. Already assigned money is not deducted
from available funds again. Existing `allocate_customer_funds()` decreases
both balances and is unsuitable for this application step.

`record_customer_funds_application()` is implemented: available delta is zero,
debt delta is minus the positive amount. The order/shipment service must prove
the matching assignment; the low-level finance function alone does not.
`Complete order` now uses `complete_order_shipment()`: the shipment, item
snapshots, full obligation, application of active pre-shipment assignments and
`COMPLETED` status commit atomically. A permitted retry returns the existing
shipment without repeating money movements. Cancelled assignments are excluded;
shipment-level limits prevent using unrelated account debt as capacity.
Post-shipment assignment/removal services are implemented as of 2026-10-22.
For a shipped order of 100 with available funds of 100 and debt of 100,
assigning 60 records `FUNDS_ASSIGNMENT` and `FUNDS_APPLICATION` atomically:
available funds become 40 and debt becomes 40. Whole-assignment removal adds
two `REVERSAL` entries, restoring available funds and debt to 100. The receipt,
shipment and original assignment/application records remain; the order stays
`COMPLETED`. Same-key retries do not repeat balance changes. Dedicated staff
receipt registration and assignment/cancellation are connected to the website
and API. Independent concurrency tests remain pending.

### Full-shipment confirmation — agreed scope

The website completion form now requests explicit browser confirmation: "Confirm full shipment of order #...? Once confirmed, shipment
cannot be cancelled and order items cannot be edited on the website."
Cancelling the dialog sends no completion request and changes nothing.

PHASE 23 does not implement correction/reopening of a confirmed shipment:
no correction action, shipment-reversal service, corrected-shipment state or
replacement-shipment flow. Keep the existing one-shipment-per-order constraint,
not a conditional "one active shipment" constraint. A real goods return remains
a separate deferred workflow. An accidentally confirmed shipment cannot be
corrected through the standard website workflow in this scope.

The dialog reduces accidental clicks, not deliberate abuse. Server-side
authorization, status/consistency checks, locking, atomicity and idempotent retry
remain mandatory. Assignment removal, receipt correction and actual cash/bank
refunds remain separate agreed money workflows; they do not reopen shipment.

See the [PHASE 23 plan](phase-23-deposits-and-order-settlement.md#order-funds-models)
for implementation boundaries and remaining work.

---

## 🏗️ Architecture

Shop_ePower uses modular Django applications. Each application owns a specific business responsibility, while services and selectors keep business rules separate from presentation and transport layers.

### Application Responsibilities

| Application | Responsibility |
|---|---|
| `accounts` | Users, roles, authentication, customer profiles and legal entities |
| `catalog` | Products, categories, brands, images, variants and public catalog |
| `suppliers` | Suppliers, supplier products, warehouse and external inventory |
| `cart` | Shopping cart, cart items and price snapshots |
| `orders` | Checkout, orders, stock reservation, delivery, fund-assignment sources and release on cancellation |
| `payments` | Confirmed receipt services, legacy payment transitions, invoice lifecycle, history and PDF generation |
| `finance` | Personal and legal financial accounts, transaction ledger, atomic balance services, status history and staff finance views |
| `notifications` | Email services and asynchronous notification tasks |
| `chat` | Rooms, messages, attachments, assignment and unread state |
| `api` | REST API endpoints, serializers and permissions |
| `core` | Shared currency, pricing, settings, utilities and infrastructure |

### Application Architecture

```mermaid
flowchart TD
    Customer([Customer])
    Manager([Manager / Admin])

    Accounts[accounts]
    Catalog[catalog]
    Suppliers[suppliers]
    Cart[cart]
    Orders[orders]
    Payments[payments]
    Finance[finance]
    Notifications[notifications]
    Chat[chat]
    API[api]
    Core[core]

    Customer --> Accounts
    Customer --> Catalog
    Customer --> Cart
    Customer --> Orders
    Customer --> Payments
    Customer --> Chat

    Manager --> Orders
    Manager --> Payments
    Manager --> Finance
    Manager --> Chat
    Manager --> Suppliers

    Accounts --> Cart
    Accounts --> Orders
    Accounts --> Finance
    Catalog --> Cart
    Catalog --> Orders
    Suppliers --> Orders
    Cart --> Orders
    Orders --> Payments
    Orders --> Finance
    Orders --> Notifications
    Orders --> Chat
    Payments --> Notifications
    Payments --> Finance

    Accounts --> API
    Catalog --> API
    Suppliers --> API
    Orders --> API
    Payments --> API

    Core -. shared services .-> Accounts
    Core -. shared services .-> Catalog
    Core -. shared services .-> Suppliers
    Core -. shared services .-> Orders
    Core -. shared services .-> Payments
    Core -. shared services .-> Finance
```

### Infrastructure Architecture

```mermaid
flowchart LR
    Browser[Browser] --> Web[Django Web :8000]

    Web --> PostgreSQL[(PostgreSQL)]
    Web --> Redis[(Redis)]
    Web --> Worker[Celery Worker]

    Beat[Celery Beat] --> Redis
    Redis --> Worker

    Worker --> PostgreSQL
    Worker --> Email[Email Backend]

    Flower[Flower :5555] --> Redis
    Flower --> Worker
```

### Design Principles

- Clear separation of business domains
- Thin views and API views
- Service-layer commands for business operations
- Selectors for optimized read operations
- Snapshot data for historical integrity
- Explicit permissions for client, manager and administrator roles
- Celery tasks as thin orchestration functions
- Primitive identifiers passed through task queues
- `transaction.on_commit()` for post-transaction tasks
- Regression tests for every discovered production-like issue
- Technical debt documented instead of hidden

---

## 🧭 Design Principles

The project follows a small set of engineering principles.

- **Business First** — business requirements drive architecture.
- **Evolution over Revolution ⭐** — existing, working components are evolved instead of rewritten. New functionality extends the current architecture while preserving stability whenever practical.
- **Test Driven Development** — new functionality is protected by automated tests.
- **Clean Architecture** — business logic belongs in services and domain layers.
- **Domain Separation** — each application owns a single business responsibility.
- **Documentation First** — documentation evolves together with the code.
- **CI Before Merge** — important changes should pass automated validation.
- **One Logical Sprint = One Commit** — each completed sprint ends with a meaningful Git commit.

---

## ⚙️ Technology Stack

| Layer | Technologies |
|---|---|
| Language | Python 3.14 |
| Web Framework | Django 6.0.5 |
| Dependency Management | Poetry and poetry.lock |
| REST API | Django REST Framework, Simple JWT |
| API Documentation | drf-spectacular, Swagger / OpenAPI |
| Database | PostgreSQL |
| Cache & Broker | Redis |
| Background Tasks | Celery |
| Scheduler | django-celery-beat |
| Monitoring | Flower |
| PDF Generation | ReportLab |
| Frontend | Django Templates, Bootstrap, JavaScript |
| Infrastructure | Docker, Docker Compose |
| Testing | Django TestCase, DRF API tests, regression tests |
| Code Quality | Ruff |
| Version Control | Git, GitHub |
| Continuous Integration | GitHub Actions |
| Container Registry | GitHub Container Registry (GHCR) |

---

## 🚀 Quick Start with Docker

### 1. Clone the Repository

```bash
git clone https://github.com/asmpc/Shop_ePower.git
cd Shop_ePower
```

### 2. Create the Environment File

Linux / macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Update the values in `.env` before starting the project.

### 3. Build the Image and Start PostgreSQL / Redis

```bash
docker compose build
docker compose up -d --wait postgres redis
```

### 4. Apply Database Migrations

```bash
docker compose run --rm --no-deps web python manage.py migrate
```

### 5. Start the Full Stack

```bash
docker compose up -d --wait
```

Applying migrations before starting all application services allows the
web health check to succeed on a fresh database.

### 6. Create a Django Administrator

```bash
docker compose exec web python manage.py createsuperuser
```

Application roles (`CLIENT`, `MANAGER`, `ADMIN`) are separate from Django's
staff and superuser flags. Assign the appropriate application role through
the user form in Django admin to access staff pages on the website.
Customer registration and legal-profile services create financial accounts;
manually created demonstration users may require explicit account setup
before checkout.

### 7. Open the Application

| Service | Address |
|---|---|
| Shop | <http://127.0.0.1:8000/shop/> |
| Django Admin | <http://127.0.0.1:8000/admin/> |
| Swagger / OpenAPI | <http://127.0.0.1:8000/api/schema/swagger-ui/> |
| Flower | <http://127.0.0.1:5555> |

---

## 🐳 Docker Compose Services

| Service | Purpose | Host Port |
|---|---|---:|
| `web` | Django development web server | `8000` |
| `postgres` | PostgreSQL database | `5433` |
| `redis` | Celery broker and result backend | `6380` |
| `celery_worker` | Background task execution | — |
| `celery_beat` | Database-backed periodic task scheduler | — |
| `flower` | Celery monitoring dashboard | `5555` |

The application services use one shared Docker image with different startup commands.

Persistent Docker volumes preserve:

- PostgreSQL data;
- Redis data.

The development bind mount:

```yaml
./src:/app/src
```

allows source-code and template changes to appear inside the running container without rebuilding the image.

---

## 🔧 Useful Commands

### Environment

```bash
docker compose up -d
docker compose ps
docker compose restart
docker compose down
```

### Logs

```bash
docker compose logs -f web
docker compose logs -f celery_worker
docker compose logs -f celery_beat
docker compose logs -f flower
```

### Django

```bash
docker compose exec web python manage.py check
docker compose exec web python manage.py showmigrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py shell
```

### Tests

```bash
docker compose exec web python manage.py test
```

Run a specific test module:

```bash
docker compose exec web python manage.py test shop_epower.catalog.tests.test_product_list_inventory
```

### Celery

```bash
docker compose exec celery_worker celery -A config inspect ping
docker compose exec celery_worker celery -A config inspect registered
docker compose exec celery_worker celery -A config inspect active
```

### Local Poetry Environment

Run these commands from the repository root after configuring `.env` and
making PostgreSQL and Redis available to the local application:

```bash
poetry install --no-root
poetry run python src/manage.py check
poetry run python src/manage.py makemigrations --check --dry-run
poetry run ruff check src
poetry run python src/manage.py test
```

When working inside `src`, use `manage.py` instead of `src/manage.py`.
The application Docker image installs runtime dependencies; local Poetry
and the CI quality job also install the development tools.

More commands and troubleshooting instructions are available in [`docs/docker.md`](docker.md).

---

## 🌐 REST API

The project exposes client, manager and administrator workflows through Django REST Framework.

### Main API Areas

- authentication and JWT tokens;
- product catalog;
- suppliers and supplier products;
- client checkout and orders;
- manager order processing;
- client payments;
- manager payment actions;
- payment history;
- invoice details;
- PDF invoice downloads;
- invoice creation by order ID, and client document/PDF access by invoice ID;
- invoice cancellation by managers and administrators with a required reason.

### Staff money actions

Managers and administrators can perform these actions; customer POSTs are forbidden.

| Action | POST endpoint | Result |
|---|---|---|
| Confirm receipt | `/api/payments/manage/orders/{order_id}/receipts/` | A PAID Payment and an available-balance credit |
| Assign order funds | `/api/orders/manage/{order_id}/funds/assign/` | An assignment; after shipment, settlement of its corresponding debt |
| Cancel assignment | `/api/orders/manage/fund-assignments/{assignment_id}/cancel/` | Reversal entries; the receipt and shipment are retained |

Receipts require `amount`, `method` and `operation_key`, with optional `comment`.
Manual methods are `on_receipt` (office) and `invoice` (bank transfer);
this action cannot confirm online payments. An Invoice is neither required
nor created automatically. Assignment takes `amount`, `operation_key` and
optional `comment`; cancellation takes `operation_key` and a required non-blank
`comment`. Cancellation applies to the whole selected assignment, without an amount field.

The caller supplies the key. Same-key retries do not repeat money movements;
changed data under an existing key is rejected. A new-key second cancellation
is also rejected. Successful receipt/assignment returns 201, including safe
retries; cancellation returns 200 with `assignment_id` and `reversal_id`.
Invalid data/business-rule failures return 400; authenticated customer POSTs
return 403.

Swagger / OpenAPI documentation is available at
[`/api/schema/swagger-ui/`](http://127.0.0.1:8000/api/schema/swagger-ui/),
with the schema at [`/api/schema/`](http://127.0.0.1:8000/api/schema/).

---

## 🧪 Testing

Shop_ePower is developed with a strong automated-testing focus.

The latest verified full run passed **871 tests in 1076.950 seconds on
2026-10-28**, including full-shipment website/API integration, staff
assignment/cancellation pages and 25 new money API tests. Tests run
against an isolated PostgreSQL test database. GitHub Actions is configured
to execute the full suite on pushes to `dev` and `main`, and on pull requests
targeting `main`.

The shipment-service module has 19 passing tests. Related order workflow,
staff-page and API modules, scoped Ruff and migration-drift checks also pass.
The user applied the new finance/order migrations to the runtime database and
manually confirmed that completing an unpaid order adds its full obligation
without changing available funds. Independent concurrency coverage for the new
shipment/assignment workflows remains open; the full suite does not prove it.
On 2026-10-25 the user reported all 13 cancellation-view tests, related assignment
view/selector and manager-order-view modules, and Ruff passing. Assignment,
cancellation and retained order-list filters were also checked manually.
After these checks, the user also ran the full project suite: all 846 tests passed.

The test suite covers:

- Django models;
- selectors;
- service-layer business rules;
- frontend views;
- checkout and profile workflows;
- stock reservation and rollback;
- payment transitions;
- financial account lifecycle, ledger entries and balance projections;
- idempotency, allocation limits, reversals, rollback and concurrent operations;
- permissions;
- invoice lifecycle;
- PDF responses;
- REST API endpoints;
- asynchronous notification integration;
- regression scenarios found during manual testing.

Examples of protected regressions include:

- profile completion before checkout;
- secure redirect through the `next` parameter;
- inventory quantity and supplier lead time in catalog cards;
- payment state-transition validation;
- administrator-only legacy reset and protection of financially credited receipts;
- checkout without an automatic payment, actual receipt registration and idempotent account credits;
- order-based invoice issuance without payment, cancellation and reissue;
- client invoice/PDF ownership checks and paginated staff invoice history;
- order-to-account linking and rejection of checkout without the matching account;
- FIFO funding portions, active-use limits and idempotent pre-shipment assignment;
- whole-assignment release, retained history and reuse of released funds;
- automatic release on authorized staff/customer order cancellation and rollback on failure;
- list pagination, preserved filters and safe return navigation;
- unread-message visibility and closed-room behavior by role.

---

## ✅ Continuous Integration

Shop_ePower uses GitHub Actions as an automated quality gate.

```text
Push to dev / main OR pull request to main
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
      Django CI          Ruff Quality
  PostgreSQL / Redis     Poetry + Ruff
  Checks + migrations
  Full test suite
          │                   │
          └─────────┬─────────┘
                    ▼
             Docker image build
                    │
                    ▼
      Image checks + container smoke test
                    │
                    ▼
       Full Docker Compose integration
                    │
                    ▼
      GHCR publishing on push events only
```

The CI workflow currently provides:

- execution on pushes to `dev` and `main`;
- execution for pull requests targeting `main`;
- Python 3.14 setup;
- Poetry installation and dependencies from the lock file;
- isolated PostgreSQL and Redis service containers;
- service health checks;
- Django configuration validation;
- real PostgreSQL and Redis connection checks;
- protection against forgotten migrations;
- execution of the full automated test suite;
- a separate Ruff quality job;
- a Docker build after the test and quality jobs succeed;
- Docker layer caching through GitHub Actions;
- Django checks and a container smoke test;
- full Compose startup with migrations, web, Flower, worker and Beat checks;
- image publishing to GHCR on pushes, with `dev`, `latest` and commit tags
  according to the branch.

The workflow is stored in:

```text
.github/workflows/ci.yml
```

Image publishing is already configured. Deployment automation remains later
work; the immediate delivery target is the controlled test pilot after
PHASE 23 settlement integration and PHASE 24 minimal 1C exchange.

---

## 📚 Documentation

Technical documentation is stored in the [`docs/`](./) directory.

| Document | Description |
|---|---|
| [`docs/docker.md`](docker.md) | Docker commands, logs, diagnostics and daily workflow |
| [`docs/architecture.md`](architecture.md) | Current project and infrastructure architecture |
| [`docs/deployment.md`](deployment.md) | Production deployment plan |
| [`docs/github-actions.md`](github-actions.md) | Current CI workflow and future CI/CD plan |
| [`docs/roadmap.md`](roadmap.md) | Master development roadmap |
| [`docs/phase-22-customer-financial-core.md`](phase-22-customer-financial-core.md) | Financial core rules and completed PHASE 22 work |
| [`docs/phase-23-deposits-and-order-settlement.md`](phase-23-deposits-and-order-settlement.md) | Current order funds and shipment settlement design |

Documentation records both implemented behavior and planned work. The
roadmap and current phase plan identify the remaining integration tasks.

---

## 📈 Project Status

### ✅ Completed

- Catalog, pricing, suppliers and inventory
- Customer profiles, authentication and authorization roles
- Shopping cart, checkout, orders and stock reservations
- Delivery, cancellation and reservation rollback
- Payment status workflows, invoices and PDF documents
- Email notifications and customer–manager chat
- Client and staff REST APIs
- Poetry dependency management and shared test helpers
- Ruff quality checks
- Docker Compose infrastructure
- GitHub Actions checks, Docker integration tests and GHCR publishing
- PHASE 22: personal and legal financial accounts, atomic financial
  services, transaction ledger and account status history
- Read-only staff finance pages with search, filters and pagination
- Paginated order and chat lists with preserved navigation
- New orders linked to the owner's matching financial account
- Website/API checkout stores a payment preference without creating a payment
- Multiple receipts per order and an atomic manual receipt-credit service
- Pre-shipment assignment/release services with FIFO sources and retained history
- Automatic fund release during authorized customer and staff order cancellation
- Order-based invoice issuance, staff cancellation and reissue with retained history
- Payment-independent client invoice data/PDF access and paginated staff history
- Removal of active failed-payment paths; historical data preserved
- Full suite of 871 tests passed in 1076.950 seconds on 2026-10-28
- Atomic full shipment, independent item snapshots and prepayment application
  connected to website/API completion; browser confirmation and staff-only POST
- Runtime finance/order migrations applied and unpaid-shipment debt checked manually
- Post-shipment assignment/removal services: assignment-service module and scoped
  Ruff passed on 2026-10-22; the subsequent full 846-test run passed on 2026-10-25
- Staff website receipt registration: office/bank funds, safe same-key retries,
  validation errors and preserved navigation; related modules and scoped Ruff pass
- Staff website assignment/cancellation and paginated history: 13 cancellation-view
  tests and related modules plus Ruff passed on 2026-10-25; manual actions and
  preserved order-list filters confirmed

### 🚧 Current Work

**PHASE 23 — Order Funds & Full-Shipment Settlement**

The account link, receipt-service foundation, website/API invoice block,
and pre-shipment assignment/release services are implemented. New orders
require the matching financial account; invoices do not require a payment
and do not themselves change funds or debt. Existing authorized order
cancellation now releases active assignments atomically.

Shipment and shipment-item records and the debt-only application primitive
are now implemented and scoped-tested, together with `OrderFundApplication`.
`Complete order` is connected through the existing website and API status action;
the website asks for confirmation, and unauthorized completion POSTs return 403.
Shipment correction/reopening remains out of PHASE 23 scope.

Post-shipment assignment/removal services are implemented and module-tested.
A matching recorded shipment is required; order limits, same-key retries,
rollback and reuse after cancellation are covered. Assignment removal restores
available funds and the corresponding debt, preserving `COMPLETED`, the receipt
and historical rows. The user reports the module and scoped Ruff passing on
2026-10-22; at that service checkpoint no new full-project run or manual
assignment/removal check was claimed.

Staff website receipt registration is implemented: managers/admins record actual
office/bank funds through the atomic service, without assigning them to the order.
The form preserves its operation key on errors; same-key retries and conflicting
data are tested. Order/list navigation context is retained. The user reports
receipt-view, receipt-service and manager-order-view modules plus scoped Ruff
passing. Manual website checks confirmed form opening, return navigation and
actual receipt registration: available funds increase by the received amount,
while debt remains unchanged. The subsequent full 846-test run passed on 2026-10-25.

Staff assignment/cancellation forms are implemented as of 2026-10-25. They use
the atomic services; paginated history retains the assignment, cancellation
reason and actor. Cancellation requires a non-blank reason; same-key retries
are safe and a new-key second cancellation shows an error without another credit.
Customer POST is forbidden. Links, hidden next fields and return navigation
preserve the original order-list filter/page. All 13 cancellation-view tests,
related assignment-view/selector and existing manager-order-view modules, and
Ruff passed. Manual assignment/cancellation and filter preservation were
confirmed. At that website milestone, the full suite passed 846 tests on 2026-10-25.

As of 2026-10-28, receipt registration, assignment and whole-assignment
cancellation API actions delegate to the existing atomic services. The 25 new
tests (8 receipt, 9 assignment, 8 cancellation) cover permissions, amounts,
required keys/reasons, retries, conflicting keys and retained history.
Post-shipment assignment/cancellation retain COMPLETED. The user reports related
order/payment API modules, receipt/assignment service modules, Ruff and
git diff --check passing. No models changed and no new migration is required.
The subsequent full suite passed **871 tests in 1076.950 seconds on
2026-10-28**. Project-wide Ruff passed; git diff --check reported only
LF/CRLF warnings, with no whitespace errors. Independent concurrency
verification remains open.

Next: customer balances and shipped-but-unpaid order lists. Remaining work includes
pre-shipment order editing, safe receipt corrections, independent concurrency
verification and actual manual cash/bank refunds.

Receipt confirmation, assigning funds to an order, shipment settlement and
real payout are separate actions. Existing debt allocation cannot substitute
for pre-shipment assignment. Before order-item editing, preserve invoice-item
snapshots so historical PDFs cannot change with the order.

### 🗺️ Next Milestones

- PHASE 24: minimal 1C integration using an agreed exchange contract
- PHASE 25: an internet-accessible test pilot without real sales or live payments

Further capabilities remain in the [roadmap](roadmap.md), including
partial shipments, external payment providers, goods-return logistics, caching,
internationalization and WebSocket communication.

---

## 🛣️ Engineering Roadmap

```text
COMPLETED
   ├── PHASE 20 — Poetry and dependency modernization
   ├── PHASE 21 — Shared test helpers and Ruff
   └── PHASE 22 — Customer financial core
        │
        ▼
PHASE 23 — Order funds and full-shipment settlement 🚧
        │
        ▼
PHASE 24 — Minimal 1C integration
        │
        ▼
PHASE 25 — Controlled online test pilot
           No real sales or live payments
        │
        ▼
FURTHER DEVELOPMENT
   Prioritized from pilot feedback and business needs
   See docs/roadmap.md
```

---

## 👨‍💻 Project

Shop_ePower is a personal diploma project created and developed by **Alexander Morozov**.

The project has been built through an iterative engineering process with extensive architectural discussions, code reviews, technical planning, and development support provided by ChatGPT.

The primary goals of this project are:

- applying modern Django engineering practices;
- learning to make architectural decisions instead of copying solutions;
- designing a scalable and maintainable system;
- following Test-Driven Development;
- mastering Docker, PostgreSQL, Redis and Celery;
- creating a strong foundation for continued development after graduation.

---

<div align="center">

## ⚡ Thank You for Visiting Shop_ePower

**The diploma defense is a milestone — not the end of the project.**

Shop_ePower will continue to evolve as a long-term engineering and portfolio project.

</div>
