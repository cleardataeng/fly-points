FROM gcr.io/cleardata-base-images/auth-proxy/python-slim-stretch

RUN pip install Flask==1.0.2 gunicorn==19.9.0

COPY . /srv
WORKDIR /srv

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--access-logfile", "-", "demo_put_target:app"]
