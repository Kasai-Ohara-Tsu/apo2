# Pythonのバージョンを指定
FROM python:3.11-slim

# 標準出力・標準エラー出力をバッファしない設定（ログがすぐに見れるように）
ENV PYTHONUNBUFFERED 1

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係のインストール
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# プロジェクトのコードをコピー
COPY . /app/

# 静的ファイルを集める (ビルド時に実行する場合)
# 注意: データベース接続が必要な処理はここでは行わない
RUN python manage.py collectstatic --noinput

# コンテナ起動時に実行するコマンド
# マイグレーションを実行してからGunicornを起動
CMD python manage.py migrate && gunicorn reception_system.wsgi:application --bind 0.0.0.0:$PORT