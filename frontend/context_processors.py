from .models import SystemSetting

def system_settings_processor(request):
    system_settings = SystemSetting.objects.first()
    return {
        "system_settings": system_settings,
        "background_image": system_settings.background_image_url if system_settings else ""
    }
