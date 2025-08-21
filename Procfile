# start gunicorn cho web server
web: gunicorn eventapp.wsgi:application --bind 0.0.0.0:8080
python manage.py runscript seed_data
