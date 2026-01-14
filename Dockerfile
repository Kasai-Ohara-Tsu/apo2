FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false

# 作業ディレクトリ
WORKDIR /app

# システム依存パッケージ（必要に応じて調整）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# 依存ファイルを先にコピーしてキャッシュを利用
# READMEの構成に合わせて backend/requirements.txt を想定
COPY backend/requirements.txt /app/requirements.txt

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

# アプリケーションコードをコピー
COPY . /app

# 非rootユーザー作成（任意）
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# 環境変数（必要に応じて .env で上書き）
ENV DJANGO_SETTINGS_MODULE=reception_system.settings \
    PORT=8000 \
    STATIC_ROOT=/app/staticfiles

# エントリポイントスクリプトを作成（コンテナ起動時にマイグレーションと collectstatic を実行）
USER root
RUN printf '#!/usr/bin/env bash\nset -e\n# 待機（DB等が起動中であればリトライ）\nif [ -n \"$DB_HOST\" ]; then\n  echo \"Waiting for DB host $DB_HOST...\"\n  for i in {1..30}; do nc -z $DB_HOST ${DB_PORT:-5432} && break || sleep 1; done\nfi\n# Django 初期化処理\npython backend/manage.py migrate --noinput || true\npython backend/manage.py collectstatic --noinput --clear || true\n# サーバ起動（Daphne を想定）\nexec daphne -b 0.0.0.0 -p ${PORT:-8000} reception_system.asgi:application\n' > /entrypoint.sh && chmod +x /entrypoint.sh

# 権限を戻す
RUN chown appuser:appuser /entrypoint.sh
USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]