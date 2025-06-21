FROM python:3.11-alpine3.21

RUN apk add build-base libpq libpq-dev

WORKDIR /orders

COPY requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput || echo "No static files found"

EXPOSE 8000

ENV DEBUG="False"

ENTRYPOINT gunicorn orders.wsgi -b 0.0.0.0:8000
