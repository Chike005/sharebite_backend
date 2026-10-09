# ShareBite API

Django REST backend for a food donation platform with authentication, donations,
staffed collection points, reservations, delivery proof, receipts and
administrator-managed drop-off sites.
The React/TypeScript frontend is maintained separately and is not included here.

## Local development

Use Python 3.12. Create a fresh environment; do not reuse the old committed Windows environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DJANGO_DEBUG=true
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Set configuration by exporting environment variables in your shell or through
your hosting dashboard. Django does not automatically load `.env` files.
SQLite is used for local development only. New uploads live under `media/`.
If migrating an existing database, copy existing `proofs/` and `receipts/` folders
into `media/` before using it. Do not publish real user data in a portfolio demo.

## Checks

```bash
DJANGO_DEBUG=true python manage.py check
DJANGO_DEBUG=true python manage.py test
DJANGO_DEBUG=true python manage.py makemigrations --check --dry-run
```

Tests cover donation details, reservation/cancellation, password updates,
workflow state protection, collection-point selection and receipt confirmation,
permissions, health and image uploads.

## Production deployment

Required configuration:

| Variable | Value |
| --- | --- |
| `DJANGO_DEBUG` | `false` (default) |
| `DJANGO_SECRET_KEY` | New random secret; never reuse the formerly committed key |
| `DJANGO_ALLOWED_HOSTS` | Backend hostnames, comma separated, without URL schemes |
| `DATABASE_URL` | Persistent PostgreSQL connection URL; include provider-required TLS options |
| `DJANGO_CORS_ALLOWED_ORIGINS` | Exact frontend origins with `https://` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Trusted frontend/admin origins with `https://` |
| `DJANGO_MEDIA_ROOT` | Path on a persistent disk, outside the source tree |
| `DJANGO_TRUST_PROXY` | `true` only when a trusted proxy strips supplied forwarded headers |

Build:

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Release (once per deployment, with the production database configured):

```bash
python manage.py migrate --noinput
```

Start:

```bash
gunicorn sharebite_backend.wsgi:application --bind 0.0.0.0:$PORT --access-logfile -
```

`Procfile` contains the start command. WhiteNoise serves collected static assets.
The unauthenticated `/api/health/` endpoint checks database connectivity; configure
health probes to use HTTPS or the trusted proxy's forwarded HTTPS header.

**Remaining before public deployment:** select hosting, configure PostgreSQL,
connect the frontend and configure persistent media with a production media server
or object storage. WhiteNoise does not serve uploaded media. Proof/receipt images
may contain private information; their storage and access policy must be chosen
before accepting public uploads. No provider or live deployment is configured yet.

## API

All routes have the `/api/` prefix. Authenticate using
`Authorization: Token <token>` from the login response.

| Route | Methods | Purpose |
| --- | --- | --- |
| `health/` | GET | Database readiness |
| `register/` | POST | Register a user |
| `login/` | POST | Obtain token and user details |
| `edituser/` | PUT, PATCH | Edit current user; validates and hashes passwords |
| `resetpassword/` | PUT | Change password using current password |
| `members/` | GET | Administrator-only member list |
| `donations/` | GET, POST | List and create donations |
| `collection-points/` | GET | List the staffed collection points |
| `donations/mine/` | GET | Current user's donations |
| `donations/reserved/` | GET | Current user's reservations |
| `donations/<id>/` | GET | Donation details |
| `donations/<id>/status/` | PUT, PATCH | Administrator updates status |
| `donations/<id>/reserve/` | POST | Reserve an available donation |
| `donations/<id>/confirm-receipt/` | POST | Administrator confirms receipt at collection point |
| `donations/<id>/cancel/` | POST | Cancel own reservation |
| `donations/<id>/proof/` | POST | Donor/admin image proof; multipart `proof_image` |
| `donations/<id>/receipt/` | POST | Reserved receiver's receipt; multipart `proof_image` |
| `receipts/` | GET | Current user's receipts |
| `dropoff-sites/` | GET, POST | Authenticated users list sites; admins create them |

Proofs and receipts take donation/user relations from the authenticated request
and URL. Donation state fields are read-only during creation. Reservations are
locked inside a transaction to prevent two receivers reserving the same donation
on PostgreSQL; SQLite development tests do not verify concurrent locking.

New donations require a collection point and start in `awaiting_dropoff`.
Only administrators can transition them to `received_at_collection_point`;
reservation attempts before confirmation are rejected by the API. Migration
`0007` seeds three illustrative Manchester-area points and associates existing
donations with the Ancoats demo point before the relationship becomes required.
These addresses and coordinates are fictional portfolio data; no real donations
are accepted.

Donation creation accepts an optional `food_image` multipart upload (JPG, PNG
or WebP; maximum 5 MB). It is separate from the donor's later proof-of-donation
upload and is returned with donation details. Optional quantity and best-before
date are also saved as donation details.

## Portfolio preparation

After deploying and verifying the separate frontend, add a live demo link,
repository link and screenshots of donation creation and reservation. Describe
verified features and your specific contributions; document unfinished map or
production storage work accurately.
