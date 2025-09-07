from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, EventViewSet, TicketViewSet, AdminStatsViewSet,
    BookingViewSet, NotificationViewSet, OrganizerViewSet,
    FirebaseLoginViewSet, vnpay_ipn, vnpay_return, paypal_config,
    paypal_return, paypal_cancel,
    EventReviewViewSet, ReviewReplyViewSet, NotificationSenderViewSet,
    OrganizerStatsViewSet,
)

# Tạo router tự động
router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'events', EventViewSet, basename='event')
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'bookings', BookingViewSet)
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'organizers', OrganizerViewSet, basename='organizer')
router.register(r'admin/stats', AdminStatsViewSet, basename='admin-stats')
router.register(r'firebase-login', FirebaseLoginViewSet, basename='firebase-login')
router.register(r'reviews', EventReviewViewSet)
router.register(r'review-replies', ReviewReplyViewSet)
router.register(r'notifications/sender', NotificationSenderViewSet, basename='notification-sender')
router.register(r'organizer/stats', OrganizerStatsViewSet, basename='organizer-stats')


urlpatterns = [
    path('', include(router.urls)),
    # Thêm các endpoint tùy chỉnh cho MoMo
    path('bookings/<int:pk>/momo-init/', BookingViewSet.as_view({'post': 'momo_init'}), name='booking-momo-init'),
    path('bookings/<int:pk>/momo-callback/', BookingViewSet.as_view({'post': 'momo_callback'}),
         name='booking-momo-callback'),

    # endpoint vnpay
    path("vnpay_ipn/", vnpay_ipn, name="vnpay_ipn"),
    path("vnpay_return/", vnpay_return, name="vnpay_return"),

    # endpoint paypal config
    path("paypal/config/", paypal_config, name="paypal-config"),
    path("paypal_return/<int:booking_id>/", paypal_return, name="paypal_return"),
    path("paypal_cancel/<int:booking_id>/", paypal_cancel, name="paypal_cancel"),
]

