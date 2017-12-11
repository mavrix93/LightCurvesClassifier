#!/bin/bash
python manage.py migrate                  # Apply database migrations
python manage.py collectstatic --noinput  # Collect static files

echo "from django.contrib.auth.models import User; User.objects.filter(email='admin@example.com').delete(); User.objects.create_superuser('admin', 'admin@example.com', 'nimda')" | python manage.py shell

# Prepare log files and start outputting logs to stdout
touch $DOCKYARD_SRVLOGS/gunicorn.log
touch $DOCKYARD_SRVLOGS/access.log
tail -n 0 -f $DOCKYARD_SRVLOGS/*.log &

echo Starting Nginx
service nginx start

echo Starting redis
redis-server --daemonize yes

echo Starting rq workers
exec python $DOCKYARD_SRVHOME/lcc/stars_processing/systematic_search/worker.py &
# Start Gunicorn processes
echo Starting Gunicorn.
exec gunicorn LCCwebApp.wsgi:application \
    --name LCCwebApp \
    --bind 127.0.0.1:$DOCKYARD_PORT \
    --workers $DOCKYARD_WORKERS \
    --timeout 300 \
    --log-level=info \
    --log-file=$DOCKYARD_SRVLOGS/gunicorn.log \
    --access-logfile=$DOCKYARD_SRVLOGS/access.log
