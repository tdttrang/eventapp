from django.shortcuts import render
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from .utils import send_booking_email_brevo, create_notification
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAdminUser, AllowAny
from . import serializers
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials, initialize_app, _apps, auth
from datetime import timedelta
from oauth2_provider.models import AccessToken, Application
from oauthlib.common import generate_token
from django.contrib.auth import get_user_model
from .serializers import FirebaseLoginSerializer
from rest_framework.viewsets import GenericViewSet
from django.db.models.functions import TruncMonth, TruncQuarter
from django.db.models import Count, Sum
from .models import (
    User, Event, EventReview, EventReviewReply,
    Ticket, Booking, Notification
)
from .serializers import (
    UserSerializer, EventSerializer, EventReviewSerializer,
    EventReviewReplySerializer, TicketSerializer, BookingCreateSerializer,
    BookingSerializer, NotificationSerializer, EventCreateSerializer,
    OrganizerRegisterSerializer, UserRegisterSerializer
)
from .permissions import IsApprovedOrganizer, IsOwner, IsAdmin
import traceback
import urllib.parse, hmac, hashlib
import json
import uuid
import requests
from django.conf import settings
from .utils import generate_qr_code
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from collections import OrderedDict
# -----------------------
# 1. UserViewSet
# Chỉ admin mới được xem danh sách người dùng
# -----------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    # tạo endpoint /users/register, mở quyền cho tất cả (allowany)
    @action(detail=False, methods=['post'], permission_classes=[AllowAny], serializer_class=UserRegisterSerializer,
            url_path='register')
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return User.objects.all()
        return User.objects.none()


class OrganizerViewSet(viewsets.GenericViewSet):
    # Chỉ lấy những user có role là 'organizer'
    queryset = User.objects.filter(role='organizer')

    # Dùng serializer để xử lý dữ liệu đầu vào
    serializer_class = OrganizerRegisterSerializer

    # Tùy theo action mà gán quyền khác nhau
    permission_classes_by_action = {
        'create': [AllowAny],  # Ai cũng có thể đăng ký
        'approve': [IsAdminUser],  # Chỉ admin mới được duyệt
    }

    # Gán permission theo action hiện tại
    def get_permissions(self):
        return [permission() for permission in self.permission_classes_by_action.get(self.action, [AllowAny])]

    # Xử lý đăng ký organizer (POST /organizers/)
    def create(self, request):
        # Lấy dữ liệu từ request và kiểm tra hợp lệ
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # Lưu dữ liệu nếu hợp lệ
            serializer.save()
            return Response(
                {'detail': 'Đăng ký tổ chức thành công. Vui lòng chờ admin duyệt.'},
                status=status.HTTP_201_CREATED
            )
        # Trả lỗi nếu dữ liệu không hợp lệ
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        try:
            organizer = self.get_object()
            if organizer.role != 'organizer':
                return Response({'detail': 'Người dùng này không phải organizer.'}, status=status.HTTP_400_BAD_REQUEST)

            organizer.is_approved = True
            organizer.save()
            return Response({'detail': 'Organizer đã được duyệt thành công.'}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'detail': 'Không tìm thấy người dùng.'}, status=status.HTTP_404_NOT_FOUND)

# -----------------------
# 2. EventViewSet
# Organizer có thể tạo/sửa/xóa sự kiện, người dùng có thể xem
# -----------------------
class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    filterset_fields = ['category', 'location', 'date']
    ordering_fields = ['date', 'average_rating', 'popularity']
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Nếu là tạo, sửa, xóa thì cần organizer đã được duyệt
        if self.action in ['create', 'update', 'destroy']:
            return [IsApprovedOrganizer()]
        # Các hành động khác thì ai cũng xem được
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        # Khi tạo sự kiện, tự động gán organizer là người đang đăng nhập
        serializer.save(organizer=self.request.user)

    def get_serializer_class(self):
        # Dùng EventCreateSerializer khi tạo mới để kiểm tra quyền và gán organizer
        if self.action == 'create':
            return EventCreateSerializer
        return EventSerializer

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request, pk=None):
        # Lấy sự kiện theo ID từ URL
        event = self.get_object()

        # Lọc các booking đã thanh toán cho sự kiện này
        bookings = Booking.objects.filter(ticket__event=event, status='paid')

        # Đếm số lượng vé đã bán
        total_tickets = bookings.count()

        # Tính tổng doanh thu từ các vé đã bán
        total_revenue = sum([b.ticket.price for b in bookings])

        # Lấy tất cả đánh giá của sự kiện
        reviews = event.reviews.all()

        # Trả về dữ liệu thống kê
        return Response({
            'event_name': event.name,
            'total_tickets_sold': total_tickets,
            'total_revenue': total_revenue,
            'average_rating': event.average_rating,
            'reviews': EventReviewSerializer(reviews, many=True).data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='dashboard-stats', permission_classes=[IsAdmin | IsApprovedOrganizer])
    def dashboard_stats(self, request):
        user = request.user

        events = self.get_queryset()
        tickets = Ticket.objects.all()
        reviews = EventReview.objects.all()

        if user.role == "organizer":
            events = events.filter(organizer=user)
            tickets = tickets.filter(event__organizer=user)
            reviews = reviews.filter(event__organizer=user)

        monthly_stats = (
            tickets.annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(revenue=Sum('price'), tickets=Count('id'))
            .order_by('month')
        )

        return Response({
            "total_events": events.count(),
            "total_tickets": tickets.count(),
            "total_revenue": tickets.aggregate(Sum('price'))['price__sum'] or 0,
            "total_reviews": reviews.count(),
            "monthly_stats": monthly_stats,
        })

# -----------------------
# 3. TicketViewSet
# Quản lý vé cho từng sự kiện
# -----------------------
class TicketViewSet(viewsets.ModelViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        # Chỉ organizer đã duyệt mới được tạo/sửa/xóa vé
        if self.action in ['create', 'update', 'destroy']:
            return [IsApprovedOrganizer()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        event_id = self.request.query_params.get('event_id')
        if event_id:
            return Ticket.objects.filter(event_id=event_id)
        return Ticket.objects.all()

    @action(detail=False, methods=['get'], url_path='stats-by-time', permission_classes=[IsAdmin | IsApprovedOrganizer])
    def stats_by_time(self, request):
        user = request.user
        mode = request.query_params.get('mode', 'month')
        trunc_func = TruncMonth if mode == 'month' else TruncQuarter

        tickets = self.get_queryset()
        if user.role == "organizer":
            tickets = tickets.filter(event__organizer=user)

        stats = (
            tickets.annotate(period=trunc_func('created_at'))
            .values('period')
            .annotate(total_revenue=Sum('price'), tickets_sold=Count('id'))
            .order_by('period')
        )
        return Response(stats)

# -----------------------
# 4. BookingViewSet
# Người dùng đặt vé, xem lịch sử, hủy vé
# -----------------------
class BookingViewSet(viewsets.ModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Chỉ hiển thị booking của người dùng hiện tại
        return Booking.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Tạo booking và gán user
        booking = serializer.save(user=self.request.user)

        # Gửi thông báo khi đặt vé thành công
        create_notification(
            user=self.request.user,
            notification_type="booking",
            subject="Đặt vé thành công",
            message=f"Bạn đã đặt vé cho sự kiện '{booking.ticket.event.name}'. Vui lòng thanh toán trong 10 phút.",
            related_object_id=booking.id
        )

    def get_serializer_class(self):
        if self.action in ["create", "book"]:
            return BookingCreateSerializer
        return BookingSerializer

        # override create -> cho phép tạo booking nhiều vé

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def book(self, request):
        try:
            ticket_id = request.data.get('ticket_id')
            print(f"Ticket ID: {ticket_id}, User: {request.user}, Authenticated: {request.user.is_authenticated}")
            ticket = get_object_or_404(Ticket, id=ticket_id)
            if ticket.event.date <= timezone.now():
                return Response({'detail': 'Không thể đặt vé cho sự kiện đã diễn ra.'}, status=status.HTTP_400_BAD_REQUEST)

            quantity = request.data.get('quantity', 1)
            booking = Booking.objects.create(
                user=request.user,
                ticket=ticket,
                quantity=quantity,
                status='pending',  # Đổi thành pending để phù hợp với logic thanh toán MoMo
                expires_at=timezone.now() + timedelta(minutes=10)
            )
            serializer = BookingSerializer(booking)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            print(f"Error: {str(e)}")
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], permission_classes=[IsOwner])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        event = booking.ticket.event
        event_start_time = booking.ticket.event.date
        now = timezone.now()

        if booking.status == 'cancelled':
            return Response({'detail': 'Đơn đã bị hủy trước đó.'}, status=status.HTTP_400_BAD_REQUEST)

        if now >= event_start_time:
            return Response({'detail': 'Không thể hủy vé sau khi sự kiện đã bắt đầu.'},
                            status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'cancelled'
        booking.save()
        # Gửi thông báo khi hủy đơn
        create_notification(
            user=request.user,
            notification_type="booking_cancel",
            subject="Hủy đơn hàng",
            message=f"Đơn hàng #{booking.id} đã bị hủy thành công.",
            related_object_id=booking.id
        )
        # Gửi thông báo cho organizer của sự kiện
        organizer = event.organizer
        create_notification(
            user=organizer.user,
            notification_type="booking_cancel_notice",
            subject="Người dùng hủy vé",
            message=f"Người dùng {request.user.username} đã hủy đơn hàng #{booking.id} cho sự kiện '{event.name}'.",
            related_object_id=booking.id
        )
        return Response({'detail': 'Đã hủy đơn thành công.'})

    @action(detail=True, methods=['post'], permission_classes=[IsApprovedOrganizer])
    def check_in(self, request, pk=None):
        booking = self.get_object()
        event = booking.ticket.event

        if event.organizer != request.user:
            return Response({'detail': 'Bạn không có quyền xác nhận người tham gia cho sự kiện này.'},
                            status=status.HTTP_403_FORBIDDEN)

        if booking.status != 'paid':
            return Response({'detail': 'Vé không hợp lệ để check-in.'}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'checked_in'
        booking.save()
        return Response({'detail': 'Check-in thành công.'})

    # @action(detail=True, methods=['post'], permission_classes=[IsOwner])
    # def pay(self, request, pk=None):
    #     booking = self.get_object()
    #
    #     if booking.status != 'pending':
    #         return Response({'detail': 'Chỉ có thể thanh toán đơn đang chờ.'}, status=status.HTTP_400_BAD_REQUEST)
    #
    #     # Giả lập thanh toán thành công
    #     booking.status = 'paid'
    #     booking.save()
    #
    #     # Gửi email xác nhận qua Brevo
    #     try:
    #         send_booking_email_brevo(
    #             to_email=request.user.email,
    #             subject=f"Xác nhận đặt vé - {booking.ticket.event.name}",
    #             message=f"Bạn đã thanh toán thành công. Mã QR: {booking.qr_code.url}"
    #         )
    #     except Exception as e:
    #         return Response({'detail': 'Thanh toán thành công, nhưng gửi email thất bại.', 'error': str(e)},
    #                         status=status.HTTP_202_ACCEPTED)
    #
    #     return Response({'detail': 'Thanh toán thành công.'})

    # thanh toan qua momo
    @action(detail=True, methods=['post'], permission_classes=[IsOwner])
    def momo_init(self, request, pk=None):
        booking = self.get_object()

        if booking.status != 'pending':
            return Response({'detail': 'Chỉ có thể thanh toán đơn đang chờ.'}, status=status.HTTP_400_BAD_REQUEST)

        if booking.expires_at < timezone.now():
            booking.status = 'cancelled'
            booking.save()
            return Response({'detail': 'Đơn hàng đã hết hạn.'}, status=status.HTTP_400_BAD_REQUEST)

        # Tính số tiền dựa trên ticket.price và quantity
        amount = int(booking.ticket.price * booking.quantity)
        order_id = f"MOMO-{booking.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
        order_info = f"Thanh toán vé sự kiện {booking.ticket.event.name}"

        # Tạo chữ ký (signature) cho MoMo
        raw_signature = (
            f"accessKey={settings.MOMO_ACCESS_KEY}&amount={amount}&extraData=&ipnUrl={settings.MOMO_IPN_URL}"
            f"&orderId={order_id}&orderInfo={order_info}&partnerCode={settings.MOMO_PARTNER_CODE}"
            f"&redirectUrl={settings.MOMO_REDIRECT_URL}&requestId={order_id}&requestType=captureWallet"
        )
        signature = hmac.new(
            settings.MOMO_SECRET_KEY.encode(),
            raw_signature.encode(),
            hashlib.sha256
        ).hexdigest()

        # Payload gửi đến MoMo
        payload = {
            "partnerCode": settings.MOMO_PARTNER_CODE,
            "requestId": order_id,
            "amount": amount,
            "orderId": order_id,
            "orderInfo": order_info,
            "redirectUrl": settings.MOMO_REDIRECT_URL,
            "ipnUrl": f"{settings.MOMO_IPN_URL}/{booking.id}/momo-callback/",
            "requestType": "captureWallet",
            "extraData": "",  # Có thể mã hóa Base64 thông tin bổ sung
            "lang": "vi",
            "signature": signature
        }

        try:
            response = requests.post(settings.MOMO_ENDPOINT, json=payload)
            result = response.json()
            print(f"MoMo request: {payload}")
            print(f"MoMo response: {result}")
            if result.get('resultCode') == 0:
                booking.payment_code = order_id
                booking.save()
                return Response({
                    "payment_url": result.get('payUrl'),
                    "deeplink": result.get('deeplink'),
                    "qr_code_url": result.get('qrCodeUrl'),
                    "order_id": order_id,
                    "amount": amount
                }, status=status.HTTP_200_OK)
            else:
                return Response({"detail": result.get('message')}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    @action(detail=True, methods=['post'], permission_classes=[AllowAny], url_path='momo-callback')
    def momo_callback(self, request, pk=None):
        booking = self.get_object()
        data = request.data
        result_code = data.get("result_code")
        order_id = data.get('orderId')
        message = data.get("message", "")

        # Kiểm tra chữ ký từ MoMo để đảm bảo an toàn
        raw_signature = (
            f"accessKey={settings.MOMO_ACCESS_KEY}&amount={data.get('amount')}&extraData={data.get('extraData')}"
            f"&message={message}&orderId={order_id}&orderInfo={data.get('orderInfo')}"
            f"&orderType={data.get('orderType')}&partnerCode={data.get('partnerCode')}"
            f"&payType={data.get('payType')}&requestId={data.get('requestId')}"
            f"&responseTime={data.get('responseTime')}&resultCode={result_code}"
            f"&transId={data.get('transId')}"
        )
        signature = hmac.new(
            settings.MOMO_SECRET_KEY.encode(),
            raw_signature.encode(),
            hashlib.sha256
        ).hexdigest()

        if signature != data.get('signature'):
            return Response({"detail": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        if result_code == 0:
            booking.status = 'paid'
            booking.expires_at = None
            # Tạo QR code (giả sử dùng Cloudinary)
            qr_data = f"Booking-{booking.id}-{booking.ticket.event.name}"
            qr_image = generate_qr_code(qr_data)  # Hàm tạo QR code
            booking.qr_code = qr_image
            booking.save()
            try:
                send_booking_email_brevo(
                    to_email=booking.user.email,
                    subject=f"Xác nhận đặt vé - {booking.ticket.event.name}",
                    message=f"Bạn đã thanh toán thành công qua MoMo. Mã QR: {booking.qr_code.url}"
                )
            except Exception as e:
                return Response(
                    {'detail': 'Thanh toán thành công, nhưng gửi email thất bại.', 'error': str(e)},
                    status=status.HTTP_202_ACCEPTED
                )
            return Response({'detail': 'Thanh toán MoMo thành công.'}, status=status.HTTP_200_OK)
        else:
            booking.status = 'cancelled'
            booking.save()
            return Response({"detail": "Thanh toán thất bại", "message": message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def vnpay_init(self, request, pk=None):
        booking = self.get_object()

        if booking.status != "pending":
            return Response({"detail": "Booking không ở trạng thái pending"}, status=400)

        # Tính tổng tiền từ các chi tiết vé
        total_amount = sum([d.ticket.price * d.quantity for d in booking.details.all()])

        order_id = f"{booking.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        vnp_Params = {
            "vnp_Version": "2.1.0",
            "vnp_Command": "pay",
            "vnp_TmnCode": settings.VNP_TMN_CODE,
            "vnp_Amount": int(total_amount) * 100,  # VNPay yêu cầu nhân 100
            "vnp_CurrCode": "VND",
            "vnp_TxnRef": order_id,
            "vnp_OrderInfo": f"Thanh toan booking {booking.id}",
            "vnp_OrderType": "other",
            "vnp_Locale": "vn",
            "vnp_ReturnUrl": settings.VNP_RETURN_URL,
            "vnp_IpAddr": request.META.get("REMOTE_ADDR"),
            "vnp_CreateDate": timezone.now().strftime("%Y%m%d%H%M%S"),
        }

        # Sắp xếp tham số
        sorted_params = sorted(vnp_Params.items())
        query_string = urllib.parse.urlencode(sorted_params)

        # Tạo hash
        hashdata = "&".join([f"{k}={v}" for k, v in sorted_params])
        secure_hash = hmac.new(
            settings.VNP_HASH_SECRET.encode("utf-8"),
            hashdata.encode("utf-8"),
            hashlib.sha512
        ).hexdigest()

        payment_url = f"{settings.VNP_URL}?{query_string}&vnp_SecureHash={secure_hash}"

        return Response({"payment_url": payment_url})
# -----------------------
# 5. NotificationViewSet
# Hiển thị thông báo của người dùng
# -----------------------
class NotificationViewSet(ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsOwner]

    def get_queryset(self):
        # Chỉ hiển thị thông báo của người dùng hiện tại
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def mark_as_read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save()
        return Response({'detail': 'Thông báo đã được đánh dấu là đã đọc.'})


# -----------------------
# EventReview
# Người dung viết đánh giá
# -----------------------
class EventReviewViewSet(viewsets.ModelViewSet):
    queryset = EventReview.objects.all()
    serializer_class = EventReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Nếu có truyền event_id → lọc theo sự kiện
        event_id = self.request.query_params.get('event_id')
        if event_id:
            return EventReview.objects.filter(event_id=event_id)
        return EventReview.objects.all()

    def perform_create(self, serializer):
        # Gán user hiện tại vào review
        serializer.save(user=self.request.user)

    def perform_create(self, serializer):
        user = self.request.user
        event = serializer.validated_data['event']
        has_booking = Booking.objects.filter(user=user, ticket__event=event, status='paid').exists()
        if not has_booking:
            raise serializers.ValidationError("Bạn chưa tham gia sự kiện này.")
        serializer.save(user=user)


# -----------------------
# ReviewReply
# Organizer phản hồi
# -----------------------
class ReviewReplyViewSet(viewsets.ModelViewSet):
    queryset = EventReviewReply.objects.all()
    serializer_class = EventReviewReplySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        review_id = self.request.query_params.get('review_id')
        if review_id:
            return EventReviewReply.objects.filter(review_id=review_id)
        return EventReviewReply.objects.all()

    def perform_create(self, serializer):
        # Gán user hiện tại vào reply
        serializer.save(user=self.request.user)


class AdminStatsViewSet(GenericViewSet):
    permission_classes = [IsAdminUser]

    @action(detail=False, methods=['get'])
    def global_stats(self, request):
        # Lấy dữ liệu booking đã thanh toán, nhóm theo tháng
        monthly_data = Booking.objects.filter(status='paid') \
            .annotate(month=TruncMonth('created_at')) \
            .values('month') \
            .annotate(
                total_participants=Count('id'),      # Số người tham gia
                total_revenue=Sum('ticket__price')   # Tổng doanh thu
            ) \
            .order_by('month')

        # Trả về thống kê toàn hệ thống
        return Response({
            'total_events': Event.objects.count(),   # Tổng số sự kiện
            'monthly_stats': monthly_data            # Dữ liệu theo tháng
        })

User = get_user_model()

# 🔐 Khởi tạo Firebase Admin SDK nếu chưa khởi tạo
if not _apps:
    cred = credentials.Certificate("firebase_key.json")  # ✅ Đảm bảo đường dẫn đúng
    initialize_app(cred)

class FirebaseLoginViewSet(viewsets.ModelViewSet):
    serializer_class = FirebaseLoginSerializer
    http_method_names = ['post']
    authentication_classes = []  # ✅ Không yêu cầu xác thực
    permission_classes = [AllowAny]  # ✅ Cho phép mọi người gọi

    def create(self, request, *args, **kwargs):
        try:
            # ✅ Bước 1: Validate dữ liệu đầu vào
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            id_token = serializer.validated_data["id_token"]

            # ✅ Bước 2: Giải mã Firebase token
            try:
                decoded_token = auth.verify_id_token(id_token)
            except Exception as e:
                print("❌ Firebase token decode failed:", traceback.format_exc())
                return Response({'error': str(e)}, status=400)

            uid = decoded_token["uid"]
            email = decoded_token.get("email")
            name = decoded_token.get("name", "")

            # ✅ Bước 3: Tìm hoặc tạo user tương ứng
            user, created = User.objects.get_or_create(
                username=uid,
                defaults={
                    "email": email,
                    "first_name": name,
                    "role": "attendee"
                }
            )
            if created:
                user.role = "attendee"
                user.save()

            if not created:
                user.first_name = name
                user.save()

            # ✅ Bước 4: Lấy Application "postman_test"
            try:
                app = Application.objects.get(name="postman_test")
            except Application.DoesNotExist:
                print("❌ Application 'postman_test' not found")
                return Response({
                    "error": "OAuth2 Application 'postman_test' not found"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # ✅ Bước 5: Tạo access_token OAuth2
            expires = timezone.now() + timedelta(days=1)
            access_token = AccessToken.objects.create(
                user=user,
                token=generate_token(),
                application=app,
                expires=expires,
                scope="read write"
            )

            # ✅ Bước 6: Trả về token cho client
            return Response({
                "access_token": access_token.token,
                "token_type": "Bearer",
                "expires_in": 86400,
                "scope": access_token.scope
            })

        except Exception as e:
            print("❌ Lỗi không xác định:", traceback.format_exc())
            return Response({
                "error": "Internal Server Error",
                "detail": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def vnpay_ipn(request):
    inputData = request.GET.dict()
    vnp_SecureHash = inputData.pop("vnp_SecureHash", None)

    # Sắp xếp tham số theo thứ tự alphabet
    ordered_data = OrderedDict(sorted(inputData.items()))

    # Tạo chuỗi hashData
    hashData = "&".join([f"{k}={v}" for k, v in ordered_data.items()])

    # Tạo chữ ký
    secure_hash = hmac.new(
        bytes(settings.VNP_HASH_SECRET, "utf-8"),
        bytes(hashData, "utf-8"),
        hashlib.sha512
    ).hexdigest()

    if secure_hash != vnp_SecureHash:
        return JsonResponse({"RspCode": "97", "Message": "Invalid signature"})

    # Kiểm tra chữ ký
    sorted_params = sorted(inputData.items())
    hashData = "&".join([f"{k}={v}" for k, v in sorted_params])
    secure_hash = hmac.new(
        settings.VNP_HASH_SECRET.encode("utf-8"),
        hashData.encode("utf-8"),
        hashlib.sha512
    ).hexdigest()

    if secure_hash != vnp_SecureHash:
        return JsonResponse({"RspCode": "97", "Message": "Invalid signature"})

    # Lấy booking_id từ vnp_OrderInfo
    order_info = inputData.get("vnp_OrderInfo", "")
    booking_id = order_info.replace("Thanh toan booking ", "").strip()

    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        return JsonResponse({"RspCode": "01", "Message": "Booking not found"})

    if inputData.get("vnp_ResponseCode") == "00":
        booking.status = "paid"
        booking.payment_code = inputData.get("vnp_TransactionNo")
        booking.save()
        return JsonResponse({"RspCode": "00", "Message": "Confirm Success"})
    else:
        booking.status = "cancelled"
        booking.save()
        return JsonResponse({"RspCode": "00", "Message": "Payment failed"})