from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Department, Staff, Visit, SystemSetting, NotificationLog
from .serializers import DepartmentSerializer, StaffSerializer, VisitSerializer, SystemSettingSerializer, NotificationLogSerializer
import pandas as pd
from io import StringIO
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from api.models import Staff # モデルをapiアプリからインポート

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by("order", "name")
    serializer_class = DepartmentSerializer

    @action(detail=False, methods=["get"])
    def hierarchy(self, request):
        # ルート部署（親がNoneの部署）を取得
        root_departments = Department.objects.filter(parent__isnull=True).order_by("order", "name")
        serializer = self.get_serializer(root_departments, many=True)
        return Response(serializer.data)

class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by("employee_number")
    serializer_class = StaffSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        query = request.query_params.get("q", "")
        department_id = request.query_params.get("department", None)

        staff = Staff.objects.all()

        if query:
            staff = staff.filter(
                Q(name__icontains=query) |
                Q(name_kana__icontains=query) |
                Q(employee_number__icontains=query)
            )
        if department_id:
            staff = staff.filter(department__id=department_id)
        
        serializer = self.get_serializer(staff, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def import_csv(self, request):
        if "file" not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES["file"]
        if not csv_file.name.endswith(".csv"):
            return Response({"error": "File is not a CSV"}, status=status.HTTP_400_BAD_REQUEST)

        data = csv_file.read().decode("utf-8-sig") # BOM付きUTF-8対応
        df = pd.read_csv(StringIO(data))

        errors = []
        for index, row in df.iterrows():
            try:
                department, _ = Department.objects.get_or_create(name=row["部署名"], defaults={
                    "department_type": "section" # デフォルトで課とするか、適切なロジックが必要
                })


                Staff.objects.update_or_create(
                    employee_number=row["社員番号"],
                    defaults={
                        "name": row["氏名"],
                        "name_kana": row.get("氏名カナ", ""),
                        "department": department,
                        "position": row.get("役職", ""),
                        "email": row.get("メールアドレス", ""),
                        "phone": row.get("内線番号", ""),
                    }
                )
            except Exception as e:
                errors.append(f"Line {index + 2}: {e}")
        
        if errors:
            return Response({"status": "partially_succeeded", "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
        return Response({"status": "success", "message": "CSV imported successfully"})

    @action(detail=False, methods=["get"])
    def export_csv(self, request):
        staff_data = Staff.objects.all().values(
            "employee_number", "name", "name_kana", "department__name", 
            "position", "email", "phone", "substitute1__employee_number", "substitute2__employee_number"
        )
        df = pd.DataFrame(list(staff_data))
        df.rename(columns={
            "department__name": "部署名",
            "substitute1__employee_number": "代理人1社員番号",
            "substitute2__employee_number": "代理人2社員番号",
        }, inplace=True)
        
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=\"staff_export.csv\""
        df.to_csv(response, index=False, encoding="utf-8-sig")
        return response


class VisitViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.all().order_by("-visited_at")
    serializer_class = VisitSerializer

    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        visit = self.get_object()
        response_status = request.data.get("response")
        response_message = request.data.get("message", "")

        if response_status == "available":
            visit.status = "accepted"
        elif response_status == "unavailable":
            visit.status = "unavailable"
        else:
            return Response({"error": "Invalid response status"}, status=status.HTTP_400_BAD_REQUEST)
        
        visit.response_message = response_message
        visit.response_time = timezone.now()
        visit.save()
        
        # WebSocket通知 (受付端末更新用)
        # from channels.layers import get_channel_layer
        # from asgiref.sync import async_to_sync
        # channel_layer = get_channel_layer()
        # async_to_sync(channel_layer.group_send)(
        #     "reception",
        #     {
        #         "type": "visit_status_update",
        #         "visit_id": visit.id,
        #         "status": visit.status,
        #         "response_message": visit.response_message,
        #     }
        # )

        serializer = self.get_serializer(visit)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        visit = self.get_object()
        current_level = visit.escalation_level
        next_staff = None
        notification_type = "escalation_notification"
        escalated_to_name = ""

        if current_level == 0 and visit.staff and visit.staff.substitute1:
            next_staff = visit.staff.substitute1
            visit.escalation_level = 1
            escalated_to_name = next_staff.name
        elif current_level == 1 and visit.staff and visit.staff.substitute2:
            next_staff = visit.staff.substitute2
            visit.escalation_level = 2
            escalated_to_name = next_staff.name
        elif current_level == 2:
            visit.escalation_level = 3
            # 総務への通知ロジック (メール送信など) は別途実装
            # general_affairs_email = SystemSetting.get_setting("general_affairs_email")
            # if general_affairs_email:
            #     send_mail(
            #         "来客エスカレーション通知",
            #         f"来客 {visit.visitor_name} ({visit.visitor_company}) が総務へエスカレーションされました。",
            #         "from@example.com",
            #         [general_affairs_email],
            #         fail_silently=False,
            #     )
            return Response({"escalated_to": "general_affairs", "message": "総務へエスカレーションしました"})
        else:
            return Response({"error": "Escalation not possible at this level or no next substitute"}, status=status.HTTP_400_BAD_REQUEST)

        visit.save()
        NotificationLog.objects.create(
            visit=visit,
            staff=next_staff,
            notification_type=notification_type,
            escalation_level=visit.escalation_level
        )

        # WebSocket通知 (担当者通知用)
        # from channels.layers import get_channel_layer
        # from asgiref.sync import async_to_sync
        # channel_layer = get_channel_layer()
        # async_to_sync(channel_layer.group_send)(
        #     f"staff_{next_staff.id}",
        #     {
        #         "type": "escalation_notification",
        #         "visit_id": visit.id,
        #         "visitor_company": visit.visitor_company,
        #         "visitor_name": visit.visitor_name,
        #         "escalation_level": visit.escalation_level,
        #         "original_staff": visit.staff.name if visit.staff else "N/A",
        #     }
        # )

        return Response({"escalated_to": next_staff.id, "escalated_to_name": escalated_to_name, "escalation_level": visit.escalation_level})

    @action(detail=False, methods=["get"])
    def statistics(self, request):
        days = int(request.query_params.get("days", 7))
        # 統計情報のロジックは別途実装
        return Response({"message": f"{days}日間の統計情報を返します"})

class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer

    @action(detail=False, methods=["get"])
    def get_setting(self, request):
        key = request.query_params.get("key")
        if not key:
            return Response({"error": "Key parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        value = SystemSetting.get_setting(key)
        if value is None:
            return Response({"error": "Setting not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"key": key, "value": value})

    @action(detail=False, methods=["post"])
    def set_setting(self, request):
        key = request.data.get("key")
        value = request.data.get("value")
        description = request.data.get("description", "")

        if not key or not value:
            return Response({"error": "Key and value parameters are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        setting, _ = SystemSetting.objects.update_or_create(
            key=key,
            defaults={
                "value": value,
                "description": description
            }
        )
        serializer = self.get_serializer(setting)
        return Response(serializer.data)

# class NotificationLogViewSet(viewsets.ModelViewSet):
#     queryset = NotificationLog.objects.all().order_by("-sent_at")
#     serializer_class = NotificationLogSerializer

