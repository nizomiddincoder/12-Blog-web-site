"""Serverda (Railway) ishga tushirish: migratsiya → static → admin (birinchi marta) → gunicorn
→ rejalashtirilgan postlar uchun fon jarayoni."""
import os
import subprocess
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def manage(*args):
    subprocess.run([sys.executable, "manage.py", *args], check=True)


def main():
    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        os.makedirs(os.path.join(data_dir, "media"), exist_ok=True)

    manage("migrate", "--noinput")
    manage("collectstatic", "--noinput", "--verbosity", "0")

    # Birinchi admin: DJANGO_SUPERUSER_USERNAME / _PASSWORD / _EMAIL berilgan bo'lsa va hali yo'q bo'lsa.
    if os.getenv("DJANGO_SUPERUSER_USERNAME") and os.getenv("DJANGO_SUPERUSER_PASSWORD"):
        import django

        django.setup()
        from django.contrib.auth import get_user_model

        if not get_user_model().objects.filter(username=os.environ["DJANGO_SUPERUSER_USERNAME"]).exists():
            manage("createsuperuser", "--noinput")

    # Rejalashtirilgan postlarni har daqiqada tekshiruvchi fon jarayoni.
    subprocess.Popen([sys.executable, "manage.py", "publish_scheduled", "--loop"])

    port = os.getenv("PORT", "8000")
    os.execvp(sys.executable, [
        sys.executable, "-m", "gunicorn", "config.wsgi:application",
        "--bind", f"0.0.0.0:{port}",
        "--workers", os.getenv("WEB_CONCURRENCY", "2"),
        "--threads", "8",
        "--timeout", "900",
        "--access-logfile", "-",
    ])


if __name__ == "__main__":
    main()
