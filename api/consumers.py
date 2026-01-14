import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.staff_id = self.scope["url_route"]["kwargs"]["staff_id"]
        self.room_group_name = f"staff_{self.staff_id}"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def visitor_notification(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def escalation_notification(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def ping(self, event):
        await self.send(text_data=json.dumps({"type": "pong"}))

class ReceptionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = "reception"
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def visit_status_update(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def ping(self, event):
        await self.send(text_data=json.dumps({"type": "pong"}))

