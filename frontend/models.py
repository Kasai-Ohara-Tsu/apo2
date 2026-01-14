# frontend/models.py
from api.models import Department, Staff, Visit, NotificationLog, SystemSetting

from django.db import models
from django.utils import timezone

# class Department(models.Model):
#     DEPARTMENT_TYPES = [
#         ("headquarters", "本部"),
#         ("department", "部"),
#         ("section", "課"),
#         ("special", "例外部門"),
#     ]
    
#     name = models.CharField(max_length=100, verbose_name="部署名")
#     department_type = models.CharField(max_length=20, choices=DEPARTMENT_TYPES, verbose_name="部署タイプ")
#     parent = models.ForeignKey(
#         "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children", verbose_name="親部署"
#     )
#     order = models.IntegerField(default=0, verbose_name="表示順")
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

#     def __str__(self):
#         return self.name

#     class Meta:
#         db_table = "api_department"  
#         verbose_name = "部署"
#         verbose_name_plural = "部署一覧"


# class Staff(models.Model):
#     employee_number = models.CharField(max_length=20, unique=True, verbose_name="社員番号")
#     name = models.CharField(max_length=100, verbose_name="氏名")
#     name_kana = models.CharField(max_length=100, blank=True, verbose_name="氏名（カナ）")
#     department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, verbose_name="部署")
#     position = models.CharField(max_length=100, blank=True, verbose_name="役職")
#     email = models.EmailField(blank=True, verbose_name="メール")
#     phone = models.CharField(max_length=20, blank=True, verbose_name="電話番号")
#     photo_url = models.URLField(blank=True, verbose_name="写真URL")
    
#     substitute1 = models.ForeignKey(
#         "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="primary_for", verbose_name="代理1"
#     )
#     substitute2 = models.ForeignKey(
#         "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="secondary_for", verbose_name="代理2"
#     )
    
#     is_active = models.BooleanField(default=True, verbose_name="有効")
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

#     def __str__(self):
#         return self.name

#     class Meta:
#         verbose_name = "社員"
#         verbose_name_plural = "社員一覧"


# class Visit(models.Model):
#     VISIT_TYPES = [
#         ("appointment", "アポイントあり"),
#         ("no-appointment", "アポイントなし"),
#         ("delivery", "宅配業者"),
#     ]
    
#     STATUS_CHOICES = [
#         ("waiting", "待機中"),
#         ("notified", "通知済み"),
#         ("accepted", "対応中"),
#         ("completed", "完了"),
#         ("cancelled", "キャンセル"),
#         ("unavailable", "不在"),
#     ]
    
#     visit_type = models.CharField(max_length=20, choices=VISIT_TYPES, verbose_name="来訪種別")
#     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting", verbose_name="状態")
    
#     visitor_company = models.CharField(max_length=200, verbose_name="会社名")
#     visitor_name = models.CharField(max_length=100, verbose_name="来訪者名")
    
#     staff = models.ForeignKey(Staff, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="担当者")
    
#     purpose = models.TextField(blank=True, verbose_name="来訪目的")
#     purpose_type = models.CharField(max_length=100, blank=True, verbose_name="目的タイプ")
    
#     response_message = models.TextField(blank=True, verbose_name="対応メッセージ")
#     response_time = models.DateTimeField(null=True, blank=True, verbose_name="対応時間")
    
#     escalation_level = models.IntegerField(default=0, verbose_name="エスカレーションレベル")
#     notified_staff = models.ManyToManyField(Staff, related_name="notified_visits", blank=True, verbose_name="通知対象スタッフ")
    
#     visited_at = models.DateTimeField(default=timezone.now, verbose_name="来訪日時")
#     created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

#     def __str__(self):
#         return f"{self.visitor_name} ({self.visitor_company}) - {self.get_status_display()}"

#     class Meta:
#         verbose_name = "来訪"
#         verbose_name_plural = "来訪記録"


# class SystemSetting(models.Model):
#     key = models.CharField(max_length=100, unique=True, verbose_name="キー")
#     value = models.TextField(verbose_name="値")
#     description = models.TextField(blank=True, verbose_name="説明")
#     updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    
#     def __str__(self):
#         return self.key

#     @staticmethod
#     def get_setting(key, default=None):
#         try:
#             return SystemSetting.objects.get(key=key).value
#         except SystemSetting.DoesNotExist:
#             return default

#     class Meta:
#         verbose_name = "システム設定"
#         verbose_name_plural = "システム設定"


# class NotificationLog(models.Model):
#     visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="notifications", verbose_name="来訪")
#     staff = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, verbose_name="担当者")
#     notification_type = models.CharField(max_length=50, verbose_name="通知タイプ")
#     escalation_level = models.IntegerField(default=0, verbose_name="エスカレーションレベル")
#     sent_at = models.DateTimeField(auto_now_add=True, verbose_name="送信日時")

#     def __str__(self):
#         staff_name = self.staff.name if self.staff else "N/A"
#         return f"{self.visit.visitor_name}への通知 ({staff_name}) - {self.notification_type}"

#     class Meta:
#         verbose_name = "通知ログ"
#         verbose_name_plural = "通知ログ"
