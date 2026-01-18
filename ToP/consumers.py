from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from .models import SalesOperation
import logging

logger = logging.getLogger(__name__)

class SalesRequestConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.company_group_name = None
        user = self.scope["user"]

        if user.is_authenticated:
            logger.info(f"WebSocket connect initiated by authenticated user: {user.email}")
            try:
                company_id = await self.get_user_company_id(user)
                self.company_group_name = f"sales_requests_{company_id}"

                logger.info(f"User {user.email} joined WebSocket group: {self.company_group_name}")
                await self.channel_layer.group_add(self.company_group_name, self.channel_name)
                await self.accept()
            except SalesOperation.DoesNotExist:
                logger.error(f"SalesOperation does not exist for user: {user.email}")
                await self.close()
            except Exception as e:
                logger.exception("Unexpected error during connect")
                await self.close()
        else:
            logger.warning("WebSocket connection attempt by unauthenticated user.")
            await self.close()

    async def disconnect(self, close_code):
        if self.company_group_name:
            try:
                logger.info(f"Disconnecting from group: {self.company_group_name}")
                await self.channel_layer.group_discard(self.company_group_name, self.channel_name)
            except Exception:
                logger.exception("Error during disconnect")

    async def send_sales_request(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "new_request",
                "data": event["data"],
            }))
            logger.info(f"Sent new sales request to group {self.company_group_name}")
        except Exception:
            logger.exception("Failed to send sales request via WebSocket")

    @database_sync_to_async
    def get_user_company_id(self, user):
        controller = SalesOperation.objects.get(user=user)
        return controller.company.id
