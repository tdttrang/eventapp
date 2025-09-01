# Import các thư viện cần thiết từ Django Rest Framework
from rest_framework import serializers
from django.db import models
from .models import (
    User, Event, EventReview, EventReviewReply,
    Ticket, Booking, Notification, BookingDetail
)
import qrcode
from io import BytesIO
from cloudinary.uploader import upload
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta



# -----------------------
# 1. UserSerializer
# Dùng để chuyển đổi dữ liệu người dùng thành JSON.
# Bao gồm thông tin cơ bản như username, email, role, avatar và trạng thái duyệt.
# -----------------------
class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'avatar', 'is_approved']

    def get_avatar(self, obj):
        return str(obj.avatar) if obj.avatar else None


# Dang ky va duyet organizer
class OrganizerRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'avatar']
        extra_kwargs = {
            'password': {'write_only': True},
            'avatar': {'required': False}
        }

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        user.role = 'organizer'
        user.is_approved = False  # Chờ admin duyệt
        user.save()
        return user


# dang ky user
class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        if User.objects.filter(email=validated_data['email']).exists():
            raise serializers.ValidationError({"email": "Email đã được sử dụng"})

        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            password=validated_data['password']
        )
        user.role = "attendee" # mặc định attendee
        user.save()
        return user

# -----------------------
# 2. EventReviewReplySerializer
# Dùng để hiển thị phản hồi của nhà tổ chức cho từng đánh giá sự kiện.
# Nested user giúp hiển thị thông tin người phản hồi.
# -----------------------
class EventReviewReplySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # Chỉ hiển thị, không cho sửa
    review = serializers.PrimaryKeyRelatedField(queryset=EventReview.objects.all())

    class Meta:
        model = EventReviewReply
        fields = ['id', 'user', 'review', 'reply_text', 'created_at']

    def validate(self, data):
        user = self.context['request'].user
        review = data['review']
        if review.event.organizer != user:
            raise serializers.ValidationError("Bạn không phải là nhà tổ chức của sự kiện này.")
        return data


# -----------------------
# 3. EventReviewSerializer
# Dùng để hiển thị đánh giá của người tham gia cho sự kiện.
# Bao gồm cả phản hồi từ nhà tổ chức (replies).
# -----------------------
class EventReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    replies = EventReviewReplySerializer(many=True, read_only=True)

    class Meta:
        model = EventReview
        fields = ['id', 'user', 'rating', 'comment', 'created_at', 'replies']


# -----------------------
# 4. TicketSerializer
# Dùng để hiển thị thông tin vé của sự kiện.
# Bao gồm loại vé, giá và số lượng còn lại.
# TicketSerializer (fix available_quantity: lọc status)
# -----------------------
class TicketSerializer(serializers.ModelSerializer):
    available_quantity = serializers.SerializerMethodField()
    class Meta:
        model = Ticket
        fields = ['id', 'event', 'price', 'quantity', 'ticket_class', 'available_quantity' ]

    def get_available_quantity(self, obj):
        # Tính tổng booked từ BookingDetail, chỉ tính booking pending hoặc paid (không tính cancelled)
        total_booked = BookingDetail.objects.filter(
            ticket=obj,
            booking__status__in=['pending', 'paid']
        ).aggregate(total=Sum('quantity'))['total'] or 0
        return obj.quantity - total_booked  # quantity gốc không thay đổi

# -----------------------
# 5. EventSerializer
# Dùng để hiển thị thông tin chi tiết của sự kiện.
# Bao gồm organizer, danh sách vé và danh sách đánh giá.
# -----------------------
class EventSerializer(serializers.ModelSerializer):
    organizer = UserSerializer(read_only=True)
    reviews = EventReviewSerializer(many=True, read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'name', 'description', 'date', 'location', 'capacity',
            'organizer', 'media', 'category', 'ticket_price_regular',
            'ticket_price_vip', 'created_at', 'updated_at', 'reviews',
            'tickets',  'average_rating'
        ]
        extra_kwargs = {
            'organizer': {'read_only': True},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
        }

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if reviews.exists():
            return round(sum([r.rating for r in reviews]) / reviews.count(), 1)
        return None

# -----------------------
# EvenCreateSerializer
# Dùng để tao su kien
# -----------------------
class EventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            'name', 'description', 'date', 'location', 'capacity',
            'media', 'category', 'ticket_price_regular', 'ticket_price_vip'
        ]

    def validate(self, data):
        user = self.context['request'].user
        if not user.is_organizer():
            raise serializers.ValidationError("Bạn không có quyền tạo sự kiện.")
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        return Event.objects.create(organizer=user, **validated_data)

# Serializer cho chi tiết vé
class BookingDetailSerializer(serializers.ModelSerializer):
    ticket_class = serializers.CharField(source="ticket.ticket_class", read_only=True)
    price = serializers.DecimalField(source="ticket.price", read_only=True, max_digits=10, decimal_places=2)

    class Meta:
        model = BookingDetail
        fields = ["id", "ticket", "ticket_class", "price", "quantity"]


# -----------------------
# 6. BookingSerializer
# Serializer cho Booking (dùng khi đọc booking)
# -----------------------
class BookingSerializer(serializers.ModelSerializer):
    details = BookingDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "user", "status", "created_at", "expires_at", "qr_code", "payment_code", "details"]


# Serializer khi tạo booking (bỏ trừ trực tiếp, thêm validate tồn kho)
class BookingCreateSerializer(serializers.Serializer):
    tickets = serializers.ListField(
        child=serializers.DictField(
            child=serializers.IntegerField(),  # mỗi dict sẽ có ticket_id và quantity
        )
    )

    def validate(self, data):
        for item in data["tickets"]:
            ticket_id = item.get("ticket_id")
            qty = item.get("quantity", 1)
            if qty <= 0:
                raise serializers.ValidationError("Số lượng phải lớn hơn 0")
            try:
                ticket = Ticket.objects.get(id=ticket_id)
            except Ticket.DoesNotExist:
                raise serializers.ValidationError(f"Ticket {ticket_id} không tồn tại")

            # Tính available động (tương tự TicketSerializer)
            total_booked = BookingDetail.objects.filter(
                ticket=ticket,
                booking__status__in=['pending', 'paid']
            ).aggregate(total=Sum('quantity'))['total'] or 0
            available = ticket.quantity - total_booked

            if available < qty:
                raise serializers.ValidationError(f"Không đủ vé cho loại {ticket.ticket_class}. Còn lại: {available}")

            # Kiểm tra event chưa diễn ra (tương tự code cũ)
            if ticket.event.date <= timezone.now():
                raise serializers.ValidationError("Không thể đặt vé cho sự kiện đã diễn ra.")

        return data

    def create(self, validated_data):
        user = self.context["request"].user
        booking = Booking.objects.create(
            user=user,
            status='pending',
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        for item in validated_data["tickets"]:
            ticket_id = item.get("ticket_id")
            qty = item.get("quantity", 1)
            ticket = Ticket.objects.get(id=ticket_id)
            # KHÔNG trừ ticket.quantity nữa! Available sẽ tự cập nhật từ query
            BookingDetail.objects.create(booking=booking, ticket=ticket, quantity=qty)

        return booking


# -----------------------
# 7. NotificationSerializer
# Dùng để hiển thị thông báo gửi đến người dùng.
# Bao gồm loại thông báo, nội dung, trạng thái đã đọc và thời gian tạo.
# -----------------------
class NotificationSerializer(serializers.ModelSerializer):
    # Hiển thị thông tin người nhận thông báo (dưới dạng nested user)
    user = UserSerializer(read_only=True)

    # Trường bổ sung để hiển thị tên đối tượng liên quan (ví dụ: tên sự kiện)
    related_object_display = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',                 # ID của thông báo
            'user',               # Người nhận thông báo
            'notification_type',  # Loại thông báo (new_event, review_reply, ...)
            'subject',            # Tiêu đề thông báo
            'message',            # Nội dung chi tiết
            'related_object_id',  # ID của đối tượng liên quan (Event, Booking, Review...)
            'related_object_display',  # Tên hoặc mô tả đối tượng liên quan
            'is_read',            # Trạng thái đã đọc hay chưa
            'created_at'          # Thời gian tạo thông báo
        ]

    def get_related_object_display(self, obj):
        """
        Hàm này dùng để lấy tên hoặc mô tả của đối tượng liên quan đến thông báo.
        Tuỳ theo loại thông báo, ta truy vấn model tương ứng để lấy thông tin hiển thị.
        """
        if obj.notification_type == "new_event":
            try:
                event = Event.objects.get(id=obj.related_object_id)
                return event.name  # Trả về tên sự kiện
            except Event.DoesNotExist:
                return None
        elif obj.notification_type == "review_reply":
            try:
                review = EventReview.objects.get(id=obj.related_object_id)
                return f"Review của {review.user.username} cho {review.event.name}"
            except EventReview.DoesNotExist:
                return None
        # Có thể mở rộng thêm các loại khác như "booking", "reminder", v.v.
        return None


# firebase login
class FirebaseLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()