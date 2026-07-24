# Shop_ePower — Technical Documentation

Этот каталог содержит техническую документацию проекта Shop_ePower.

## Документы

- [Docker Manual](docker.md) — ежедневная работа с Docker Compose: запуск, остановка, логи, порты, Django-команды, Celery и диагностика.
- [Architecture](architecture.md) — текущая архитектура проекта, доменные границы и инфраструктурная схема.
- [Deployment](deployment.md) — черновик плана production-развёртывания. Реализация запланирована после защиты.
- [GitHub Actions](github-actions.md) — черновик будущего CI-процесса для PHASE 19.

## Текущий статус

Через Docker Compose работают:

- PostgreSQL;
- Redis;
- Django Web;
- Celery Worker;
- Celery Beat;
- Flower.

Основные адреса:

- Shop_ePower: http://127.0.0.1:8000/shop/
- Django Admin: http://127.0.0.1:8000/admin/
- Flower: http://127.0.0.1:5555

## Правило актуализации

После существенных инфраструктурных изменений обновляются:

1. `docker.md`;
2. `architecture.md`;
3. `.env.example`;
4. главный `README.md`;
5. Master Roadmap.
