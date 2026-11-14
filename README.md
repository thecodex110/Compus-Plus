# Campus Plus

A web portal for everyday campus life at COEP Technological University, Pune: help requests to the BVG team, Lost & Found, COEP Market, printouts and stationery delivered to the gate, blood donors and hospitals. Django + PostgreSQL, mobile-first, in **English and हिंदी**.

Campus Plus is a student project; it is not an official COEP product.

## Status

| # | Module | State |
|---|--------|-------|
| 1 | Auth & roles + Service Requests (BVG) | ✅ done |
| 2 | Lost & Found | ✅ done |
| 3 | Photocopy + stationery ordering | ✅ done |
| 4 | COEP Market | ✅ done |
| 5 | Blood directory & hospitals | ✅ done |
| 6 | Notifications, admin dashboard, polish | ✅ done |
| 7 | Redesign, Hindi, stationery, remaining gaps | ✅ done |

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

## Module 5 — Blood directory & hospitals

- **Opt-in only** (`/blood/me/`): a student adds their blood group (and optionally last donation date) only after ticking a consent box. They can hide themselves with one switch or delete the entry; hidden entries never appear anywhere.
- **Search** (`/blood/`, students, teachers, admins): tap the needed group; optionally include compatible donor groups (e.g. B+ can receive B+, B−, O+, O−). Exact matches come first; donors who gave in the last 90 days are flagged.
- **Phone privacy**: numbers are hidden until the searcher taps "Show number". Every lookup is logged, the donor sees who looked them up, and one person can view at most 15 numbers a day.
- **Hospitals** (`/blood/hospitals/`, every role incl. BVG staff): name, address, distance, phone, emergency phone, 24×7 and blood-bank tags, Directions link, plus 108 / 112 buttons. Admins manage the list in `/django-admin/`.
- The seeded hospitals are real names with **approximate** distances and **no phone numbers**: add verified numbers in admin before relying on the page.

## Module 6 — Notifications, admin dashboard, polish

**Notifications** — bell in the header with an unread count (checks every 15 s). Who gets what:

| Event | Who is notified |
|---|---|
| New service request | every BVG staff member (Medical/Security marked urgent) |
| Request accepted / started / done | the person who raised it |
| Print order placed | that shop (urgent: verify payment) |
| Print order verified / printing / out for delivery / delivered / rejected | the student |
| Someone views a donor's number | that donor |

On `/notifications/` a user can tap **Turn on alerts** to get browser pop-ups while the portal is open in a tab. (True push to a closed phone needs Web Push/VAPID keys and HTTPS. That's a later add-on.)

**Admin dashboard** (`/admin-panel/`, admins land here after login):
- Live numbers: open/high-priority requests, active print orders, Lost & Found posts, items for sale, listed donors, open shops, plus requests waiting over 15 minutes.
- **Users**: search/filter by role; create BVG staff, shop (its shop profile is made automatically) and admin accounts; deactivate/reactivate anyone.
- **Campus**: add classrooms in bulk (building + floor + comma-separated rooms); remove rooms that have no request history.
- **Hospitals**: add, edit, remove.
- **Moderate**: remove Lost & Found posts and market listings.
- `/django-admin/` stays available for anything advanced.

**Polish**
- Profile page (`/accounts/profile/`, tap your role chip): edit name/phone/department/year and change password.
- "Forgot password?" on the login page: reset link by email.
- Login is locked for 15 minutes after 10 wrong passwords for the same email; the `?next=` redirect after login only allows this site.
- Friendly 403/404/500 pages. Floors are listed G, 1, 2… everywhere.

## Deploy (Render)

Vercel does not fit this app (serverless functions have no persistent disk, and print files, photos and QR codes are uploaded files). `render.yaml` sets everything up on **Render**:

- a **web service** (gunicorn) with a **persistent disk** at `/var/data`. It holds `media/` (public photos and shop QR codes) and `private_media/` (print files and payment screenshots, never served directly);
- a managed **PostgreSQL** database;
- a daily **clean-up job** (`campus-purge`). A Render cron job cannot mount the web service's disk, so the job only calls `/internal/purge-print-files/` on the web service with a secret token (`CRON_TOKEN`, generated once and shared by both services) and the web service does the deleting.

The plans in `render.yaml` are paid ones; check Render's pricing page first. The disk means a single instance and a few seconds of downtime on every deploy.

1. Push the repo to GitHub.
2. Render dashboard → **New → Blueprint** → choose the repo. Render asks for the SMTP values (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`): OTP and password-reset emails need a real mail account. `APP_URL` can stay empty for now.
3. When the web service is live, copy its URL (`https://campus-plus-xxxx.onrender.com`) into **`APP_URL`** of the `campus-purge` job.
4. Open the web service's **Shell** and run `python manage.py createsuperuser`. Log in on the **Admin** tab, then add staff, shops, classrooms and hospitals from the dashboard. Don't run `seed_demo` in production.
5. Custom domain: add it in Render, then set `ALLOWED_HOSTS=portal.example.com` and `CSRF_TRUSTED_ORIGINS=https://portal.example.com` on the web service. The `*.onrender.com` address works without them.

`render.yaml` also pins Python with `.python-version` (3.12). Static files are built during the deploy (`collectstatic`); the compiled Hindi file `locale/hi/LC_MESSAGES/django.mo` is committed, so the server needs no gettext. With `DEBUG=0` the app turns on the HTTPS redirect, secure cookies and HSTS.

**Any other host.** Set `DEBUG=0`, a long random `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, the `DB_*` values and the SMTP values. Build with `pip install -r requirements.txt && python manage.py collectstatic --noinput`, start with `python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:$PORT`. Set `DATA_DIR` to a persistent disk. Run `python manage.py purge_print_files` daily, or set `CRON_TOKEN` and have any scheduler `POST` to `/internal/purge-print-files/` with the header `Authorization: Bearer <CRON_TOKEN>`.

## Module 7 — Redesign, Hindi, and the remaining gaps

**New look ("Drawing Sheet").** Every screen borrows from the Engineering Graphics sheet every COEP student draws in first year: a ruled **title block** on every record (sheet number like `REQ-0042`, `ORD-0017`, `LF-0103`, `MKT-0007`, location, who raised it, who checked it, status), square corners, condensed technical lettering, and one colour per module: Requests vermilion, Lost & Found teal, Market ultramarine, Print ochre, Blood crimson. Red is kept for emergencies and errors. Icons are a hand-made SVG line set (`templates/_icons.html`, used as `{% icon "name" %}`), not emoji. Phones get a bottom tab bar; desktops get a side rail. The font is Anek Devanagari (Ek Type, SIL OFL), self-hosted in `static/fonts/`; one family covers Hindi and English.

**English / हिंदी.** The EN | हिं switch in the top bar saves the choice on the user's account (cookie for signed-out visitors). Notifications are written in each *recipient's* language, so a Hindi-speaking guard gets Hindi alerts even when an English user raised the request. Translations live in `locale/hi/LC_MESSAGES/django.po`. After changing any user-facing text:

```bash
.venv/bin/python manage.py makemessages -l hi --ignore=.venv
# translate the new entries in django.po, then
.venv/bin/python manage.py compilemessages --ignore=.venv
```

**Stationery.** Shops list stationery (name, price, in stock) on their Stationery page. Students add stationery to a print order, or order stationery alone; it's priced together with printing and delivered the same way.

**Gaps closed.** Admins manage shops from the admin panel (`/admin-panel/shops/`: name, location, phone, open/closed, live order counts). A student or teacher can cancel a request until BVG staff accept it. The owner of a Lost & Found post can delete it.

## Tests

```bash
.venv/bin/python manage.py test
```
