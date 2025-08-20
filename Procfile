# chạy migrate khi deploy
release: python manage.py migrate

# start gunicorn cho web server
web: gunicorn eventapp.wsgi:application --bind 0.0.0.0:8080
