FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=apo2.settings

WORKDIR /app

# 依存関係
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# アプリ本体
COPY . .

# collectstatic はビルド時に実行
RUN python manage.py collectstatic --noinput

# 起動時に実行
CMD python manage.py migrate && gunicorn apo2.wsgi:application --bind 0.0.0.0:$PORT
