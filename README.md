# alans-albums — quick setup

Minimal instructions to get the project running locally and to create the Django admin user.

1) Create and activate virtual environment (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Install dependencies:

```powershell
pip install -r requirements.txt
```

3) Run migrations and create a superuser (interactive):

```powershell
python manage.py migrate
python manage.py createsuperuser
```

4) Or create a superuser non-interactively using environment variables and the included script:

```powershell
setx DJANGO_SUPERUSER_USERNAME myadmin
setx DJANGO_SUPERUSER_EMAIL admin@example.com
setx DJANGO_SUPERUSER_PASSWORD "YourP@ssw0rd"
;# you may need to open a new shell for setx to be available; or use $env:... for the current session
$env:DJANGO_SUPERUSER_USERNAME = 'myadmin'; $env:DJANGO_SUPERUSER_EMAIL = 'admin@example.com'; $env:DJANGO_SUPERUSER_PASSWORD = 'YourP@ssw0rd'
python scripts/create_admin.py
```

5) Run the dev server:

```powershell
python manage.py runserver
```

6) To run with gunicorn (production-like):

```powershell
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

Local PostgreSQL via Docker
-----------------------------------

If you'd like to use PostgreSQL locally (recommended to match production), start the database with Docker Compose:

```powershell
docker compose up -d
```

This starts a postgres service on localhost:5432 with credentials shown in `docker-compose.yml`.

You can use the example `.env.example` to set `DATABASE_URL` or set it in your shell before running migrations. Example value:

```
postgres://alans:alans_password@127.0.0.1:5432/alans_albums
```

After starting the DB, run migrations and create the admin as documented above.

Security note: Do NOT commit real secret keys or passwords to the repository. Move secrets out of `env.py` and into environment variables or a secure secrets manager before deploying.

Cloudinary and migrations
-------------------------

After adding the Cloudinary-backed `ListingImage` model, run:

```powershell
python manage.py makemigrations accounts
python manage.py migrate
```

Make sure `CLOUDINARY_URL` (or `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`) are set before uploading images.
