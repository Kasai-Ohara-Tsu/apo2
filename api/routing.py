from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/staff/(?P<staff_id>\w+)/$", consumers.NotificationConsumer.as_asgi()),
    re_path(r"ws/reception/$", consumers.ReceptionConsumer.as_asgi()),
]
