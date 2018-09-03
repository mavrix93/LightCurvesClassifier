FROM python:3.6

MAINTAINER Martin Vo

ENV TINI_VERSION v0.14.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini /tini
RUN chmod +x /tini
ENTRYPOINT ["/tini", "--"]

# apt-get install -y python python-pip python-dev python-tk \
RUN echo "deb http://packages.dotdeb.org jessie all" >> /etc/apt/sources.list && \
    echo "deb-src http://packages.dotdeb.org jessie all" >> /etc/apt/sources.list && \
    wget https://www.dotdeb.org/dotdeb.gpg && apt-key add dotdeb.gpg
RUN apt-get update && apt-get -y install redis-server
RUN apt-get -y install libfreetype6-dev libpng12-dev libxft-dev libblas-dev liblapack-dev libatlas-base-dev gfortran \
    nginx dialog net-tools libxml2-dev libxslt1-dev python-lxml

ENV DOCKYARD_SRVHOME=/srv
ENV DOCKYARD_SRVPROJ=$DOCKYARD_SRVHOME/web \
    DOCKYARD_SRVDATA=$DOCKYARD_SRVHOME/data \
    DOCKYARD_SRVSAMPLE=$DOCKYARD_SRVHOME/sample_data \
    DOCKYARD_SRVLOGS=$DOCKYARD_SRVHOME/logs \
    DOCKYARD_SRVSTATIC=$DOCKYARD_SRVHOME/static/ \
    DOCKYARD_WORKERS=5 \
    DOCKYARD_PORT=8000 \
    DOCKYARD_APP_CONTEXT=lcc \
    MPLBACKEND="agg"
    #DOCKYARD_SECRET - should be set during deployment

ADD lcc_web/web/requirements.txt tmp/requirements.txt
RUN mkdir -p $DOCKYARD_SRVSTATIC $DOCKYARD_SRVLOGS \
&& pip install -r tmp/requirements.txt

# prepare web application
ADD . $DOCKYARD_SRVHOME

RUN python $DOCKYARD_SRVHOME/setup.py install
RUN mv $DOCKYARD_SRVHOME/lcc_web/* $DOCKYARD_SRVHOME

# prepare nginx configuration
ADD nginx.conf /etc/nginx/sites-enabled/default

# Port to expose
EXPOSE 80
# 'data' folder for user outputs (better to store data on external ftp
VOLUME ["$DOCKYARD_SRVDATA", "$DOCKYARD_SRVLOGS"]

# WORKDIR $DOCKYARD_SRVPROJ
WORKDIR /srv/web
ENV PYTHONPATH /srv

# TODO: Fix me
ENV DOCKYARD_SRVSAMPLE $DOCKYARD_SRVHOME/sample_data
RUN pip install lxml
COPY ./docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh
CMD "/docker-entrypoint.sh"
