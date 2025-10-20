release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
web: gunicorn config.wsgi:application --log-file - --workers 3 --timeout 30