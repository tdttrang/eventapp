from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, EventViewSet, TicketViewSet, AdminStatsViewSet,
    BookingViewSet, NotificationViewSet, OrganizerViewSet,
    FirebaseLoginViewSet,
)
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.urls import path

# Tạo router tự động
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'events', EventViewSet)
router.register(r'tickets', TicketViewSet)
router.register(r'bookings', BookingViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'organizers', OrganizerViewSet, basename='organizer')
router.register(r'admin/stats', AdminStatsViewSet, basename='admin-stats')
router.register(r'firebase-login', FirebaseLoginViewSet, basename='firebase-login')
urlpatterns = [
    path('', include(router.urls)),
]

