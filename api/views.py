import pandas as pd
import requests
import json
from io import StringIO

from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Department, Staff, Visit, SystemSetting
from .serializers import DepartmentSerializer, StaffSerializer, VisitSerializer, SystemSettingSerializer

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all().order_by("order", "name")
    serializer_class = DepartmentSerializer

    @action(detail=False, methods=["get"])
    def hierarchy(self, request):
        """ルート部署（親がNoneの部署）から階層構造を取得"""
        root_departments = Department.objects.filter(parent__isnull=True).order_by("order", "name")
        serializer = self.get_serializer(root_departments, many=True)
        return Response(serializer.data)

class StaffViewSet(viewsets.ModelViewSet):
    queryset = Staff.objects.all().order_by("employee_number")
    serializer_class = StaffSerializer

    @action(detail=False, methods=["get"])
    def search(self, request):
        """名前、カナ、社員番号によるスタッフ検索"""
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
        """CSVによるスタッフ一括登録"""
        if "file" not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        csv_file = request.FILES["file"]
        data = csv_file.read().decode("utf-8-sig")
        df = pd.read_csv(StringIO(data))

        errors = []
        for index, row in df.iterrows():
            try:
                department, _ = Department.objects.get_or_create(name=row["部署名"], defaults={
                    "department_type": "section"
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
        """スタッフ一覧のCSV出力"""
        staff_data = Staff.objects.all().values(
            "employee_number", "name", "name_kana", "department__name", 
            "position", "email", "phone"
        )
        df = pd.DataFrame(list(staff_data))
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="staff_export.csv"'
        df.to_csv(response, index=False, encoding="utf-8-sig")
        return response

class VisitViewSet(viewsets.ModelViewSet):
    queryset = Visit.objects.all().order_by("-visited_at")
    serializer_class = VisitSerializer

    def perform_create(self, serializer):
        """データ保存時に自動でTeamsへ通知"""
        # 1. データベースに保存
        visit = serializer.save()
        
        # 2. 担当者の部署にTeams API URLがあるかチェック
        if visit.staff and visit.staff.department and visit.staff.department.teams_api_url:
            self.send_teams_notification(visit, visit.staff.department.teams_api_url)

    def send_teams_notification(self, visit, webhook_url):
        """TeamsチャネルへAdaptive Card形式で通知を投稿"""
        local_time = timezone.localtime(visit.visited_at).strftime('%H:%M')
        
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "text": "🔔 来客通知", "weight": "Bolder", "size": "Large", "color": "Attention"},
                        {"type": "TextBlock", "text": f"担当: **{visit.staff.name}** さん", "wrap": True},
                        {"type": "FactSet", "facts": [
                            {"title": "会社名:", "value": visit.visitor_company},
                            {"title": "お客様:", "value": f"{visit.visitor_name} 様"},
                            {"title": "用件:", "value": visit.purpose_preset or visit.purpose_custom or "なし"},
                            {"title": "到着:", "value": local_time}
                        ]}
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "管理画面を表示",
                            "url": f"http://localhost:8000/admin/api/visit/{visit.id}/change/"
                        }
                    ],
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json"
                }
            }]
        }

        try:
            # タイムアウトを短めに設定してユーザーを待たせない
            requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Teams Notification Failed: {e}")
    @action(detail=True, methods=["post"])
    def respond(self, request, pk=None):
        """担当者からの応答（受諾・拒否）を処理"""
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
        return Response(self.get_serializer(visit).data)

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        """代理人へのエスカレーション処理"""
        visit = self.get_object()
        current_level = visit.escalation_level
        next_staff = None

        if current_level == 0 and visit.staff and visit.staff.substitute1:
            next_staff = visit.staff.substitute1
            visit.escalation_level = 1
        elif current_level == 1 and visit.staff and visit.staff.substitute2:
            next_staff = visit.staff.substitute2
            visit.escalation_level = 2
        elif current_level == 2:
            visit.escalation_level = 3
            return Response({"escalated_to": "general_affairs", "message": "総務へ転送しました"})
        else:
            return Response({"error": "No substitute available"}, status=status.HTTP_400_BAD_REQUEST)

        visit.save()
        return Response({
            "escalated_to": next_staff.id, 
            "escalated_to_name": next_staff.name, 
            "level": visit.escalation_level
        })

class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer

    @action(detail=False, methods=["get"])
    def get_setting(self, request):
        key = request.query_params.get("key")
        if not key:
            return Response({"error": "Key is required"}, status=status.HTTP_400_BAD_REQUEST)
        value = SystemSetting.get_setting(key)
        return Response({"key": key, "value": value})