"""Create a Django superuser from environment variables.

Usage:
  Activate your venv, then:
    python scripts/create_admin.py

It reads these environment variables:
  DJANGO_SUPERUSER_USERNAME
  DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD

If they are not set it will prompt interactively.
"""
import os
import sys

if __name__ == "__main__":
    # ensure project path is on sys.path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

    try:
        import django
        django.setup()
        from django.contrib.auth import get_user_model
    except Exception as exc:
        print("Failed to import Django. Activate your venv and install requirements.")
        raise

    User = get_user_model()

    username = os.environ.get('DJANGO_SUPERUSER_USERNAME') or input('Username: ')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL') or input('Email: ')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    if not password:
        import getpass
        password = getpass.getpass('Password: ')

    if User.objects.filter(username=username).exists():
        print(f"User '{username}' already exists. Skipping creation.")
        sys.exit(0)

    user = User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' created.")
