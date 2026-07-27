# Shop_ePower — Master Roadmap v3

> Living roadmap describing completed milestones, current engineering work,
> future development and the review process used after major phases.
>
> Last updated: July 2026.

---

## Status Legend

| Symbol | Meaning |
|:---:|---|
| ✅ | Completed |
| 🚧 | In progress |
| ⏳ | Planned |
| 📋 | Backlog / future |
| 🔁 | Continuous improvement |

---

## 🗺️ Project Journey

```text
PHASE 1–18    ✅ Core Platform
      │
      ▼
PHASE 18.8    ✅ Docker & Documentation
      │
      ▼
PHASE 19      🚧 GitHub Actions
      │
      ├── Sprint 1 ✅ CI Foundation
      ├── Sprint 2 🚧 Docker Build in CI
      └── Sprint 3 ⏳ Release Preparation
      │
      ▼
PHASE 19.5    ⏳ Developer Environment
      │
      ▼
PHASE 20      ⏳ Production Deployment
      │
      ▼
PHASE 21      ⏳ CI/CD & Release Automation
      │
      ▼
PHASE 22      ⏳ Performance & Redis Cache
      │
      ▼
PHASE 23      ⏳ WebSockets & Real-Time Features
      │
      ▼
PHASE 24      ⏳ Invoice Revisions
      │
      ▼
PHASE 25      ⏳ 1C & Supplier Integrations
      │
      ▼
PHASE 26      📋 Full Internationalization
```

---

## ✅ Completed Milestones

### Core Platform

- Modular Django architecture
- Custom User model
- CLIENT / MANAGER / ADMIN roles
- Authentication and authorization
- Service layer
- Selector pattern
- Snapshot-based business history

### Catalog

- Categories and brands
- Products and product images
- Product variants
- Search, filters and pagination
- Dynamic pricing
- Multi-currency display
- Public inventory information

### Accounts

- Customer profile
- Legal entity support
- Profile completeness validation
- Checkout protection for incomplete profiles

### Suppliers & Inventory

- Internal warehouse
- External suppliers
- Supplier prices
- Stock aggregation
- Lead-time calculation
- Stock reservation

### Cart & Orders

- Shopping cart
- Guest/user cart merge
- Checkout
- Order lifecycle
- Delivery workflow
- Manager workflow
- Cancellation workflow
- Stock release on cancellation

### Payments & Invoices

- Payment lifecycle
- Payment history
- Manager and administrator actions
- Client payment endpoints
- Invoice generation
- Invoice cancellation
- PDF generation with ReportLab
- Client PDF access

### Communication

- Email notifications
- Celery-based asynchronous tasks
- Customer-manager chat
- Manager room pickup
- Attachments
- Unread counters
- Room closing workflow

### REST API

- Accounts API
- Catalog API
- Suppliers API
- Orders API
- Payments API
- Invoice API
- JWT authentication
- OpenAPI / Swagger

### Infrastructure

- Docker Compose
- Django Web container
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat
- Flower
- Health checks
- Persistent volumes
- Development bind mount

### Quality & Documentation

- **465 automated tests**
- Regression tests
- Django system checks
- Migration consistency checks
- Technical documentation
- Docker operations guide
- Architecture document
- Deployment plan
- GitHub Actions plan
- Professional project README

---

## 🚧 Current Phase

# PHASE 19 — GitHub Actions

## Sprint 1 — CI Foundation ✅ COMPLETE

Implemented:

- `.github/workflows/ci.yml`
- workflow triggers for `dev` and `main`
- pull request validation for `main`
- Python 3.14 setup
- pip dependency caching
- GitHub Actions secret for Django `SECRET_KEY`
- PostgreSQL service container
- Redis service container
- PostgreSQL health check
- Redis health check
- Django system check
- real PostgreSQL connection check
- real Redis connection check
- missing migration check
- complete execution of **465 automated tests**
- protected `main` branch through GitHub Rulesets
- required `Django CI` status before merge
- updated README with live CI badge

Result:

```text
Push / Pull Request
        │
        ▼
GitHub Actions
        │
        ▼
Python + Dependencies
        │
        ▼
PostgreSQL + Redis
        │
        ▼
Django Checks
        │
        ▼
Migration Validation
        │
        ▼
465 Tests
        │
        ▼
Required Django CI Status
```

---

## Sprint 2 — Docker Integration 🚧 CURRENT

Goals:

- Docker image build in GitHub Actions
- Dockerfile validation
- Docker Compose configuration validation
- Docker layer caching
- container startup smoke test
- Django check inside the built image
- confirmation that the CI-built image matches the local Docker workflow

Definition of Done:

- Docker image builds successfully on every relevant push and pull request
- invalid Dockerfile changes fail the pipeline
- invalid Compose configuration fails the pipeline
- built container starts successfully
- basic smoke checks pass

---

## Sprint 3 — Release Preparation ⏳ PLANNED

Goals:

- release workflow design
- version tagging strategy
- GitHub Release preparation
- production image build
- container registry evaluation
- release notes
- deployment handoff

---

## ⏳ Next Phase

# PHASE 19.5 — Developer Environment

Purpose:

Create a professional and reproducible development environment that improves
productivity, reduces accidental errors and supports future infrastructure work.

Planned work:

- PyCharm GitHub Actions plugin
- Docker integration in PyCharm
- `.env` file support
- YAML validation
- recommended inspections
- live templates
- useful hotkeys
- formatter and import settings
- test run configurations
- GitHub integration
- IDE setup documentation

This phase does not change business functionality, but improves development
speed, consistency and maintainability.

---

## ⏳ Planned After Diploma

# PHASE 20 — Production Deployment

- Linux server
- Gunicorn
- Nginx
- HTTPS
- production settings
- static and media strategy
- PostgreSQL backup strategy
- Redis and Celery production configuration
- Flower protection
- logging
- health checks
- rollback documentation

# PHASE 21 — CI/CD & Release Automation

- production container registry
- automated image publishing
- deployment workflow
- production secrets
- release tags
- smoke tests after deployment
- rollback automation

# PHASE 22 — Performance & Redis Cache

- catalog caching
- inventory caching
- cache invalidation rules
- query optimization
- performance measurements
- load testing

# PHASE 23 — WebSockets & Real-Time Features

- WebSocket chat
- real-time unread counters
- real-time order updates
- real-time notifications
- reconnect strategy
- channel-layer infrastructure

# PHASE 24 — Invoice Revisions

- replace `Invoice → Payment` OneToOne relation with ForeignKey
- multiple invoice versions
- previous invoice link
- active invoice selection
- reissue after cancellation
- preservation of historical PDFs

# PHASE 25 — 1C & Supplier Integrations

- 1C integration
- external supplier imports
- product synchronization
- price synchronization
- stock synchronization
- retry and error-handling strategy
- audit history

# PHASE 26 — Full Internationalization

- complete RU/EN translation
- localized validation messages
- localized emails
- localized invoices
- translation maintenance workflow

---

## 🔁 Continuous Improvement Backlog

- global test helper refactoring
- test-data factories by domain
- code-quality tooling
- coverage reporting
- security scanning
- dependency update automation
- monitoring and metrics
- centralized logging
- performance profiling
- accessibility improvements

---

## 📚 Project Review Process

After every completed major phase, a separate Project Review will be created.

Planned structure:

```text
docs/
└── project-reviews/
    ├── phase-18-8-docker-documentation.md
    ├── phase-19-github-actions.md
    ├── phase-20-production-deployment.md
    └── ...
```

Each Project Review will contain:

1. **Phase Goal**
2. **Initial State**
3. **Implemented Work**
4. **Architecture and Engineering Decisions**
5. **Problems Encountered**
6. **How Problems Were Solved**
7. **Testing and Verification**
8. **Lessons Learned**
9. **Deferred Work**
10. **Next Phase**

The first new review will be created after the full completion of
**PHASE 19 — GitHub Actions**.

Project Reviews will form the engineering history of Shop_ePower and explain
not only what was implemented, but also why the project evolved in that way.

---

## 🎯 Long-Term Vision

Shop_ePower is intended to evolve from a diploma project into a
production-quality portfolio application demonstrating:

- clean modular architecture;
- business-oriented Django development;
- automated testing;
- containerized infrastructure;
- continuous integration;
- safe release processes;
- maintainable technical documentation;
- incremental engineering growth;
- readiness for production deployment and external integrations.

The diploma defense is an important milestone, but not the end of the project.
