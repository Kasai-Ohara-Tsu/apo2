# 来客受付システム (Visitor Reception System)

Python/Django/Bootstrapで実装された来客受付システムです。

## システム概要

このシステムは以下の機能を提供します：

1. **来訪者情報入力** - 会社名と来訪者名を入力
2. **担当者検索** - 部署または名前から担当者を検索
3. **待機画面** - 担当者への通知と応答待機
4. **REST API** - 部署・社員情報の管理API

## プロジェクト構成

```
backend/
├── reception_system/      # Djangoプロジェクト設定
│   ├── settings.py       # プロジェクト設定
│   ├── urls.py          # URLルーティング
│   ├── asgi.py          # ASGI設定（WebSocket対応）
│   └── wsgi.py          # WSGI設定
├── api/                  # REST APIアプリケーション
│   ├── models.py        # データモデル（部署、社員）
│   ├── serializers.py   # DRFシリアライザー
│   ├── views.py         # APIビュー
│   ├── urls.py          # APIエンドポイント
│   ├── consumers.py     # WebSocketコンシューマー
│   ├── routing.py       # WebSocketルーティング
│   └── admin.py         # Django Admin設定
├── frontend/            # フロントエンドアプリケーション
│   ├── views.py         # フロントエンドビュー
│   ├── urls.py          # フロントエンドURL
│   └── templates/       # HTMLテンプレート
│       └── frontend/
│           ├── base.html                # ベーステンプレート
│           ├── index.html               # ウェルカムスクリーン
│           └── screens/
│               ├── visitor_info.html    # 来訪者情報入力
│               ├── staff_search.html    # 担当者検索（修正済み）
│               ├── waiting.html         # 待機画面
│               ├── reception_complete.html
│               ├── staff_unavailable.html
│               ├── purpose_input.html
│               ├── notification_complete.html
│               └── delivery.html
├── manage.py            # Djangoコマンドラインツール
├── requirements.txt     # Python依存パッケージ
├── initial_data.json    # 初期データ
└── db.sqlite3          # SQLiteデータベース
```

## インストール手順

### 1. 環境セットアップ

```bash
# Pythonバージョン確認（3.11推奨）
python3 --version

# 仮想環境の作成
python3 -m venv venv

# 仮想環境の有効化
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. データベースマイグレーション

```bash
python manage.py migrate
```

### 4. スーパーユーザーの作成（オプション）

```bash
python manage.py createsuperuser
```

### 5. 初期データの読み込み

```bash
python manage.py loaddata initial_data.json
```

## 実行方法

### 開発サーバーの起動

```bash
python manage.py runserver 0.0.0.0:8000
```

サーバーが起動したら、ブラウザで以下のURLにアクセス：

- **フロントエンド**: http://localhost:8000/
- **API**: http://localhost:8000/api/
- **Admin**: http://localhost:8000/admin/

## APIエンドポイント

### 部署情報

```
GET /api/departments/
GET /api/departments/hierarchy/
```

### 社員情報

```
GET /api/staff/
```

## フロントエンド画面フロー

1. **ウェルカムスクリーン** (`/`)
   - アポイントあり / なし を選択

2. **来訪者情報入力** (`/visitor-info/`)
   - 会社名と来訪者名を入力
   - localStorageに情報を保存

3. **担当者検索** (`/staff-search/`)
   - 部署から検索 / 名前から検索
   - 担当者を選択

4. **待機画面** (`/waiting/`)
   - 担当者への通知を表示
   - 応答待機


## 技術スタック

| レイヤー | 技術 |
|---------|------|
| **バックエンド** | Django 4.2 |
| **API** | Django REST Framework |
| **リアルタイム通信** | Django Channels |
| **データベース** | SQLite |
| **フロントエンド** | Django Templates + Bootstrap 5 |
| **スタイリング** | Bootstrap 5 + Custom CSS |
| **JavaScript** | Vanilla JavaScript |

## 環境変数

`.env`ファイルを作成して以下を設定（オプション）：

```
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
```

## トラブルシューティング

### ポート8000が既に使用されている場合

```bash
# 別のポートで起動
python manage.py runserver 0.0.0.0:8001
```

### データベースエラーが発生した場合

```bash
# マイグレーションをリセット
python manage.py migrate api zero
python manage.py migrate
python manage.py loaddata initial_data.json
```

### JavaScriptが動作しない場合

- ブラウザのコンソール（F12）でエラーを確認
- キャッシュをクリア（Ctrl+Shift+Delete）
- 開発者ツールで`localStorage`の値を確認

## 本番環境への展開

本番環境では以下の設定を推奨：

1. `settings.py`で`DEBUG = False`に設定
2. `ALLOWED_HOSTS`に本番ドメインを追加
3. `SECRET_KEY`を環境変数から読み込み
4. データベースをPostgreSQLに変更
5. WebサーバーをGunicornなどで起動
6. リバースプロキシ（Nginx）を設定

## ライセンス

このプロジェクトはMIT Licenseの下で公開されています。

## サポート

問題が発生した場合は、以下を確認してください：

1. Pythonバージョンが3.11以上
2. すべての依存パッケージがインストール済み
3. データベースマイグレーションが完了
4. 初期データが読み込まれている
5. ポート8000が利用可能

---

**最終更新**: 2025年月日
# tapco
