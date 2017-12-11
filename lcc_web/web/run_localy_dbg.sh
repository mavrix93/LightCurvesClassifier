export PYTHONPATH=$PYTHONPAT:'/Users/martinvo/workspace/private2/LightCurvesClassifier'
export DOCKYARD_SRC=web
export DOCKYARD_SRVHOME=/Users/martinvo/workspace/private2/LightCurvesClassifier/lcc_web
export DOCKYARD_SRVPROJ=$DOCKYARD_SRVHOME/web
export DOCKYARD_SRVDATA=$DOCKYARD_SRVHOME/data
export DOCKYARD_SRVSAMPLE=$DOCKYARD_SRVHOME/sample_data
export DOCKYARD_SRVLOGS=$DOCKYARD_SRVHOME/logs
export DOCKYARD_SRVSTATIC=$DOCKYARD_SRVHOME/static/
export DOCKYARD_APP_CONTEXT=lcc
export DOCKYARD_DEBUG=True

# python3.6 manage.py migrate                  # Apply database migrations
# python3.6 manage.py makemigrations
# python3.6 manage.py collectstatic --noinput  # Collect static files
python3.6 manage.py runserver 0.0.0.0:8001

