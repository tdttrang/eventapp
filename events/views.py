from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework import viewsets, permissions, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
import logging
import pytz, socket
import uuid
from .utils import send_booking_email_brevo, create_notification
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAdminUser, AllowAny
# from . import serializers
from firebase_admin import credentials, initialize_app, _apps, auth
from datetime import datetime, timedelta
from oauth2_provider.models import AccessToken, Application
from oauthlib.common import generate_token
from django.contrib.auth import get_user_model
from .serializers import FirebaseLoginSerializer
from rest_framework.viewsets import GenericViewSet
from django.db.models.functions import TruncMonth, TruncQuarter
from django.db.models import Count, Sum
from .models import (
    User, Event, EventReview, EventReviewReply,
    Ticket, Booking, Notification, BookingDetail
)
from .serializers import (
    UserSerializer, EventSerializer, EventReviewSerializer,
    EventReviewReplySerializer, TicketSerializer, BookingCreateSerializer,
    BookingSerializer, NotificationSerializer, EventCreateSerializer,
    OrganizerRegisterSerializer, UserRegisterSerializer
)
from .permissions import IsApprovedOrganizer, IsOwner, IsAdmin
import traceback
import hmac, hashlib
import requests
from django.conf import settings
from .utils import generate_qr_code
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .vnpay import vnpay
from django.http import HttpResponse
from django.db.models import F, ExpressionWrapper, DecimalField
from django_filters import rest_framework as filters
from rest_framework.parsers import MultiPartParser, FormParser
from decimal import Decimal
from .paypal_client import PayPalClient
from rest_framework.exceptions import PermissionDenied
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

    # endpoint /api/users/me/: lấy thông tin ngươif dùng hiện tại, chỉ người dùng đã đăng nhập mới truy cập được
    # chinh sua thong tin nguoi dung
    @action(
        detail=False,
        methods=['get', 'patch', 'delete'],
        permission_classes=[IsAuthenticated],
        url_path='me'
    )
    def me(self, request):
        if request.method == 'GET':
            serializer = self.get_serializer(request.user, context={'request': request})
            return Response(serializer.data)

        elif request.method == 'PATCH':
            serializer = self.get_serializer(
                request.user,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        elif request.method == 'DELETE':
            # Ví dụ: chỉ xóa avatar
            user = request.user
            user.avatar.delete(save=False)  # xóa file vật lý nếu dùng ImageField
            user.avatar = None
            user.save()
            serializer = self.get_serializer(user, context={'request': request})
            return Response(serializer.data, status=200)

    # endpoint upload avtar
    @action(
        detail=False, methods=['post'],
        permission_classes=[IsAuthenticated],
        url_path='me/avatar',
        parser_classes=[MultiPartParser, FormParser]
    )
    def upload_avatar(self, request):
        user = request.user
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)

        # Gán file mới, CloudinaryStorage sẽ tự upload
        user.avatar = avatar_file
        user.save()

        # Trả về full thông tin user, avatar là URL Cloudinary
        serializer = self.get_serializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


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


class EventFilter(filters.FilterSet):
    date__gte = filters.DateFilter(field_name="date", lookup_expr='gte')  # Từ ngày
    date__lte = filters.DateFilter(field_name="date", lookup_expr='lte')  # Đến ngày
    location = filters.CharFilter(field_name="location", lookup_expr='icontains')  # Partial match (không case-sensitive)

    class Meta:
        model = Event
        fields = ['category', 'location', 'date', 'date__gte', 'date__lte']
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
    ordering = ['id']

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

        # Tính từ BookingDetail thay vì Booking
        details = BookingDetail.objects.filter(
            ticket__event=event,
            booking__status='paid'
        )

        # Đếm số lượng vé đã bán
        total_tickets = sum([d.quantity for d in details])

        # Tính tổng doanh thu từ các vé đã bán
        total_revenue = sum([d.ticket.price * d.quantity for d in details])

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

    @action(detail=False, methods=['get'], url_path='dashboard-stats',
            permission_classes=[IsAdmin | IsApprovedOrganizer])
    def dashboard_stats(self, request):
        user = request.user

        events = self.get_queryset()
        details = BookingDetail.objects.all()
        tickets = Ticket.objects.all()
        reviews = EventReview.objects.all()

        if user.role == "organizer":
            events = events.filter(organizer=user)
            details = details.filter(ticket__event__organizer=user)
            tickets = tickets.filter(event__organizer=user)
            reviews = reviews.filter(event__organizer=user)

        # Fix monthly_stats: Wrap expression price * quantity
        revenue_expression = ExpressionWrapper(
            F('ticket__price') * F('quantity'),
            output_field=DecimalField(max_digits=12, decimal_places=2)  # Adjust max_digits nếu revenue lớn
        )
        monthly_stats = (
            details.annotate(month=TruncMonth('booking__created_at'))
            .values('month')
            .annotate(
                revenue=Sum(revenue_expression),
                tickets=Sum('quantity')
            )
            .order_by('month')
        )
        # Fix total_revenue: Dùng aggregate thay vì sum list (tối ưu, không fetch all)
        total_revenue_agg = details.aggregate(
            total=Sum(revenue_expression, filter=F('booking__status') == 'paid')
        )['total'] or 0

        # Total_tickets cũng aggregate cho nhất quán
        total_tickets_agg = details.aggregate(
            total=Sum('quantity', filter=F('booking__status') == 'paid')
        )['total'] or 0

        return Response({
            "total_events": events.count(),
            "total_tickets": total_tickets_agg,
            "total_revenue": total_revenue_agg,
            "total_reviews": reviews.count(),
            "monthly_stats": monthly_stats,
        })

    # api: events/locations
    @action(detail=False, methods=['get'], url_path='locations')
    def get_locations(self, request):
        locations = Event.objects.values_list('location', flat=True).distinct()
        return Response(locations)

    # api: events/categories
    @action(detail=False, methods=['get'], url_path='categories')
    def get_categories(self, request):
        categories = Event.objects.values_list('category', flat=True).distinct()
        return Response(categories)
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

        details = BookingDetail.objects.all()
        if user.role == "organizer":
            details = details.filter(ticket__event__organizer=user)

        # Fix stats: Wrap expression
        revenue_expression = ExpressionWrapper(
            F('ticket__price') * F('quantity'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
        stats = (
            details.annotate(period=trunc_func('booking__created_at'))
            .values('period')
            .annotate(
                total_revenue=Sum(revenue_expression),
                tickets_sold=Sum('quantity')
            )
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

    # def perform_create(self, serializer):
    #     # Tạo booking và gán user
    #     booking = serializer.save(user=self.request.user)
    #
    #     # Gửi thông báo khi đặt vé thành công
    #     create_notification(
    #         user=self.request.user,
    #         notification_type="booking",
    #         subject="Đặt vé thành công",
    #         message=f"Bạn đã đặt vé cho sự kiện '{booking.ticket.event.name}'. Vui lòng thanh toán trong 10 phút.",
    #         related_object_id=booking.id
    #     )

    def get_serializer_class(self):
        if self.action in ["create", "book"]:
            return BookingCreateSerializer
        return BookingSerializer

        # override create -> cho phép tạo booking nhiều vé

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        # Gửi notification (di chuyển từ perform_create, lấy event từ details)
        if booking.details.exists():
            event_name = booking.details.first().ticket.event.name
            create_notification(
                user=request.user,
                notification_type="booking",
                subject="Đặt vé thành công",
                message=f"Bạn đã đặt vé cho sự kiện '{event_name}'. Vui lòng thanh toán trong 10 phút.",
                related_object_id=booking.id
            )
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def book(self, request):
        # Thống nhất với create: Wrap thành list tickets nếu chỉ 1 vé
        ticket_id = request.data.get('ticket_id')
        quantity = request.data.get('quantity', 1)
        if not ticket_id:
            return Response({'detail': 'Ticket ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        data = {"tickets": [{"ticket_id": ticket_id, "quantity": quantity}]}
        serializer = BookingCreateSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsOwner])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if not booking.details.exists():
            return Response({'detail': 'Booking không có chi tiết vé.'}, status=status.HTTP_400_BAD_REQUEST)
        event = booking.details.first().ticket.event  # Lấy event từ details
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
            user=event.organizer,
            notification_type="booking_cancel_notice",
            subject="Người dùng hủy vé",
            message=f"Người dùng {request.user.username} đã hủy đơn hàng #{booking.id} cho sự kiện '{event.name}'.",
            related_object_id=booking.id
        )
        return Response({'detail': 'Đã hủy đơn thành công.'})

    @action(detail=True, methods=['post'], permission_classes=[IsApprovedOrganizer])
    def check_in(self, request, pk=None):
        booking = self.get_object()
        if not booking.details.exists():
            return Response({'detail': 'Booking không có chi tiết vé.'}, status=status.HTTP_400_BAD_REQUEST)
        event = booking.details.first().ticket.event

        if event.organizer != request.user:
            return Response({'detail': 'Bạn không có quyền xác nhận người tham gia cho sự kiện này.'},
                            status=status.HTTP_403_FORBIDDEN)

        if booking.status != 'paid':
            return Response({'detail': 'Vé không hợp lệ để check-in.'}, status=status.HTTP_400_BAD_REQUEST)

        booking.status = 'checked_in'
        booking.save()
        return Response({'detail': 'Check-in thành công.'})

    @action(detail=True, methods=['post'], permission_classes=[IsOwner])
    def momo_init(self, request, pk=None):
        booking = self.get_object()

        if booking.status != 'pending':
            return Response({'detail': 'Chỉ có thể thanh toán đơn đang chờ.'}, status=status.HTTP_400_BAD_REQUEST)

        if booking.expires_at < timezone.now():
            booking.status = 'cancelled'
            booking.save()
            return Response({'detail': 'Đơn hàng đã hết hạn.'}, status=status.HTTP_400_BAD_REQUEST)

        # Tính amount từ details
        amount = int(sum([d.ticket.price * d.quantity for d in booking.details.all()]))
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
        data = request.data
        booking = self.get_object()
        order_id = data.get("orderId")
        result_code = data.get("resultCode")
        message = data.get("message", "")

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
            # Fix qr_data dùng details
            event_name = booking.details.first().ticket.event.name if booking.details.exists() else "Sự kiện không xác định"
            qr_data = f"Booking-{booking.id}-{event_name}"
            qr_image = generate_qr_code(qr_data)  # Hàm tạo QR code
            booking.qr_code = qr_image
            booking.save()
            try:
                send_booking_email_brevo(
                    to_email=booking.user.email,
                    subject=f"Xác nhận đặt vé - {event_name}",
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

        #total_amount = sum([d.ticket.price * d.quantity for d in booking.details.all()])
        total_amount = sum([Decimal(d.ticket.price) * d.quantity for d in booking.details.all()])
        print(">>> [DEBUG] total_amount (VND):", total_amount)

        order_id = f"{booking.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"

        # khởi tạo vnpay
        vnp = vnpay()
        vnp.requestData['vnp_Version'] = '2.1.0'
        vnp.requestData['vnp_Command'] = 'pay'
        vnp.requestData['vnp_TmnCode'] = settings.VNP_TMN_CODE
        vnp.requestData['vnp_Amount'] = int(total_amount * 100)
        vnp.requestData['vnp_CurrCode'] = 'VND'
        vnp.requestData['vnp_TxnRef'] = order_id
        vnp.requestData['vnp_OrderInfo'] = f"Thanh toan booking {booking.id}"
        vnp.requestData['vnp_OrderType'] = 'billpayment'
        vnp.requestData['vnp_Locale'] = 'vn'
        # ✅ Thêm BankCode test của VNPAY (NCB là thẻ test)
        vnp.requestData['vnp_BankCode'] = 'NCB'
        vnp.requestData['vnp_ReturnUrl'] = settings.VNP_RETURN_URL
        vnp.requestData['vnp_IpnUrl'] = settings.VNP_IPN_URL

        # set timezone VN
        tz = pytz.timezone('Asia/Ho_Chi_Minh')
        current_time = timezone.localtime(timezone.now())
        vnp.requestData['vnp_CreateDate'] = current_time.strftime("%Y%m%d%H%M%S")
        vnp.requestData['vnp_ExpireDate'] = (current_time + timedelta(minutes=15)).strftime("%Y%m%d%H%M%S")

        print(">>> [DEBUG] current_time local:", current_time)
        print(">>> [DEBUG] current_time UTC:", timezone.now())

        # ip address
        # try:
        #     ip_addr = (
        #             request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0]
        #             or request.META.get("REMOTE_ADDR", "")
        #             or "127.0.0.1"
        #     )
        #     # ép IPv6 -> IPv4
        #     ip_addr = socket.gethostbyname(ip_addr)
        # except Exception:
        #     ip_addr = "127.0.0.1"
        # vnp.requestData['vnp_IpAddr'] = ip_addr

        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if xff:
            ip_addr = xff.split(",")[0].strip()
        else:
            ip_addr = request.META.get("REMOTE_ADDR", "127.0.0.1")

        # Nếu dạng IPv6 mapped IPv4 ('::ffff:1.2.3.4') -> lấy IPv4
        if ip_addr.startswith("::ffff:"):
            ip_addr = ip_addr.split(":")[-1]

        vnp.requestData["vnp_IpAddr"] = ip_addr
        # In log chi tiết
        print(">>> VNPAY requestData:", vnp.requestData)

        vnp.requestData['vnp_Amount'] = int(total_amount * 100)
        print(">>> [DEBUG] vnp_Amount gửi đi:", vnp.requestData['vnp_Amount'])

        # Build URL
        payment_url = vnp.get_payment_url(settings.VNP_URL, settings.VNP_HASH_SECRET)

        # In log URL
        print(">>> Payment URL built:", payment_url)

        print(">>> [DEBUG] VNP_TMN_CODE:", settings.VNP_TMN_CODE)
        print(">>> [DEBUG] VNP_HASH_SECRET length:", len(settings.VNP_HASH_SECRET))
        print(">>> [DEBUG] VNP_URL:", settings.VNP_URL)
        print(">>> [DEBUG] VNP_RETURN_URL:", settings.VNP_RETURN_URL)
        print(">>> [DEBUG] VNP_IPN_URL:", settings.VNP_IPN_URL)

        return Response({"payment_url": payment_url})

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def fake_payment(self, request, pk=None):
        booking = self.get_object()
        booking.status = "paid"
        booking.qr_code = generate_qr_code(f"Booking:{booking.id}")
        booking.save()
        send_booking_email_brevo(booking.user.email, "Xac nhan dat ve", "Cam on ban da dat ve...")
        return Response({"detail": "Fake payment success"})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def paypal_create(self, request, pk=None):
        booking = self.get_object()

        if booking.status != "pending":
            return Response({"detail": "Booking khong o trang thai pending"}, status=400)

        # tinh tong VND tu booking.details
        total_vnd = sum([Decimal(d.ticket.price) * d.quantity for d in booking.details.all()])
        print(">>> [DEBUG] total_amount (VND):", total_vnd)

        # doi sang USD (26000 VND = 1 USD)
        rate = Decimal(getattr(settings, "EXCHANGE_RATE_VND_TO_USD", "26000"))
        total_usd = (total_vnd / rate).quantize(Decimal("0.01"))
        print(">>> [DEBUG] total_amount (USD):", total_usd, "rate:", rate)

        paypal = PayPalClient()
        order = paypal.create_order(total_usd, currency="USD")

        order_id = order.get("id")
        approve_link = None
        for link in order.get("links", []):
            if link.get("rel") == "approve":
                approve_link = link.get("href")
                break

        booking.payment_code = order_id
        booking.save()

        print(">>> [PayPal create] booking:", booking.id, "order_id:", order_id)
        print(">>> [PayPal create] approve_link:", approve_link)

        site_domain = getattr(settings, "SITE_DOMAIN", "").rstrip(
            "/") or "https://eventapp-production-bcaa.up.railway.app"

        return_url = f"{site_domain}/api/paypal_return/{booking.id}/"
        cancel_url = f"{site_domain}/api/paypal_cancel/{booking.id}/"

        order = paypal.create_order(total_usd, currency="USD", return_url=return_url, cancel_url=cancel_url)

        return Response({
            "orderID": order_id,
            "approve_url": approve_link,
            "amount_usd": f"{total_usd:.2f}"
        })

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def paypal_capture(self, request, pk=None):
        booking = self.get_object()
        order_id = request.data.get("orderID")

        if not order_id:
            return Response({"detail": "orderID is required"}, status=400)

        paypal = PayPalClient()
        try:
            capture_resp = paypal.capture_order(order_id)
        except Exception as e:
            print(">>> [PayPal capture] error:", str(e))
            return Response({"detail": "Error capturing order", "error": str(e)}, status=500)

        print(">>> [PayPal capture] booking:", booking.id, "resp:", capture_resp)

        status_val = capture_resp.get("status", "")
        if status_val.upper() == "COMPLETED" or any(
                pu.get("payments", {}).get("captures", [{}])[0].get("status", "").upper() == "COMPLETED"
                for pu in capture_resp.get("purchase_units", [])
        ):
            booking.status = "paid"
            booking.payment_code = order_id
            booking.save()
            print(f">>> [Booking {booking.id}] marked as paid")

        return Response({"capture": capture_resp})


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
logger = logging.getLogger(__name__)
class EventReviewViewSet(viewsets.ModelViewSet):
    queryset = EventReview.objects.all().order_by('created_at')
    serializer_class = EventReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Nếu có truyền event_id → lọc theo sự kiện
        event_id = self.request.query_params.get('event_id')
        if event_id:
            return EventReview.objects.filter(event_id=event_id).order_by('created_at')
        return EventReview.objects.all().order_by('created_at')

    def perform_create(self, serializer):
        user = self.request.user
        event = serializer.validated_data['event']

        # Kiểm tra xem người dùng đã có vé đã thanh toán cho sự kiện này chưa
        has_booking = Booking.objects.filter(
            user=user,
            details__ticket__event=event,
            status='paid'
        ).exists()

        logger.info(f"Debug: User={user.id}, Event={event.id}, Has Booking={has_booking}")

        # Nếu không có vé, ném ra lỗi PermissionDenied
        if not has_booking:
            raise PermissionDenied({
                "detail": "Bạn cần đặt vé hoặc tham gia sự kiện trước khi bình luận. Vui lòng kiểm tra và thử lại!",
                "requires_booking": True
            })

        # Nếu có vé, lưu bình luận và gán người dùng
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
        # Update dùng details filter paid
        details = BookingDetail.objects.filter(booking__status='paid')
        monthly_data = (
            details.annotate(month=TruncMonth('booking__created_at'))
            .values('month')
            .annotate(
                total_participants=Sum('quantity'),  # Số vé tham gia
                total_revenue=Sum('ticket__price' * 'quantity')  # Doanh thu đúng
            )
            .order_by('month')
        )

        # Trả về thống kê toàn hệ thống
        return Response({
            'total_events': Event.objects.count(),  # Tổng số sự kiện
            'monthly_stats': monthly_data  # Dữ liệu theo tháng
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

    # ✅ log toàn bộ tham số VNPAY gửi về để debug
    print(">>> [VNPAY IPN] raw params:", inputData)

    vnp = vnpay()
    vnp.responseData = inputData

    # validate chữ ký
    is_valid = vnp.validate_response(settings.VNP_HASH_SECRET)
    print(">>> [VNPAY IPN] validate result:", is_valid)

    if not is_valid:
        print(">>> [VNPAY IPN] ❌ Invalid signature")
        return JsonResponse({"RspCode": "97", "Message": "Invalid signature"})

    # Lấy booking_id từ OrderInfo
    booking_id = inputData.get("vnp_OrderInfo", "").replace("Thanh toan booking ", "").strip()
    print(">>> [VNPAY IPN] booking_id parsed:", booking_id)

    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        print(">>> [VNPAY IPN] ❌ Booking not found:", booking_id)
        return JsonResponse({"RspCode": "01", "Message": "Booking not found"})

    response_code = inputData.get("vnp_ResponseCode")
    print(f">>> [VNPAY IPN] Booking {booking_id} - ResponseCode: {response_code}")

    if response_code == "00":
        if booking.status == "paid":
            print(f">>> [VNPAY IPN] ⚠️ Booking {booking_id} already PAID")
            return JsonResponse({"RspCode": "02", "Message": "Booking already paid"})

        # Update status
        booking.status = "paid"
        booking.payment_code = inputData.get("vnp_TransactionNo")
        booking.qr_code = generate_qr_code(f"Booking:{booking.id}")
        booking.save()

        print(f">>> [VNPAY IPN] ✅ Booking {booking_id} updated to PAID")

        # Gửi email xác nhận
        try:
            send_booking_email_brevo(
                booking.user.email,
                "Xác nhận đặt vé",
                "Cảm ơn bạn đã đặt vé..."
            )
            print(f">>> [VNPAY IPN] 📧 Email sent to {booking.user.email}")
        except Exception as e:
            print(">>> [VNPAY IPN] ⚠️ Lỗi gửi mail:", str(e))

        return JsonResponse({"RspCode": "00", "Message": "Confirm Success"})
    else:
        booking.status = "cancelled"
        booking.save()
        print(f">>> [VNPAY IPN] ❌ Booking {booking_id} updated to CANCELLED")
        return JsonResponse({"RspCode": "00", "Message": "Payment failed"})

@csrf_exempt
def vnpay_return(request):
    inputData = request.GET.dict()

    # ✅ Log toàn bộ tham số VNPAY gửi về
    print(">>> [VNPAY RETURN] raw params:", inputData)

    vnp = vnpay()
    vnp.responseData = inputData

    # validate chữ ký
    is_valid = vnp.validate_response(settings.VNP_HASH_SECRET)
    print(">>> [VNPAY RETURN] validate result:", is_valid)

    if not is_valid:
        print(">>> [VNPAY RETURN] ❌ Chữ ký không hợp lệ")
        return HttpResponse("Chữ ký không hợp lệ")

    booking_id = inputData.get("vnp_OrderInfo", "").replace("Thanh toan booking ", "").strip()
    print(">>> [VNPAY RETURN] booking_id parsed:", booking_id)

    try:
        booking = Booking.objects.get(id=booking_id)
    except Booking.DoesNotExist:
        print(">>> [VNPAY RETURN] ❌ Booking không tồn tại:", booking_id)
        return HttpResponse("Booking không tồn tại")

    response_code = inputData.get("vnp_ResponseCode")
    print(f">>> [VNPAY RETURN] Booking {booking_id} - ResponseCode: {response_code}")

    if response_code == "00":
        if booking.status != "paid":
            booking.status = "paid"
            booking.payment_code = inputData.get("vnp_TransactionNo")
            booking.qr_code = generate_qr_code(f"Booking:{booking.id}")
            booking.save()

            print(f">>> [VNPAY RETURN] ✅ Booking {booking_id} updated to PAID")

            # Gửi mail xác nhận
            try:
                send_booking_email_brevo(
                    booking.user.email,
                    "Xác nhận đặt vé",
                    "Cảm ơn bạn đã đặt vé..."
                )
                print(f">>> [VNPAY RETURN] 📧 Email sent to {booking.user.email}")
            except Exception as e:
                print(">>> [VNPAY RETURN] ⚠️ Gửi mail lỗi:", str(e))

        return HttpResponse("Thanh toán thành công!")
    else:
        booking.status = "cancelled"
        booking.save()
        print(f">>> [VNPAY RETURN] ❌ Booking {booking_id} updated to CANCELLED")
        return HttpResponse("Thanh toán thất bại!")


# endpoint public config cho frontend
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def paypal_config(request):
    return Response({
        "PAYPAL_CLIENT_ID": settings.PAYPAL_CLIENT_ID,
        "PAYPAL_MODE": getattr(settings, "PAYPAL_MODE", "sandbox")
    })


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def paypal_return(request, booking_id):
    """
    Endpoint PayPal redirect khi thanh toan thanh cong
    PayPal se goi ve return_url ma ta truyen vao create_order
    """
    print(">>> [PayPal return] booking_id:", booking_id, "params:", request.query_params)

    # Lay orderID tu query neu co
    order_id = request.query_params.get("token") or request.query_params.get("orderID")
    booking = get_object_or_404(Booking, pk=booking_id)

    if order_id:
        paypal = PayPalClient()
        try:
            capture_resp = paypal.capture_order(order_id)
            status_val = capture_resp.get("status", "")
            if status_val.upper() == "COMPLETED" or any(
                pu.get("payments", {}).get("captures", [{}])[0].get("status", "").upper() == "COMPLETED"
                for pu in capture_resp.get("purchase_units", [])
            ):
                booking.status = "paid"
                booking.payment_code = order_id
                booking.save()
                print(f">>> [Booking {booking.id}] marked as paid by PayPal return")
        except Exception as e:
            print(">>> [PayPal return] capture error:", str(e))

    # Dieu huong ve frontend
    frontend_url = f"{settings.SITE_DOMAIN}/payment/result?status=success&bookingId={booking.id}&message=PayPal%20payment%20success"
    return redirect(frontend_url)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def paypal_cancel(request, booking_id):
    """
    Endpoint PayPal redirect khi user cancel thanh toan
    """
    print(">>> [PayPal cancel] booking_id:", booking_id, "params:", request.query_params)

    booking = get_object_or_404(Booking, pk=booking_id)

    # Khong doi booking.status, chi dieu huong ve frontend
    frontend_url = f"{settings.SITE_DOMAIN}/payment/result?status=failed&bookingId={booking.id}&message=PayPal%20payment%20cancelled"
    return redirect(frontend_url)
