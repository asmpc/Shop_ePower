# Shop_ePower — GitHub Actions Plan

> **Статус: DRAFT / PHASE 19**  
> Workflow ещё не реализован.

## 1. Цель

Каждый push и pull request автоматически проверяет:

- установку зависимостей;
- Django system checks;
- наличие забытых миграций;
- тесты;
- Docker build;
- отсутствие случайных секретов.

## 2. Pipeline

```text
Checkout
  ↓
Python setup
  ↓
Install dependencies
  ↓
PostgreSQL + Redis
  ↓
Django check
  ↓
Migration check
  ↓
Tests
  ↓
Docker build
```

## 3. Jobs

### tests

- Ubuntu runner;
- Python 3.14;
- PostgreSQL service;
- Redis service;
- test environment variables;
- `python manage.py check`;
- `python manage.py makemigrations --check --dry-run`;
- `python manage.py test`.

### docker-build

```powershell
docker build -t shop-epower-ci .
```

На первом этапе image не публикуется.

### code-quality — опционально

После согласования:

- Ruff;
- formatting check;
- import ordering;
- coverage.

До защиты не добавлять инструмент, требующий массового изменения стабильного кода.

## 4. Secrets

Возможные будущие GitHub Secrets:

```text
DJANGO_SECRET_KEY
DATABASE_PASSWORD
REGISTRY_USERNAME
REGISTRY_TOKEN
DEPLOY_SSH_KEY
```

Для тестов использовать отдельные безопасные test values.

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

## 6. Migration validation

```powershell
python manage.py makemigrations --check --dry-run
```

Pipeline падает, если разработчик изменил модели и забыл миграцию.

## 7. Test database

CI использует временную базу и никогда не подключается к development/production.

## 8. Дальнейшее развитие

```text
build
  ↓
tag
  ↓
push registry
  ↓
deploy
```

## 9. Definition of Done PHASE 19

- workflow в `.github/workflows/`;
- push и PR triggers;
- Django check зелёный;
- migration check зелёный;
- тесты зелёные;
- Docker build зелёный;
- CI badge;
- секреты не выводятся;
- failure блокирует merge в main.
