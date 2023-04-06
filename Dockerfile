FROM python:3.11.2-alpine3.17

LABEL version="0.1.0" \
  description="secrets-to-vault"

# hadolint ignore=DL3018
RUN apk add --no-cache curl 

RUN adduser -u 10001 -s /bin/bash -D appuser && mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY ./app /usr/src/app
RUN pip3 install --no-cache-dir --no-compile -r requirements.txt

USER appuser
EXPOSE 3000/tcp

ENTRYPOINT ["gunicorn"] 
CMD ["--bind", "0.0.0.0:3000", "--certfile=/certs/tls.crt", "--keyfile=/certs/tls.key", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
