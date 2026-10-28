# COEP Campus Portal

Django + PostgreSQL web portal for COEP Technological University. Spec: see the project brief (roles, modules, data model, rules).

## Status

| # | Module | State |
|---|--------|-------|
| 1 | Auth & roles + Service Requests (BVG) | ✅ done |
| 2 | Lost & Found | next |
| 3 | Photocopy ordering | — |
| 4 | COEP Market | — |
| 5 | Blood directory & hospitals | — |
| 6 | Notifications, admin dashboard, polish | — |

## Run locally

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
cp .env.example .env
createdb campusplus
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

Open http://localhost:8000.

### Demo accounts (local only)

`seed_demo` creates one account per role. Password = `DEMO_PASSWORD` from `.env` (default `campus-demo-123`).

| Role | Email |
|------|-------|
| Student | student@coeptech.ac.in |
| Teacher | teacher@coeptech.ac.in |
| BVG Staff | bvg@coeptech.ac.in, bvg2@coeptech.ac.in |
| Photocopy Shop | shop@coeptech.ac.in |
| Admin | admin@coeptech.ac.in (also opens `/django-admin/`) |

### Sign-up

Only emails on `ALLOWED_EMAIL_DOMAINS` can sign up, and only as Student or Teacher. A 6-digit code is emailed; in development it is printed in the `runserver` console. BVG staff, shops and admins are created by an admin in `/django-admin/`.

## Module 1 — what's built

- **Auth**: email + password login, COEP-only sign-up with email OTP, passwords hashed (PBKDF2), role-based access on every view (`accounts.decorators.role_required`).
- **Service requests**: category → Building → Floor → Classroom → optional note. Medical/Security are auto high-priority, sorted first, and have one-tap buttons on the home screen; the last used location is pre-filled, so an urgent request takes two taps.
- **BVG staff**: open queue (high priority first) → Accept → Start work → Mark done. Accepting locks the row so two staff can't take the same job.
- **History**: every status change is stored in `RequestEvent` and shown as a timeline.
- **Live status**: pages poll a tiny fingerprint endpoint every 8 s and refresh when something changes (WebSockets/push come in module 6).

## Tests

```bash
.venv/bin/python manage.py test
```
