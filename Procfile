# Procfile
release: python manage.py migrate
web: gunicorn eventapp.wsgi:application --worker-class eventlet --bind 0.0.0.0:8080
