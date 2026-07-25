# Shop_ePower — GitHub Actions Plan

> **Status: DRAFT / PHASE 19**
>
> Continuous Integration will be implemented after completing the current
> Docker and documentation work.

---

## 1. Goal

Every push and pull request should automatically validate project quality.

Pipeline responsibilities:

- install dependencies
- prepare services
- Django system checks
- migration validation
- automated tests
- Docker image build
- secret safety

---

## 2. Planned Pipeline

```text
Developer Push
      │
      ▼
 GitHub Actions
      │
      ▼
Checkout Repository
      │
      ▼
Setup Python 3.14
      │
      ▼
Install Dependencies
      │
      ▼
Start PostgreSQL + Redis
      │
      ▼
Django Check
      │
      ▼
Migration Check
      │
      ▼
Automated Tests
      │
      ▼
Docker Build
      │
      ▼
✅ Pipeline Passed
```

---

## 3. Planned Jobs

### tests

- Ubuntu runner
- Python 3.14
- PostgreSQL service
- Redis service
- isolated test environment
- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test`

### docker-build

```bash
docker build -t shop-epower-ci .
```

The image will only be validated during the first phase and not published.

### code-quality (future)

After the diploma:

- Ruff
- formatting checks
- import ordering
- coverage
- static analysis

---

## 4. GitHub Secrets

Potential secrets:

```text
DJANGO_SECRET_KEY
DATABASE_PASSWORD
REGISTRY_USERNAME
REGISTRY_TOKEN
DEPLOY_SSH_KEY
```

Development secrets will never be reused in CI.

---

## 5. Triggers

```yaml
on:
  push:
    branches:
      - main
      - dev
  pull_request:
    branches:
      - main
```

---

## 6. Migration Validation

```bash
python manage.py makemigrations --check --dry-run
```

The workflow must fail whenever models change without a migration.

---

## 7. Test Database

CI always uses an isolated temporary database.

The workflow must never connect to development or production databases.

---

## 8. Future CI/CD Roadmap

```text
Push
 │
 ▼
CI
 │
 ▼
Build Image
 │
 ▼
Container Registry
 │
 ▼
Automatic Deployment
 │
 ▼
Smoke Tests
```

---

## 9. Definition of Done

- workflow stored in `.github/workflows/`
- push trigger
- pull request trigger
- Django check passes
- migration check passes
- tests pass
- Docker build passes
- CI badge added to README
- secrets remain protected
- failed pipeline blocks merge

---

## 10. Engineering Principles

- CI must be deterministic.
- Every commit should be reproducible.
- Tests must remain independent.
- Build failures should be easy to diagnose.
- CI should grow incrementally without destabilizing the project.

The initial goal is a reliable, fast feedback loop. Deployment automation will
be added only after the CI pipeline becomes stable.