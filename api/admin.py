from django.contrib import admin
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget
from .models import Department, Staff, Visit, SystemSetting, NotificationLog
from django.db.models import F
from django.db.models.functions import Coalesce

# -------------------
# Department Admin
# -------------------
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name','id', 'department_type', 'order')
    list_display_links = ('name',)
    list_filter = ('department_type',)
    search_fields = ('name','id')

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
 
        fields = (
            'employee_number', 'name', 'name_kana',
            'department', 'position', 'email', 'phone',
            'photo_url'
        )

# -------------------
# Visit Inline
# -------------------
class VisitInline(admin.TabularInline):
    model = Visit
    fields = ('visitor_name', 'visitor_company', 'visit_type',  'visited_at')
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
        'section_name',  
        'position',
    )
    search_fields = ('name', 'employee_number', 'name_kana', 'department__name', 'section_name')
    list_filter = ('department',)
    ordering = ('department__order', 'name')
    inlines = [VisitInline]
    readonly_fields = ('photo_preview',)

    fieldsets = (
        ('基本情報', {
            'fields': ('employee_number', 'name', 'name_kana', 'department', 'position')
        }),
        ('連絡先', {
            'fields': ('email', 'phone', 'photo_url') 
        }),
    )


    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            head_department_name=Coalesce(F('department__parent__name'), F('department__name')),
            section_name_value=F('department__name')
        )

    def get_ordering(self, request):
        ordering_param = request.GET.get('o', '')
        if ordering_param == 'head_department_name':
            return ['head_department_name', 'section_name_value', 'position', 'name']
        elif ordering_param == '-head_department_name':
            return ['-head_department_name', '-section_name_value', '-position', 'name']
        return super().get_ordering(request)

    def head_department(self, obj):
        return obj.head_department_name
    head_department.short_description = "本部"
    head_department.admin_order_field = 'head_department_name'

    def section_name(self, obj):
        parent = getattr(obj.department, 'parent', None) if obj.department else None
        return obj.department.name if parent else "-"
    section_name.short_description = "課"
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
    list_filter = ('visit_type', 'staff')
    search_fields = ('visitor_name', 'visitor_company', 'purpose_preset', 'purpose_custom')
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
            'fields': ('visited_at','status')
        }),
    )


# -------------------
# SystemSetting Admin
# -------------------
@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ( "description", "value", "updated_at")
    search_fields = ("key", "value")
    fieldsets = (
        (None, {
            "fields": ("key", "value", "description")
        }),
    )

# # -------------------
# # NotificationLog Admin
# # -------------------
# class NotificationLogAdmin(admin.ModelAdmin):
#     list_display = ('visit_info', 'staff_name', 'notification_type', 'escalation_level', 'sent_at')
#     list_filter = ('notification_type', 'escalation_level', 'staff')

#     def visit_info(self, obj):
#         return f'{obj.visit.visitor_name}({obj.visit.visitor_company})'
#     visit_info.short_description = '来訪情報'

#     def staff_name(self, obj):
#         return obj.staff.name if obj.staff else ''
#     staff_name.short_description = '担当者'

# -------------------
# Register Models
# -------------------
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Staff, StaffAdmin)
admin.site.register(Visit, VisitAdmin)
admin.site.register(NotificationLog, NotificationLogAdmin)
