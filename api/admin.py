from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Department, Staff, Visit, SystemSetting
from django.db.models import F, Case, When, Value, CharField
from django.db.models.functions import Coalesce

# -------------------
# Department Admin
# -------------------
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'department_type', 'parent', 'order', 'teams_api_status')
    list_display_links = ('name',)
    list_filter = ('department_type',)
    search_fields = ('name', 'id', 'teams_api_url')
    ordering = ('order', 'id')
    
    def teams_api_status(self, obj):
        if obj.teams_api_url:
            return format_html('<span style="color: green;">{}</span>', "✅ 設定済み")
        return format_html('<span style="color: gray;">{}</span>', "❌ 未設定")
    
    teams_api_status.short_description = "Teams連携"

# -------------------
# Staff Resource for ImportExport
# -------------------
class StaffResource(resources.ModelResource):
    department = fields.Field(
        column_name='department_id',
        attribute='department',
        widget=ForeignKeyWidget(Department, 'id')
    )

    class Meta:
        model = Staff
        import_id_fields = ('employee_number',)
        skip_unchanged = True
        report_skipped = False
        fields = (
            'employee_number',
            'name',
            'name_kana',
            'department',
            'position',
            'photo_url',
        )
        export_order = (
            'employee_number',
            'name',
            'name_kana',
            'department',
            'position',
            'photo_url',
        )

# -------------------
# Visit Inline
# -------------------
class VisitInline(admin.TabularInline):
    model = Visit
    fields = ('visitor_name', 'visitor_company', 'visit_type', 'visited_at')
    readonly_fields = ('visitor_name', 'visitor_company', 'visit_type', 'visited_at')
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = '訪問履歴'
    verbose_name_plural = '訪問履歴'

# -------------------
# Staff Admin
# -------------------
class StaffAdmin(ImportExportModelAdmin):
    resource_class = StaffResource
    list_display = (
        'employee_number',
        'name',
        'head_department',
        'position',
    )
    search_fields = ('name', 'employee_number', 'name_kana', 'department__name', 'department__parent__name')
    list_filter = ('department__parent', 'department', 'position') 
    ordering = ('department__parent__order', 'department__order', 'name')
    inlines = [VisitInline]
    readonly_fields = ('head_department', 'position')

    fieldsets = (
        ('基本情報', {
            'fields': (
                'employee_number',
                'name',
                'name_kana',
                'department',
                'head_department',
                'section_name',
                'position',
            )
        }),
        ('写真', {
            'fields': ('photo_url',)
        }),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('department', 'department__parent').annotate(
            head_department_name=Case(
                When(department__parent__isnull=False, then=F('department__parent__name')),
                default=F('department__name'),
                output_field=CharField()
            ),
            section_name_value=Case(
                When(department__parent__isnull=False, then=F('department__name')),
                default=Value('-'),
                output_field=CharField()
            )
        )

    def get_ordering(self, request):
        ordering_param = request.GET.get('o', '')
        if 'head_department' in ordering_param:
            if ordering_param.startswith('-'):
                return ['-head_department_name', '-section_name_value', 'name']
            return ['head_department_name', 'section_name_value', 'name']
        return super().get_ordering(request)

    def head_department(self, obj):
        """本部名を表示"""
        if obj.department:
            if obj.department.parent:
                return obj.department.parent.name
            elif obj.department.department_type == 'headquarters':
                return obj.department.name
        return "-"
    head_department.short_description = "本部"
    head_department.admin_order_field = 'head_department_name'

    def section_name(self, obj):
        """部署名を表示（本部直下の場合のみ）"""
        if obj.department and obj.department.parent:
            return obj.department.name
        return "-"
    section_name.short_description = "部署"
    section_name.admin_order_field = 'section_name_value'

    def photo_preview(self, obj):
        if obj.photo_url:
            return format_html('<img src="{}" style="height:100px;border-radius:8px;">', obj.photo_url.url)
        return "画像なし"
    photo_preview.short_description = "写真プレビュー"

# -------------------
# Visit Admin
# -------------------
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        'visitor_name',
        'visitor_company',
        'visit_type',
        'staff',
        'purpose_preset',
        'purpose_custom',
        'visited_at',
        'status',
    )
    list_filter = ('visit_type', 'status', 'staff__department__parent', 'staff__department')
    search_fields = ('visitor_name', 'visitor_company', 'purpose_preset', 'purpose_custom', 'staff__name')
    date_hierarchy = 'visited_at'
    ordering = ('-visited_at',)

    fieldsets = (
        ('来訪者情報', {
            'fields': ('visitor_name', 'visitor_company', 'staff', 'visit_type')
        }),
        ('用件情報', {
            'fields': ('purpose_preset', 'purpose_custom')
        }),
        ('状態', {
            'fields': ('visited_at', 'status')
        }),
    )

# -------------------
# SystemSetting Admin
# -------------------
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "description", "value", "updated_at")
    search_fields = ("key", "value")
    fieldsets = (
        (None, {
            "fields": ("key", "value", "description")
        }),
    )

# -------------------
# Register Models
# -------------------
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Staff, StaffAdmin)
admin.site.register(Visit, VisitAdmin)