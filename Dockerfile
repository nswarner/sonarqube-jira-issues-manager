FROM alpine:latest

RUN apk add --no-cache python3 py3-pip
COPY ./sonarqube_sync.py /srv/sonarqube_sync.py

RUN pip3 install requests

CMD ["python3", "/srv/sonarqube_sync.py"]