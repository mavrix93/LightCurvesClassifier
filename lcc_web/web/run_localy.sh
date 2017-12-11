export DOCKYARD_SRC=web
export DOCKYARD_SRVHOME=/Users/martinvo/workspace/private2/LCCwebApp
export DOCKYARD_SRVPROJ=$DOCKYARD_SRVHOME/web
export DOCKYARD_SRVSAMPLE=$DOCKYARD_SRVHOME/sample_data
export DOCKYARD_SRVDATA=$DOCKYARD_SRVHOME/data
export DOCKYARD_SRVLOGS=$DOCKYARD_SRVHOME/logs
export DOCKYARD_SRVSTATIC=$DOCKYARD_SRVHOME/static/
export DOCKYARD_APP_CONTEXT=lcc
export DOCKYARD_PORT=8000
export http_host=http://127.0.0.1:80

python3.6 manage.py migrate                  # Apply database migrations
python3.6 manage.py collectstatic --noinput  # Collect static files


service nginx start
# Start Gunicorn processes
echo Starting Gunicorn.
exec gunicorn LCCwebApp.wsgi:application \
    --name LCCwebApp \
    --bind 127.0.0.1:$DOCKYARD_PORT \
    --workers 3 \
    --log-level=info \
    --log-file=$DOCKYARD_SRVLOGS/gunicorn.log \
    --access-logfile=$DOCKYARD_SRVLOGS/access.log

