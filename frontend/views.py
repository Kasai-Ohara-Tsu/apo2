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

# --- API既存のインポートの下に以下を確認・追記 ---
import requests
import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# ------------------------------------------

API_BASE_URL = 'http://localhost:8000/api'

# --- APIここから追記 ---
#総務へ通知
AZURE_LOGIC_APP_URL_soumu = "https://prod-20.japanwest.logic.azure.com:443/workflows/1628c90d4b6742e3bd93ec228dcb47fb/triggers/When_an_HTTP_request_is_received/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2FWhen_an_HTTP_request_is_received%2Frun&sv=1.0&sig=lbHWKvzuJMqLSFWra2wskyenyXNg-X-bmjHVfZ5hTx4"
#本部総務へ通知
AZURE_LOGIC_APP_URL_honbu = "https://prod-23.japanwest.logic.azure.com:443/workflows/7be5cf09b027471380894387025ba358/triggers/When_an_HTTP_request_is_received/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2FWhen_an_HTTP_request_is_received%2Frun&sv=1.0&sig=EoXNgwY2yToel5enXjG9X5XtXJiLm9zoHFmdsQ8qWmc"
        

# メッセージ一時保存用（サーバー再起動でリセットされます）
latest_message = ""
latest_title = ""
# --- APIここまで追記 ---

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

    # 担当者情報を取得
    staff = Staff.objects.filter(id=staff_id).first() if staff_id else None

    # Visitレコードを作成（ステータスは「待機中」）
    if staff:
        visit = create_visit(
            visitor_name=visitor_name,
            visitor_company=visitor_company,
            staff=staff,
            purpose_preset=purpose_preset,
            purpose_custom=purpose_custom,
            purpose_type=purpose_type,
            visit_type="appointment"
        )
        # ステータスを「待機中」に設定
        visit.status = "waiting"
        visit.save()

    # ★ ここに通知処理を移動・追記する ★
    if staff:
        # 1. 送信先URLの決定
        notification_url = None
        if staff.department and staff.department.teams_api_url:
            notification_url = staff.department.teams_api_url
        else:
            notification_url = AZURE_LOGIC_APP_URL_honbu

        # 2. 送信データの作成
        teams_data = {
            "title": "【新規来客】",
            "participant": visitor_name,
            "company": visitor_company,
            "staff_name": staff.name,
            "staff_id": staff.id,  # ← staff_idを追加
            "date": timezone.now().strftime('%Y/%m/%d %H:%M'),
            "message": f"{visitor_company} の {visitor_name} 様がお見えです。ご対応をお願いします。"
        }

        # 3. 実際にTeamsへ飛ばす
        try:
            requests.post(notification_url, json=teams_data)
            print(f">>> {staff.name}の部署へ通知を送りました")
        except Exception as e:
            print(f">>> 通知エラー: {e}")

    return render(request, "frontend/screens/waiting.html", {
        "visitor_company": visitor_company,
        "visitor_name": visitor_name,
        "staff_name": staff.name if staff else "不明",
        "staff": staff,
        "purpose_preset":purpose_preset,
        "purpose_custom":purpose_custom,
        "escalation_seconds": escalation_seconds,
    })




def waiting2(request):
    """
    アポイントなし：担当者選択直後の待機画面。
    ここでTeamsへの通知を自動的に実行する。
    """
    staff_id = request.GET.get('staff_id')
    visitor_name = request.GET.get('visitor_name', 'お客様')
    visitor_company = request.GET.get('visitor_company', '（不明）')
    purpose_preset = request.GET.get('purpose_preset', '')
    purpose_custom = request.GET.get('purpose_custom', '')
    visit_type = request.GET.get('visit_type', 'no-appointment')

    staff = Staff.objects.filter(id=staff_id).first() if staff_id else None

    # Visitレコードを作成（ステータスは「待機中」）
    if staff:
        visit = create_visit(
            visitor_name=visitor_name,
            visitor_company=visitor_company,
            staff=staff,
            purpose_preset=purpose_preset,
            purpose_custom=purpose_custom,
            visit_type=visit_type
        )
        # ステータスを「待機中」に設定
        visit.status = "waiting"
        visit.save()

    # --- ここで自動的にTeams通知を送る ---
    if staff:
        notification_url = staff.department.teams_api_url if staff.department and staff.department.teams_api_url else AZURE_LOGIC_APP_URL_honbu
        
        payload = {
            "title": "【新規来客（アポなし）】",
            "participant": visitor_name,
            "company": visitor_company,
            "staff_name": staff.name,
            "staff_id": staff.id,  # ← staff_idを追加
            "message": f"⚠️ {visitor_company} の {visitor_name} 様がお見えです。ご対応をお願いします。"
        }
        try:
            res = requests.post(notification_url, json=payload)
            print(f">>> アポなし即時通知完了({staff.name}宛): {res.status_code}")
        except Exception as e:
            print(f">>> アポなし通知エラー: {e}")
    # ----------------------------------

    # 設定取得
    escalation_seconds = int(SystemSetting.get_setting("escalation_interval_seconds", 5))

    context = {
        'staff': staff,
        'staff_name': staff.name if staff else "不明",
        'visitor_name': visitor_name,
        'visitor_company': visitor_company,
        'purpose_preset': purpose_preset,
        'purpose_custom': purpose_custom,
        'visit_type': visit_type,
        'escalation_seconds': escalation_seconds,
    }
    return render(request, 'frontend/screens/waiting2.html', context)



def cancel_from_waiting2(request):
    """
    待機画面からのキャンセル時、URLやリファラ（前の画面）から「今のお客様」を確実に特定する。
    """
    # 1. まずURLのパラメータ(?visitor_name=...)から取得を試みる
    visitor_name = request.GET.get("visitor_name")
    visitor_company = request.GET.get("visitor_company")
    staff_id = request.GET.get("staff_id")

    # 2. 【重要】もしURLになければ、直前の画面URL(Referer)から情報を抜き出す
    # これにより、HTML側のボタン設定が不十分でも「今見ていた画面」の情報を救出できます
    if not visitor_name:
        referer = request.META.get('HTTP_REFERER', '')
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(referer)
        query_params = parse_qs(parsed_url.query)
        
        visitor_name = query_params.get('visitor_name', [None])[0]
        visitor_company = query_params.get('visitor_company', [None])[0]
        staff_id = query_params.get('staff_id', [None])[0]

    # 3. それでもダメならセッション（最後の手段）
    if not visitor_name:
        visitor_name = request.session.get("visitor_name", "お客様")
    if not visitor_company:
        visitor_company = request.session.get("visitor_company", "（不明）")
    if not staff_id:
        staff_id = request.session.get("staff_id")

    # 4. 担当者と通知URLの特定
    staff = Staff.objects.filter(id=staff_id).first() if staff_id else None
    notification_url = staff.department.teams_api_url if staff and staff.department and staff.department.teams_api_url else AZURE_LOGIC_APP_URL_honbu

    # 5. 通知データの作成
    cancel_data = {
        "title": "🔴【呼び出しキャンセル】",
        "participant": visitor_name,
        "company": visitor_company,
        "staff_name": staff.name if staff else "担当者",
        "message": f"⚠️ {visitor_name} 様の呼び出しはキャンセルされました。対応不要です。"
    }

    # 6. 送信とログ出力
    try:
        if notification_url:
            res = requests.post(notification_url, json=cancel_data)
            print(f">>> 【最優先確定】キャンセル通知送信: {visitor_name} 様 ({res.status_code})")
    except Exception as e:
        print(f">>> キャンセル通知エラー: {e}")

    # 7. データの掃除
    visit_id = request.session.get("visit_id")
    if visit_id:
        Visit.objects.filter(id=visit_id).delete()
    request.session.pop("visit_id", None)

    # 8. 適切な検索画面へ戻す
    visit_type = request.GET.get("visit_type") or request.session.get("visit_type", "no-appointment")
    from django.urls import reverse
    from urllib.parse import urlencode
    
    # ログの挙動に合わせ、アポあり(appointment)ならstaff_searchへ戻る
    target_view = 'frontend:staff_search' if visit_type == "appointment" else 'frontend:staff_search2'
    base_url = reverse(target_view)
    
    params = {"visitor_name": visitor_name, "visitor_company": visitor_company, "visit_type": visit_type}
    return redirect(f"{base_url}?{urlencode(params)}")

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
    
    # 1. 担当者情報を取得
    staff = Staff.objects.filter(id=staff_id).first() if staff_id and staff_id.isdigit() else None

    # ★ 2. 通知先URLを動的に決定する（ここが重要！）
    notification_url = None
    if staff and staff.department and staff.department.teams_api_url:
        # 担当者がいて、その所属部署にURLが設定されている場合
        notification_url = staff.department.teams_api_url
        print(f">>> 部署専用URLを使用します: {staff.department.name}")
    else:
        # 設定がない場合は、これまでの「本部」URLを予備として使う
        notification_url = AZURE_LOGIC_APP_URL_honbu
        print(">>> 部署URL未設定のため本部URLを使用します")

    # ★ 修正ポイント2: staff 取得後に通知データを作成する ★
    teams_data = {
        "title": "【新規来客】",
        "participant": visitor_name,
        "company": visitor_company,
        "staff_name": staff.name if staff else "担当者",
        "date": timezone.now().strftime('%Y/%m/%d %H:%M'),
        "message": f"{visitor_company} の {visitor_name} 様がお見えです。ご対応をお願いします。"
    }

    # 3. 決定したURLに対して送信
    try:
        res = requests.post(notification_url, json=teams_data) # 変数 notification_url を使う
        print(f">>> 通知完了: {res.status_code}")
    except Exception as e:
        print(f">>> 通知エラー: {e}")

    # 既存 Visit
    visit_id = request.session.get("visit_id")
    visit = Visit.objects.filter(id=visit_id).first() if visit_id else None

    url_visit_type = request.GET.get("visit_type")

    if visit:
        visit.status = status_param or "notified"
        visit.staff = staff
        
        if url_visit_type:
            visit.visit_type = url_visit_type
            
        if purpose_preset is not None:
            visit.purpose_preset = purpose_preset
        if purpose_custom is not None:
            visit.purpose_custom = purpose_custom
            
        visit.save()
        print(f"3. Visit updated. New DB visit_type: {visit.visit_type}")
    else:
        # 新規作成
        final_visit_type = url_visit_type if url_visit_type else "no-appointment"
        print(f"2. No Visit found. Creating new with visit_type: {final_visit_type}")
        
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
# views.py の notification_complete を以下に差し替え

def notification_complete(request):
    visitor_name = request.GET.get("visitor_name", "")
    visitor_company = request.GET.get("visitor_company", "")
    staff_id = request.GET.get("staff_id")
    purpose_preset = request.GET.get("purpose_preset")
    purpose_custom = request.GET.get("purpose_custom")
    status_param = request.GET.get("status") or "notified"
    url_visit_type = request.GET.get("visit_type")

    staff = Staff.objects.filter(id=staff_id).first() if staff_id and staff_id.isdigit() else None

    # 1. メッセージ内容の決定
    if staff:
        message_title = f"{staff.name}は不在のため、総務へ通知しました。"
        message_lead = "担当者が不在のため、総務へ通知いたしました。しばらくお待ちください。"
    else:
        message_title = "総務へ通知しました"
        message_lead = "総務へ通知いたしました。しばらくお待ちください。"

    # 2. 通知先 URL の決定 (★修正ポイント: notification_url を確実に定義)
    soumu_dept = Department.objects.filter(name="総務").first()
    target_url = soumu_dept.teams_api_url if soumu_dept and soumu_dept.teams_api_url else AZURE_LOGIC_APP_URL_soumu

    # 3. Teams 通知の送信
    try:
        teams_data = {
            "title": "【総務呼び出し】",
            "participant": visitor_name,
            "company": visitor_company,
            "staff_name": staff.name if staff else "不明",
            "date": timezone.now().strftime('%Y/%m/%d %H:%M'),
            "message": f"{visitor_company} の {visitor_name} 様がお見えですが、担当者が不在のため呼び出しがありました。"
        }
        #res = requests.post(target_url, json=teams_data)
        print("f>>> 通知完了: {res.status_code}")
    except Exception as e:
        print(f">>> 通知エラー: {e}")

    # 4. 既存 Visit の取得 (★修正ポイント: visit を確実に定義)
    visit_id = request.session.get("visit_id")
    visit = Visit.objects.filter(id=visit_id).first() if visit_id else None
    
    if visit:
        print(f">>> Visit found: {visit.id}")
        visit.status = status_param
        if staff:
            visit.staff = staff
        if url_visit_type:
            visit.visit_type = url_visit_type
        if purpose_preset is not None:
            visit.purpose_preset = purpose_preset
        if purpose_custom is not None:
            visit.purpose_custom = purpose_custom
        visit.responded_at = timezone.now()
        visit.save()
    else:
        # 新規作成
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

    # 5. セッション削除
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

@csrf_exempt # 外部（Teams等）から呼ばれる可能性がある場合は付けておきます
def handle_form_submission(request):
    """
    form.html からの送信結果を受け取り、対応可否に応じて通知を振り分ける
    """
    if request.method == "POST":
        # フォームからのデータを取得
        availability = request.POST.get("availability") # 'A' が対応可, 'B' が対応不可
        custom_message = request.POST.get("message", "")
        
        # どの来客の件か特定するための情報（URLパラメータやセッションから）
        staff_id = request.GET.get("staff_id")
        visitor_name = request.GET.get("visitor_name", "お客様")
        visitor_company = request.GET.get("visitor_company", "（不明）")
        
        staff = Staff.objects.filter(id=staff_id).first() if staff_id else None
        original_dept_url = staff.department.teams_api_url if staff and staff.department and staff.department.teams_api_url else AZURE_LOGIC_APP_URL_honbu

        # 該当するVisitレコードを探す（最新のもの）
        visit = Visit.objects.filter(
            visitor_name=visitor_name,
            visitor_company=visitor_company,
            staff=staff
        ).order_by('-created_at').first()

        if availability == "B":
            # --- 【対応不可】の場合：総務へ通知 ---
            
            # Visitレコードのステータスを更新（対応不可→総務へエスカレーション）
            # notification_complete画面で使われる "notified" ステータスに設定
            if visit:
                visit.status = "notified"
                visit.responded_at = timezone.now()
                visit.save()
            
            # 1. 元の部署へ
            requests.post(original_dept_url, json={
                "title": "🔴【対応不可・総務転送】",
                "participant": visitor_name,
                "company": visitor_company,
                "staff_name": staff.name if staff else "担当者",
                "message": f"⚠️ 担当者が対応不可を選択したため、総務へ転送されました。追加メッセージ: {custom_message}"
            })
            
            # 2. 総務へ（エスカレーション）
            soumu_dept = Department.objects.filter(name="総務").first()
            soumu_url = soumu_dept.teams_api_url if soumu_dept and soumu_dept.teams_api_url else AZURE_LOGIC_APP_URL_soumu
            
            requests.post(soumu_url, json={
                "title": "🚨【緊急・総務対応依頼】",
                "participant": visitor_name,
                "company": visitor_company,
                "staff_name": f"{staff.name}（対応不可）" if staff else "担当者（対応不可）",
                "message": f"‼️ 担当部署より対応不可の回答がありました。代わりの対応をお願いします。メッセージ: {custom_message}"
            })
            
            print(f">>> 対応不可通知を送信しました（{visitor_name}様分）")
            
            # 社員側には簡潔な完了メッセージを表示
            return render(request, "frontend/screens/staff_response_complete.html", {
                "message": "対応不可の通知を送信しました。総務へエスカレーションされました。"
            })

        else:
            # --- 【対応可能】の場合 ---
            
            # Visitレコードのステータスを「対応中」に更新
            # reception_complete画面で使われる "manager" ステータスに設定
            if visit:
                visit.status = "manager"
                visit.responded_at = timezone.now()
                visit.save()
            
            # 元の部署にメッセージを送る
            requests.post(original_dept_url, json={
                "title": "🟢【対応中】",
                "participant": visitor_name,
                "company": visitor_company,
                "staff_name": staff.name if staff else "担当者",
                "message": f"✅ 担当者が向かっています。メッセージ: {custom_message}"
            })
            
            # 社員側には簡潔な完了メッセージを表示
            return render(request, "frontend/screens/staff_response_complete.html", {
                "message": "対応可能の通知を送信しました。来訪者の画面が更新されます。"
            })

    return redirect('frontend:index')


def show_response_form(request):
    """
    Teamsのリンクから呼ばれ、対応入力フォーム(form.html)を表示する
    """
    # URLパラメータから情報を取得（Logic Appから渡される想定）
    context = {
        "staff_id": request.GET.get("staff_id"),
        "visitor_name": request.GET.get("visitor_name"),
        "visitor_company": request.GET.get("visitor_company"),
    }
    # スタッフ情報を念のため取得
    if context["staff_id"]:
        context["staff"] = Staff.objects.filter(id=context["staff_id"]).first()
        
    return render(request, "frontend/screens/form.html", context)


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



# API追記
#エンドポイント：部署階層取得
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


# --- ファイルの最後尾に貼り付け ---

def teams(request):
    """Teams（Logic App）へ通知を送る関数"""
    # 既存のロジックから必要な情報（訪問者名など）を取得して送る形に後で調整可能
    payload = {
        "title": "受付通知",
        "message": "来客があります。"
    }
    requests.post(AZURE_LOGIC_APP_URL_soumu, json=payload)
    return redirect('frontend:index') # indexへ戻る

@csrf_exempt
def teams_webhook(request):
    """外部からのWebhook（Teams返信など）を受け取る関数"""
    global latest_message, latest_title
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode('utf-8'))
            latest_message = data.get("message", "")
            latest_title = data.get("title", "")
            return JsonResponse({"status": "ok"})
        except:
            return JsonResponse({"status": "error"}, status=400)
    return JsonResponse({"error": "Method not allowed"}, status=405)

def show_message(request):
    """受け取ったメッセージを画面に表示する関数"""
    message_clean = latest_message.replace('<p>', '').replace('</p>', '')
    return render(request, "frontend/screens/show_message.html", {
        "title": latest_title,
        "message": message_clean,
    })

# 来訪者の待機画面用：Visitステータスをチェックするエンドポイント
@require_http_methods(["GET"])
def check_visit_status(request):
    """
    来訪者の待機画面から定期的に呼ばれ、対応状況を返す
    """
    staff_id = request.GET.get("staff_id")
    visitor_name = request.GET.get("visitor_name")
    visitor_company = request.GET.get("visitor_company")
    
    staff = Staff.objects.filter(id=staff_id).first() if staff_id else None
    
    # 該当するVisitレコードを探す（最新のもの）
    visit = Visit.objects.filter(
        visitor_name=visitor_name,
        visitor_company=visitor_company,
        staff=staff
    ).order_by('-created_at').first()
    
    if visit:
        return JsonResponse({
            "status": visit.status,
            "staff_name": staff.name if staff else "担当者"
        })
    else:
        return JsonResponse({
            "status": "waiting",
            "staff_name": staff.name if staff else "担当者"
        })
