# COEP Campus Portal

Django + PostgreSQL web portal for COEP Technological University. Spec: see the project brief (roles, modules, data model, rules).

## Status

| # | Module | State |
|---|--------|-------|
| 1 | Auth & roles + Service Requests (BVG) | ✅ done |
| 2 | Lost & Found | ✅ done |
| 3 | Photocopy ordering | ✅ done |
| 4 | COEP Market | ✅ done |
| 5 | Blood directory & hospitals | next |
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
| Photocopy Shop | shop@coeptech.ac.in (open), shop2@coeptech.ac.in (closed) |
| Admin | admin@coeptech.ac.in (also opens `/django-admin/`) |

### Sign-up

Only emails on `ALLOWED_EMAIL_DOMAINS` can sign up, and only as Student or Teacher. A 6-digit code is emailed; in development it is printed in the `runserver` console. BVG staff, shops and admins are created by an admin in `/django-admin/`.

## Module 1 — what's built

- **Auth**: email + password login, COEP-only sign-up with email OTP, passwords hashed (PBKDF2), role-based access on every view (`accounts.decorators.role_required`).
- **Service requests**: category → Building → Floor → Classroom → optional note. Medical/Security are auto high-priority, sorted first, and have one-tap buttons on the home screen; the last used location is pre-filled, so an urgent request takes two taps.
- **BVG staff**: open queue (high priority first) → Accept → Start work → Mark done. Accepting locks the row so two staff can't take the same job.
- **History**: every status change is stored in `RequestEvent` and shown as a timeline.
- **Live status**: pages poll a tiny fingerprint endpoint every 8 s and refresh when something changes (WebSockets/push come in module 6).

## Module 2 — Lost & Found

- Instagram-style feed at `/lost-found/`: photo, title, description, place, date, Lost/Found tag and who posted it. Newest uploads first, then by date; filter by Lost/Found and search by item or place.
- Photos are resized to 1280 px and re-saved as JPEG, which also strips EXIF (GPS location). Found items need a photo.
- Contact: the uploader's college email always; their phone only if they tick "Show my phone number" on that post.
- The uploader marks a post **Returned**, which removes it from the feed (it stays in "My posts"). Admins can remove a post.
- Students, teachers and admins can use it; BVG staff and shops cannot.

## Module 3 — Photocopy ordering

**Student** (`/print/`): pick an open shop → upload a PDF/JPG/PNG (pages are counted automatically) → choose B/W or colour, single/double sided, copies, A4/A3, binding, page range → see the exact price → pay with **that shop's own QR code** in any UPI app → upload the payment screenshot + last 4–6 digits of the transaction ID → choose Main Gate or Library. Track it: Placed → Payment Verified → Printing → Out for Delivery → Delivered.

**Shop** (`/print/shop/`): Open/Closed switch, orders in "To verify / In progress / Done" tabs. For a new order the shop checks the money in its **own** payment app, then Verify → Start printing (download file) → Out for delivery → Delivered, or Reject with a reason. Settings: name, location, QR code, UPI ID, full price list. A shop can't open until it has uploaded a QR.

**Payments**: the portal never takes or moves money; it only stores the screenshot and digits as proof.

**Files**: print files and screenshots live in `private_media/` (never public) and are served only to that order's student and shop. The print file is deleted as soon as the order is delivered or rejected. Run this daily (cron) to delete everything older than `PRINT_FILE_RETENTION_DAYS` (default 7) and unpaid drafts older than a day:

```bash
.venv/bin/python manage.py purge_print_files
```

The demo shops use a fake QR marked "DEMO QR – DO NOT PAY".

## Module 4 — COEP Market

- `/market/`: grid of items for sale, 2 per row on phones. Search by title/description, category chips, and filters for condition, min/max price and sort (newest, price low→high, high→low).
- Selling (students): up to 5 photos (resized, EXIF stripped), title, price in ₹ (0 = free), category, condition, description. Edit to change details or add/remove photos.
- Buyer contacts the seller by college email; phone, call and WhatsApp only if the seller ticks "Show my phone number". Payment happens directly between buyer and seller; the seller then taps **Mark as sold**, which hides it from the market.
- Admins can remove a listing. Teachers, BVG staff and shops don't see the market (spec: students buy and sell).

## Tests

```bash
.venv/bin/python manage.py test
```
