# Import các thư viện cần thiết từ Django Rest Framework
from rest_framework import serializers
from django.db import models
from .models import (
    User, Event, EventReview, EventReviewReply,
    Ticket, Booking, Notification
)
import qrcode
from io import BytesIO
from cloudinary.uploader import upload


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
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            password=validated_data['password']
        )
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
# -----------------------
class TicketSerializer(serializers.ModelSerializer):
    available_quantity = serializers.SerializerMethodField()
    class Meta:
        model = Ticket
        fields = ['id', 'event', 'price', 'quantity', 'ticket_class', 'available_quantity' ]

    def get_available_quantity(self, obj):
        total_booked = obj.booking_set.aggregate(total=models.Sum('quantity'))['total'] or 0
        return obj.quantity - total_booked

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


# -----------------------
# 6. BookingSerializer
# Dùng để hiển thị thông tin đặt vé của người dùng.
# Bao gồm thông tin vé, số lượng, trạng thái và mã QR.
# -----------------------
class BookingSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    ticket = TicketSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'user', 'ticket', 'quantity', 'status',
            'created_at', 'expires_at', 'qr_code'
        ]



class BookingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['ticket', 'quantity']

    def validate(self, data):
        total_booked = data['ticket'].booking_set.aggregate(total=models.Sum('quantity'))['total'] or 0
        available = data['ticket'].quantity - total_booked
        if data['quantity'] > available:
            raise serializers.ValidationError("Không đủ vé.")
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        booking = Booking.objects.create(user=user, **validated_data)

        # Tạo QR code
        qr = qrcode.make(f"Booking ID: {booking.id} - User: {user.username}")
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        # Upload lên Cloudinary
        result = upload(buffer, folder="qr_codes")
        booking.qr_code = result['secure_url']
        booking.save()

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