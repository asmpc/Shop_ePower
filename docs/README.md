# Shop_ePower --- Technical Documentation

This directory contains the technical documentation for the
**Shop_ePower** project.

It includes architecture descriptions, Docker infrastructure guides,
deployment planning, CI documentation, and other engineering materials
that support the project's development and maintenance.

------------------------------------------------------------------------

## Documentation Index

-   **Docker Manual** (`docker.md`)\
    Daily work with Docker Compose, containers, logs, networking, Django
    management commands, Celery, and troubleshooting.

-   **Architecture** (`architecture.md`)\
    Project architecture, application boundaries, domain structure,
    infrastructure, and component interactions.

-   **Deployment** (`deployment.md`)\
    Draft production deployment plan. Full deployment will be
    implemented after the diploma defense.

-   **GitHub Actions** (`github-actions.md`)\
    Draft Continuous Integration (CI) documentation planned for **PHASE
    19**.

-   **Master Roadmap** (`roadmap.md`) *(planned)*\
    Overall development roadmap before and after the diploma defense.

------------------------------------------------------------------------

## Current Infrastructure Status

The Docker Compose environment currently includes:

-   PostgreSQL
-   Redis
-   Django Web
-   Celery Worker
-   Celery Beat
-   Flower

### Local Services

-   **Shop:** http://127.0.0.1:8000/shop/
-   **Django Admin:** http://127.0.0.1:8000/admin/
-   **Flower:** http://127.0.0.1:5555

------------------------------------------------------------------------

## Documentation Maintenance

After significant infrastructure or architectural changes, the following
documentation should be reviewed and updated:

1.  `docker.md`
2.  `architecture.md`
3.  `.env.example`
4.  Root `README.md`
5.  `roadmap.md` (when available)

Keeping the documentation synchronized with the source code is
considered part of the development process.
