from .models import SystemSetting

def system_settings_processor(request):
    system_settings = SystemSetting.objects.first()
    return {
        "system_settings": system_settings,
        "background_image": system_settings.background_image_url if system_settings else ""
    }

def redirect_settings(request):
    # 管理画面で設定した 'redirect_timeout' キーを取得
    # 文字列を数値に変換（予期せぬ入力への対策としてtry-exceptを入れると安全）
    try:
        seconds_str = SystemSetting.get_setting('redirect_timeout', default='120')
        seconds = int(seconds_str)
    except (ValueError, TypeError):
        seconds = 120  # エラー時はデフォルト120秒

    return {
        'redirect_timeout_ms': seconds * 1000  # JS用にミリ秒で返す
    }