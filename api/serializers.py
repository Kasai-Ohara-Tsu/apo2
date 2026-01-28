from rest_framework import serializers
from .models import Department, Staff, Visit, SystemSetting

class DepartmentSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = '__all__'

    def get_children(self, obj):
        return DepartmentSerializer(obj.children.order_by('order'), many=True).data

class StaffSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Staff
        fields = '__all__'
    teams_api_url = serializers.CharField(source='department.teams_api_url', read_only=True)

    class Meta:
        model = Staff
        fields = [
            'id', 'employee_number', 'name', 'name_kana', 
            'department', 'position', 'photo_url', 'teams_api_url'
        ]

class VisitSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Visit
        fields = '__all__'

class SystemSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSetting
        fields = '__all__'

# class NotificationLogSerializer(serializers.ModelSerializer):
#     staff_name = serializers.CharField(source='staff.name', read_only=True)
#     visit_visitor_name = serializers.CharField(source='visit.visitor_name', read_only=True)

#     class Meta:
#         model = NotificationLog
#         fields = '__all__'
