from django.urls import path
from ToP.consumers import SalesRequestConsumer

websocket_urlpatterns = [
        path('ws/sales-requests/', SalesRequestConsumer.as_asgi()),
]