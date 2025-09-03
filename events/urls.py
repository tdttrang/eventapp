from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, EventViewSet, TicketViewSet, AdminStatsViewSet,
    BookingViewSet, NotificationViewSet, OrganizerViewSet,
    FirebaseLoginViewSet, vnpay_ipn, vnpay_return,
    EventReviewViewSet, ReviewReplyViewSet
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
router.register(r'reviews', EventReviewViewSet)
router.register(r'review-replies', ReviewReplyViewSet)


urlpatterns = [
    path('', include(router.urls)),
    # Thêm các endpoint tùy chỉnh cho MoMo
    path('bookings/<int:pk>/momo-init/', BookingViewSet.as_view({'post': 'momo_init'}), name='booking-momo-init'),
    path('bookings/<int:pk>/momo-callback/', BookingViewSet.as_view({'post': 'momo_callback'}),
         name='booking-momo-callback'),

    # endpoint vnpay
    path("vnpay_ipn/", vnpay_ipn, name="vnpay_ipn"),
    path("vnpay_return/", vnpay_return, name="vnpay_return"),

]

