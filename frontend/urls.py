from django.urls import path
from . import views

app_name = 'frontend'

urlpatterns = [
    path('', views.index, name='index'),
    path('visitor-info/', views.visitor_info, name='visitor_info'),
    path('staff-search/', views.staff_search, name='staff_search'),
    path('staff-search2/', views.staff_search2, name='staff_search2'),
    path('purpose-input/', views.purpose_input, name='purpose_input'),
    path('waiting/', views.waiting, name='waiting'),
    path('waiting2/', views.waiting2, name='waiting2'),
    path('reception-complete/', views.reception_complete, name='reception_complete'),
    path('notification-complete/', views.notification_complete, name='notification_complete'),
    path('which/', views.which, name='which'),
    path('cancel_from_waiting', views.cancel_from_waiting, name='cancel_from_waiting'),
    path('cancel_from_waiting2', views.cancel_from_waiting2, name='cancel_from_waiting2'),

    # path('notification/', views.notification, name='notification'),
    # path('staff-unavailable/', views.staff_unavailable, name='staff_unavailable'),
    # path('delivery/', views.delivery, name='delivery'),
    # path('collection/', views.collection, name='collection'),
    # path('courier/', views.courier, name='courier'),

    # API endpoints
    path('api/departments/', views.get_departments, name='get_departments'),
    path('api/staff/', views.get_staff, name='get_staff'),
    path('api/notify-staff/', views.notify_staff, name='notify_staff'),
]

