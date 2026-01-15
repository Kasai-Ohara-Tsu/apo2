FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=reception_system.settings

WORKDIR /app

# 依存関係
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# アプリ本体
COPY . .

# collectstatic はビルド時
RUN python manage.py collectstatic --noinput

# entrypoint を追加
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
