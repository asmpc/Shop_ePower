# Shop_ePower — Deployment Plan

> **Status: Planned after the diploma defense**
>
> Production deployment is intentionally scheduled for the post-diploma roadmap.
> The current Docker Compose environment is optimized for development, learning,
> testing and feature implementation.

---

## 1. Deployment Goals

Deploy Shop_ePower to a Linux server with:

- Nginx reverse proxy
- HTTPS (Let's Encrypt)
- Gunicorn application server
- Django
- PostgreSQL
- Redis
- Celery Worker
- Celery Beat
- persistent storage
- automated backups
- monitoring
- safe database migrations

---

## 2. Target Production Architecture

```text
                    Internet
                        │
                        ▼
              Nginx (HTTPS / TLS)
                        │
                        ▼
                  Gunicorn (WSGI)
                        │
                        ▼
                     Django
          ┌─────────────┼──────────────┐
          ▼             ▼              ▼
    PostgreSQL       Redis        Static/Media
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
       Celery Worker  Celery Beat   Flower*
```

*Flower should only be exposed through VPN, authentication or a private network.

---

## 3. Production Principles

Development uses:

```text
python manage.py runserver
```

Production will use:

```text
Gunicorn + Nginx
```

No development server will be exposed to the Internet.

---

## 4. Planned Configuration

### Django

- DEBUG=False
- SECRET_KEY from environment
- ALLOWED_HOSTS
- CSRF_TRUSTED_ORIGINS
- secure cookies
- logging
- production email backend
- static/media configuration

### Settings Structure

Planned after diploma:

```text
config/settings/
    base.py
    development.py
    production.py
```

### Docker

Possible future layout:

```text
compose.yaml
compose.production.yaml
```

---

## 5. Reverse Proxy

Nginx responsibilities:

- HTTPS termination
- proxy to Gunicorn
- static files
- media files
- security headers
- request limits
- compression

---

## 6. Static & Media

Static:

```bash
python manage.py collectstatic --noinput
```

Media should never be stored inside immutable images.

Possible storage:

- Docker volumes
- S3-compatible storage
- managed object storage

---

## 7. Database Migration Strategy

```text
Backup
   │
   ▼
Build
   │
   ▼
Deploy
   │
   ▼
Run migrations
   │
   ▼
Health check
   │
   ▼
Traffic switch
```

Never execute migrations simultaneously from multiple application instances.

---

## 8. Backup Strategy

- daily PostgreSQL backups
- retention policy
- off-host backup storage
- regular restore verification

---

## 9. Celery

Production recommendations:

- exactly one Beat instance
- multiple Workers if needed
- retries
- time limits
- graceful shutdown
- monitoring

---

## 10. Flower

Flower is intended for operations.

Recommendations:

- authentication
- VPN or private network
- temporary exposure only
- disable when not required

---

## 11. Security Checklist

- secrets outside Git
- dedicated PostgreSQL user
- HTTPS only
- secure cookies
- firewall
- least-privilege containers
- regular dependency updates

---

## 12. Definition of Done

- HTTPS configured
- Gunicorn operational
- Nginx configured
- static/media served correctly
- PostgreSQL backups verified
- Redis and Celery stable
- one Beat instance
- logging enabled
- health checks working
- smoke tests passed
- rollback procedure documented

---

## 13. Future Improvements

The production platform will evolve incrementally following the project's
engineering principle of **Evolution over Revolution**.

Each deployment improvement should preserve backward compatibility whenever
practical and extend the existing infrastructure instead of replacing it.



After the diploma:

- GitHub Actions CI/CD
- automated deployments
- container image publishing
- observability (Prometheus/Grafana)
- centralized logging
- horizontal scaling
- Kubernetes evaluation (optional)

---

## 14. Relation to the Roadmap

Production deployment is intentionally planned after the current development
phases focused on application functionality and infrastructure maturity.

Implementation order is maintained in **docs/roadmap.md** and includes:

- production deployment;
- CI/CD automation;
- observability and monitoring;
- performance optimization;
- future horizontal scaling.

