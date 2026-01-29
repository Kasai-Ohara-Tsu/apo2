from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import requests
from api.models import Department, Staff, SystemSetting, Visit
from django.utils import timezone
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db.models import Q
from django.urls import reverse
from urllib.parse import urlencode

API_BASE_URL = 'http://localhost:8000/api'


def create_visit(visitor_name, visitor_company, staff, purpose_preset=None, purpose_custom=None, purpose_type="", visit_type=""):

    visitor_name = visitor_name or "なし"
    visitor_company = visitor_company or "なし"

    # ラジオ用 / 自由入力用に分ける
    purpose_preset = purpose_preset if purpose_preset else ""
    purpose_custom = purpose_custom if purpose_custom else ""

    visit = Visit.objects.create(
        visitor_name=visitor_name,
        visitor_company=visitor_company,
        staff=staff,
        visit_type=visit_type,
        purpose_preset=purpose_preset,
        purpose_custom=purpose_custom,
        purpose_type=purpose_type,
        visited_at=timezone.now(),
        status="waiting", 
    )

    if staff:
        visit.notified_staff.add(staff)

    visit.save()
    return visit



def record_visit(request, visit_type="other"):
    """
    来訪履歴を作成または更新する共通関数
    - 既にセッションに visit_id があれば更新
    - なければ新規作成
    """
    visitor_name = request.GET.get("visitor_name") or "なし"
    visitor_company = request.GET.get("visitor_company") or "なし"
    staff_id = request.GET.get("staff_id")
    purpose_preset = request.GET.get("purpose_preset", "")
    purpose_custom = request.GET.get("purpose_custom", "")
    purpose_type = request.GET.get("purpose_type", "")

    staff = Staff.objects.filter(id=staff_id).first()

    visit_id = request.session.get("visit_id")
    visit = None

    if visit_id:
        # 既存訪問を更新
        visit = Visit.objects.filter(id=visit_id).first()
        if visit:
            # ★ 修正箇所: purpose_preset または purpose_custom に値がある場合のみ更新 ★
            if purpose_preset or purpose_custom:
                visit.purpose_preset = purpose_preset
                visit.purpose_custom = purpose_custom
                visit.purpose_type = purpose_type
                visit.save()
            
            return visit

    # なければ新規作成
    visit = create_visit(visitor_name, visitor_company, staff, purpose_preset, purpose_custom, purpose_type, visit_type,)
    visit.save()

    request.session["visit_id"] = visit.id
    return visit


def get_all_subdept_ids(department):
    """指定部署とその子部署すべてのIDをリストで返す"""
    ids = [department.id]
    for child in department.children.all():
        ids.extend(get_all_subdept_ids(child))
    return ids

def get_department_full_name(dept):
    """部署のフルパスを取得（例：営業部 営業第二課）"""
    names = []
    current = dept
    while current:
        names.insert(0, current.name)
        current = current.parent
    return "　".join(names)

def get_department_hierarchy():
    departments = Department.objects.filter(department_type="department").order_by("order")
    hierarchy = []

    for dept in departments:

        sections = Department.objects.filter(parent=dept, department_type="section").order_by("order")

        section_data = []
        for sec in sections:
            staff = Staff.objects.filter(department=sec).order_by("name")
            section_data.append({
                "section": sec,
                "staff_list": staff,
            })

        hierarchy.append({
            "department": dept,
            "sections": section_data,
        })

    return hierarchy





#  初期画面表示
def index(request):
    system_settings = SystemSetting.objects.first()
    return render(request, "frontend/index.html", {
        "system_settings": system_settings
    })

# 来訪者情報入力画面
def visitor_info(request):
    return render(request, 'frontend/screens/visitor_info.html')


# 担当者検索画面
def staff_search(request):
    """
    本部タブ表示＋課ごと社員表示＋名前検索対応
    """
    record_visit(request, visit_type="appointment") 
    visitor_name = request.GET.get("visitor_name")
    visitor_company = request.GET.get("visitor_company")
    visit_type = "appointment"
    purpose_preset = request.GET.get("purpose_preset")
    purpose_custom = request.GET.get("purpose_custom")
    try:
        # 本部取得（部署タブ用）
        headquarters_list = Department.objects.filter(
        Q(department_type="headquarters") | Q(department_type="special")
        ).order_by("order")
        departments_data = []

        # 本部配下の課を取得する関数
        def get_sections(dept):
            return dept.children.filter(department_type="section").order_by("order")

        for hq in headquarters_list:
            dept_info = {
                "id": hq.id,
                "name": hq.name,
                "full_name": hq.name,
                "sections": [],
                "staff_list": [],
            }

            # 本部直下の社員
            staff_qs = Staff.objects.filter(department=hq).order_by("name")
            for staff in staff_qs:
                dept_info["staff_list"].append({
                    "id": staff.id,
                    "name": staff.name,
                    "name_kana": staff.name_kana,
                    "position": staff.position,
                    "photo_url": staff.photo_url,
                    "department_full_name": get_department_full_name(hq),
                })

            # 本部配下の課ごと社員
            sections = get_sections(hq)
            for section in sections:
                section_staff_qs = Staff.objects.filter(department=section).order_by("name")
                section_staff_list = []
                for staff in section_staff_qs:
                    section_staff_list.append({
                        "id": staff.id,
                        "name": staff.name,
                        "name_kana": staff.name_kana,
                        "position": staff.position,
                        "photo_url": staff.photo_url,
                        "department_full_name": get_department_full_name(section),
                    })
                dept_info["sections"].append({
                    "id": section.id,
                    "name": section.name,
                    "full_name": get_department_full_name(section),
                    "staff_list": section_staff_list,
                })

            departments_data.append(dept_info)

        # 名前検索用 全社員リスト
        all_staff_qs = Staff.objects.filter().order_by("name")
        staff_list = []
        for staff in all_staff_qs:
            staff_list.append({
                "id": staff.id,
                "name": staff.name,
                "name_kana": staff.name_kana,
                "position": staff.position,
                "photo_url": staff.photo_url,
                "department_full_name": get_department_full_name(staff.department) if staff.department else "",
            })

        context = {
            "departments_data": departments_data, 
            "staff_list": staff_list,              
            "body_class": "name-search",
            "visitor_name": visitor_name,
            "visitor_company": visitor_company,
            "purpose_preset": purpose_preset,
            "purpose_custom": purpose_custom,
            "visit_type":visit_type,
        }

        return render(request, "frontend/screens/staff_search.html", context)

    except Exception as e:
        print(f"Error in staff_search view: {e}")
        return render(request, "frontend/screens/staff_search.html", {
            "departments_data": [],
            "staff_list": [],
            "error": str(e),
        })


def staff_search2(request):
    """
    本部タブ表示＋課ごと社員表示＋名前検索対応
    """
    record_visit(request, visit_type="no-appointment") 
    visitor_name = request.GET.get("visitor_name")
    visitor_company = request.GET.get("visitor_company")
    visit_type = "no-appointment"
    purpose_preset = request.GET.get("purpose_preset")
    purpose_custom = request.GET.get("purpose_custom")
    try:
        # 本部取得（部署タブ用）
        headquarters_list = Department.objects.filter(
        Q(department_type="headquarters") | Q(department_type="special")
        ).order_by("order")
        departments_data = []

        # 本部配下の課を取得する関数
        def get_sections(dept):
            return dept.children.filter(department_type="section").order_by("order")

        for hq in headquarters_list:
            dept_info = {
                "id": hq.id,
                "name": hq.name,
                "full_name": hq.name,
                "sections": [],
                "staff_list": [],
            }

            # 本部直下の社員
            staff_qs = Staff.objects.filter(department=hq).order_by("name")
            for staff in staff_qs:
                dept_info["staff_list"].append({
                    "id": staff.id,
                    "name": staff.name,
                    "name_kana": staff.name_kana,
                    "position": staff.position,
                    "photo_url": staff.photo_url,
                    "department_full_name": get_department_full_name(hq),
                })

            # 本部配下の課ごと社員
            sections = get_sections(hq)
            for section in sections:
                section_staff_qs = Staff.objects.filter(department=section).order_by("name")
                section_staff_list = []
                for staff in section_staff_qs:
                    section_staff_list.append({
                        "id": staff.id,
                        "name": staff.name,
                        "name_kana": staff.name_kana,
                        "position": staff.position,
                        "photo_url": staff.photo_url,
                        "department_full_name": get_department_full_name(section),
                    })
                dept_info["sections"].append({
                    "id": section.id,
                    "name": section.name,
                    "full_name": get_department_full_name(section),
                    "staff_list": section_staff_list,
                })

            departments_data.append(dept_info)

        # 名前検索用 全社員リスト
        all_staff_qs = Staff.objects.filter().order_by("name")
        staff_list = []
        for staff in all_staff_qs:
            staff_list.append({
                "id": staff.id,
                "name": staff.name,
                "name_kana": staff.name_kana,
                "position": staff.position,
                "photo_url": staff.photo_url,
                "department_full_name": get_department_full_name(staff.department) if staff.department else "",
            })

        context = {
            "departments_data": departments_data, 
            "staff_list": staff_list,              
            "body_class": "name-search",
            "visitor_name": visitor_name,
            "visitor_company": visitor_company,
            "purpose_preset": purpose_preset,
            "purpose_custom": purpose_custom,
            "visit_type":visit_type,
        }

        return render(request, "frontend/screens/staff_search2.html", context)

    except Exception as e:
        print(f"Error in staff_search2 view: {e}")
        return render(request, "frontend/screens/staff_search2.html", {
            "departments_data": [],
            "staff_list": [],
            "error": str(e),
        })

def get_department_full_name(dept):
    """
    部署の階層名を取得（例：本部 > 部 > 課）
    """
    if not dept:
        return ""
    names = []
    current = dept
    while current:
        names.append(current.name)
        current = current.parent
    return " > ".join(reversed(names))



def waiting(request):
    staff_id = request.GET.get("staff_id")
    staff_name = request.GET.get("staff_name")
    visitor_company = request.GET.get("visitor_company")
    visitor_name = request.GET.get("visitor_name")
    purpose_preset = request.GET.get("purpose_preset", "")
    purpose_custom = request.GET.get("purpose_custom","")
    purpose_type = request.GET.get("purpose_type", "")

    # 設定取得
    escalation_seconds = int(SystemSetting.get_setting("escalation_interval_seconds", 5))

    # スタッフ取得
    staff = Staff.objects.filter(id=staff_id).first()

    request.session["visit_type"] = "appointment"


    return render(request, "frontend/screens/waiting.html", {
        "visitor_company": visitor_company,
        "visitor_name": visitor_name,
        "staff_name": staff.name if staff else "不明",
        "staff": staff,
        "purpose_preset":purpose_preset,
        "purpose_custom":purpose_custom,
        "escalation_seconds": escalation_seconds,
    })

def waiting(request):
    staff_id = request.GET.get("staff_id")
    staff_name = request.GET.get("staff_name")
    visitor_company = request.GET.get("visitor_company")
    visitor_name = request.GET.get("visitor_name")
    purpose_preset = request.GET.get("purpose_preset", "")
    purpose_custom = request.GET.get("purpose_custom","")
    purpose_type = request.GET.get("purpose_type", "")

    # 設定取得
    escalation_seconds = int(SystemSetting.get_setting("escalation_interval_seconds", 5))

    # スタッフ取得
    staff = Staff.objects.filter(id=staff_id).first()

    return render(request, "frontend/screens/waiting.html", {
        "visitor_company": visitor_company,
        "visitor_name": visitor_name,
        "staff_name": staff.name if staff else "不明",
        "staff": staff,
        "purpose_preset":purpose_preset,
        "purpose_custom":purpose_custom,
        "escalation_seconds": escalation_seconds,
    })

def cancel_from_waiting(request):
    """
    waiting2画面からのキャンセル時、セッションに保存された情報をstaff_search2画面へ引き継いでリダイレクトする
    また、キャンセルされた訪問のVisitレコードを削除する。
    """
    # セッションから情報を取得
    visit_id = request.session.get("visit_id")
    visitor_name = request.session.get("visitor_name", "")
    visitor_company = request.session.get("visitor_company", "")
    purpose_preset = request.session.get("purpose_preset", "")
    purpose_custom = request.session.get("purpose_custom", "")
    visit_type = request.session.get("visit_type", "appointment")

    if visit_id:
        Visit.objects.filter(id=visit_id).delete()
    
    request.session.pop("visit_id", None)

    params = {
        "visitor_name": visitor_name,
        "visitor_company": visitor_company,
        "purpose_preset": purpose_preset,
        "purpose_custom": purpose_custom,
        "visit_type": visit_type
    }
    
    from django.urls import reverse
    from urllib.parse import urlencode

    base_url = reverse('frontend:staff_search')
    query_string = urlencode(params)

    return redirect(f"{base_url}?{query_string}")



def waiting2(request):
    staff_id = request.GET.get("staff_id")
    staff_name = request.GET.get("staff_name")
    visitor_company = request.GET.get("visitor_company")
    visitor_name = request.GET.get("visitor_name")
    purpose_preset = request.GET.get("purpose_preset", "")
    purpose_custom = request.GET.get("purpose_custom","")
    purpose_type = request.GET.get("purpose_type", "")
    visit_type = "no-appointment"

    # 設定取得
    escalation_seconds = int(SystemSetting.get_setting("escalation_interval_seconds", 5))

    # スタッフ取得
    staff = Staff.objects.filter(id=staff_id).first()

    request.session["visitor_name"] = visitor_name
    request.session["visitor_company"] = visitor_company
    request.session["staff_id"] = staff_id
    request.session["purpose_preset"] = purpose_preset
    request.session["purpose_custom"] = purpose_custom
    request.session["visit_type"] = "no_appointment"
    # record_visit(request, visit_type="no_appointment")



    return render(request, "frontend/screens/waiting2.html", {
        "visitor_company": visitor_company,
        "visitor_name": visitor_name,
        "staff_name": staff.name if staff else "不明",
        "staff": staff,
        "purpose_preset":purpose_preset,
        "purpose_custom":purpose_custom,
        "escalation_seconds": escalation_seconds,
        "visit_type":visit_type,
    })


def cancel_from_waiting2(request):
    """
    waiting2画面からのキャンセル時、セッションに保存された情報をstaff_search2画面へ引き継いでリダイレクトする
    また、キャンセルされた訪問のVisitレコードを削除する。
    """
    # セッションから情報を取得
    visit_id = request.session.get("visit_id")
    visitor_name = request.session.get("visitor_name", "")
    visitor_company = request.session.get("visitor_company", "")
    purpose_preset = request.session.get("purpose_preset", "")
    purpose_custom = request.session.get("purpose_custom", "")
    visit_type = request.session.get("visit_type", "no-appointment")

    if visit_id:
        Visit.objects.filter(id=visit_id).delete()
    
    request.session.pop("visit_id", None)

    params = {
        "visitor_name": visitor_name,
        "visitor_company": visitor_company,
        "purpose_preset": purpose_preset,
        "purpose_custom": purpose_custom,
        "visit_type": visit_type
    }
    
    # URL名 'frontend:staff_search2' を使用し、クエリパラメータを安全にエンコードして渡す
    from django.urls import reverse
    from urllib.parse import urlencode

    base_url = reverse('frontend:staff_search2')
    query_string = urlencode(params)

    return redirect(f"{base_url}?{query_string}")







def which(request):
    visitor_name = request.GET.get("visitor_name")
    visitor_company = request.GET.get("visitor_company")
    staff_id = request.GET.get("staff_id")
    visit_type = request.GET.get("visit_type")
    purpose_preset = request.GET.get("purpose_preset") or "--"
    purpose_custom = request.GET.get("purpose_custom") or "--"

    if not purpose_preset and not purpose_custom:
        return redirect("frontend:purpose_input")

    return render(request, "frontend/screens/which.html", {
        "visitor_name": visitor_name,
        "visitor_company": visitor_company,
        "staff_id": staff_id,
        "purpose_preset": purpose_preset,
        "purpose_custom": purpose_custom,
        "visit_type":visit_type,
    })



# 要件入力画面
def purpose_input(request):
    staff_id = request.GET.get("staff_id")
    staff_name = request.GET.get("staff_name")
    visitor_company = request.GET.get("visitor_company")
    visitor_name = request.GET.get("visitor_name")
    purpose_preset = request.GET.get("purpose_preset", "")
    purpose_custom = request.GET.get("purpose_custom","")
    visit_type = ("no-appointment")

    purposes = [
        "新規取引のご相談",
        "既存取引のご相談",
        "配達・納品の方",
        "集荷の方",
        "その他のお問い合わせ",
    ]

    return render(request, "frontend/screens/purpose_input.html", {
        "visitor_company": visitor_company,
        "visitor_name": visitor_name,
        "staff_name": staff_name,
        "purposes": purposes,
        "staff_id": staff_id,
        "purpose_preset": purpose_preset,
        "purpose_custom": purpose_custom,
        "visit_type":visit_type,
    })



# 受付完了画面
def reception_complete(request):
    print(">>> reception_complete GET:", request.GET.dict())

    visitor_name = request.GET.get("visitor_name", "")
    visitor_company = request.GET.get("visitor_company", "")
    staff_id = request.GET.get("staff_id")
    purpose_preset = request.GET.get("purpose_preset")
    purpose_custom = request.GET.get("purpose_custom")
    status_param = request.GET.get("status")


    staff = Staff.objects.filter(id=staff_id).first() if staff_id and staff_id.isdigit() else None

    # 既存 Visit
    visit_id = request.session.get("visit_id")
    visit = Visit.objects.filter(id=visit_id).first() if visit_id else None

    url_visit_type = request.GET.get("visit_type")

    if visit:
        visit.status = status_param or "notified"
        visit.staff = staff
        
        if url_visit_type:
            visit.visit_type = url_visit_type
            
        # 目的情報の更新 (前回修正済みと仮定)
        if purpose_preset is not None:
            visit.purpose_preset = purpose_preset
        if purpose_custom is not None:
            visit.purpose_custom = purpose_custom
            
        visit.save()

        print(f"3. Visit updated. New DB visit_type: {visit.visit_type}")
    # 新規 → create_visit して status 反映
    else:
        print(f"2. No Visit found. Creating new with visit_type: {visit_type}")

        final_visit_type = url_visit_type if url_visit_type else "no-appointment"
        
        visit = create_visit(
            visitor_name=visitor_name,
            visitor_company=visitor_company,
            staff=staff,
            purpose_preset=purpose_preset,
            purpose_custom=purpose_custom,
            purpose_type="",
            visit_type=final_visit_type,
        )

        visit.status = status_param or "manager"
        visit.save()

        request.session["visit_id"] = visit.id
        print(f">>> Visit created: id={visit.id}, status={visit.status}")

    # 履歴固定 → セッション削除
    if "visit_id" in request.session:
        del request.session["visit_id"]

    return render(request, "frontend/screens/reception_complete.html", {
        "visitor_name": visitor_name,
        "visitor_company": visitor_company,
        "staff_name": staff.name if staff else "",
        "staff": staff,
        "visit": visit,
    })


# 通知画面
def notification_complete(request):
    visitor_name = request.GET.get("visitor_name", "")
    visitor_company = request.GET.get("visitor_company", "")
    staff_id = request.GET.get("staff_id")
    purpose_preset = request.GET.get("purpose_preset")
    purpose_custom = request.GET.get("purpose_custom")
    status_param = request.GET.get("status") or "notified"

    staff = Staff.objects.filter(id=staff_id).first() if staff_id and staff_id.isdigit() else None

    url_visit_type = request.GET.get("visit_type")

    # 遷移元に応じてメッセージを決定
    if staff_id and staff:
        # waiting/waiting2から来た場合（担当者不在）
        message_title = f"{staff.name}は不在のため、総務へ通知しました。"
        message_lead = "担当者が不在のため、総務へ通知いたしました。しばらくお待ちください。"
    else:
        # whichから来た場合（総務通知）
        message_title = "総務へ通知しました"
        message_lead = "総務へ通知いたしました。しばらくお待ちください。"

    # 既存 Visit を取得
    visit_id = request.session.get("visit_id")
    visit = Visit.objects.filter(id=visit_id).first() if visit_id else None

 
    if visit:
        print(f">>> Visit found: {visit.id} / before status={visit.status}")
        visit.status = status_param or "manager"

        if staff: # staff が None でない場合のみ更新
            visit.staff = staff
        
        if url_visit_type:
            visit.visit_type = url_visit_type
        # リクエストパラメータに目的情報があれば更新する
        if purpose_preset is not None:
            visit.purpose_preset = purpose_preset
        if purpose_custom is not None:
            visit.purpose_custom = purpose_custom
            
        visit.responded_at = timezone.now()
        visit.save()
        print(f">>> Visit updated: status={visit.status}")


    # --- Visit が無い場合 → 新規作成 ---
    else:
        print(">>> No existing visit, creating new Visit")

        final_visit_type = url_visit_type if url_visit_type else "no-appointment"

        visit = create_visit(
            visitor_name=visitor_name,
            visitor_company=visitor_company,
            staff=staff,
            purpose_preset=purpose_preset,
            purpose_custom=purpose_custom,
            purpose_type="",
            visit_type=final_visit_type,
        )

        visit.status = status_param
        visit.save()

        # 新しく作った Visit をセッションに保存
        request.session["visit_id"] = visit.id

        print(f">>> Visit created: id={visit.id}, status={visit.status}")

    # 履歴確定 → セッション削除
    if "visit_id" in request.session:
        del request.session["visit_id"]

    return render(request, "frontend/screens/notification_complete.html", {
        "visitor_name": visitor_name,
        "visitor_company": visitor_company,
        "staff": staff,
        "staff_name": staff.name if staff else "",
        "visit": visit,
        "message_title": message_title, 
        "message_lead": message_lead,   
    })



# APIエンドポイント：部署階層取得
@require_http_methods(["GET"])
def get_departments(request):
    try:
        response = requests.get(f'{API_BASE_URL}/departments/hierarchy/')
        if response.status_code == 200:
            return JsonResponse(response.json(), safe=False)
        return JsonResponse({'error': 'Failed to fetch departments'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# APIエンドポイント：スタッフ一覧取得
@require_http_methods(["GET"])
def get_staff(request):
    try:
        response = requests.get(f'{API_BASE_URL}/staff/')
        if response.status_code == 200:
            return JsonResponse(response.json(), safe=False)
        return JsonResponse({'error': 'Failed to fetch staff'}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# APIエンドポイント：スタッフ通知
@require_http_methods(["POST"])
@csrf_exempt
def notify_staff(request):
    try:
        data = json.loads(request.body)
        staff_id = data.get('staff_id')
        visitor_info = data.get('visitor_info')
        # 実際にはAPIやWebSocketで通知を送信
        return JsonResponse({'status': 'success', 'message': 'Notification sent'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


