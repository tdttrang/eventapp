from rest_framework import serializers
from .models import (
    User, Event, EventReview, EventReviewReply,
    Ticket, Booking, Notification, BookingDetail
)
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
import cloudinary.uploader
import json



# -----------------------
# 1. UserSerializer
# Dùng để chuyển đổi dữ liệu người dùng thành JSON.
# Bao gồm thông tin cơ bản như username, email, role, avatar và trạng thái duyệt.
# -----------------------
class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'avatar', 'is_approved']
        read_only_fields = ['id', 'role', 'is_approved']

    def to_representation(self, instance):
        """Trả về URL Cloudinary đầy đủ và chính xác"""
        data = super().to_representation(instance)
        # Dùng .url để đảm bảo có URL tuyệt đối
        data['avatar'] = instance.avatar.url if instance.avatar else None
        return data

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

class OrganizerPendingSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'avatar']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['avatar'] = instance.avatar.url if instance.avatar else None
        return data

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

    # field event: để xử lý input ID của event khi tạo review, query dùng validate event tồn tại
    event = serializers.PrimaryKeyRelatedField(queryset=Event.objects.all(), write_only=True)

    class Meta:
        model = EventReview
        fields = ['id', 'event', 'user', 'rating', 'comment', 'created_at', 'replies']

# hiển thị thông tin cần thiết của event bên trong ticket
class EventInTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        # Chỉ lấy các trường mà frontend cần để hiển thị trong card vé
        fields = ['id', 'name', 'date', 'location', 'media']

# -----------------------
# 4. TicketSerializer
# Dùng để hiển thị thông tin vé của sự kiện.
# Bao gồm loại vé, giá và số lượng còn lại.
# TicketSerializer (fix available_quantity: lọc status)
# -----------------------
class TicketSerializer(serializers.ModelSerializer):
    event = EventInTicketSerializer(read_only=True)
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
    # Trường để nhận chuỗi Json chứa thông tin các loại vé từ FE
    tickets = serializers.CharField(write_only=True)
    media = serializers.ImageField(required=False, write_only=True)

    class Meta:
        model = Event
        fields = [
            'name', 'description', 'date', 'location', 'category',
            'media', 'tickets'
        ]
        read_only_fields = ['id']

    def validate(self, data):
        user = self.context['request'].user
        if not user.is_organizer():
            raise serializers.ValidationError("Bạn không có quyền tạo sự kiện.")
        return data

    def create(self, validated_data):
        # Lấy user từ context, giống như code của bạn
        user = self.context['request'].user

        # Tách dữ liệu tickets ra khỏi dữ liệu chính
        tickets_data_str = validated_data.pop('tickets')

        # Tạo sự kiện với các dữ liệu còn lại và gán organizer
        event = Event.objects.create(organizer=user, **validated_data)

        # Xử lý tạo các object Ticket từ chuỗi JSON
        tickets_data = json.loads(tickets_data_str)
        for ticket_info in tickets_data:
            Ticket.objects.create(
                event=event,
                ticket_class=ticket_info['ticket_class'],
                price=ticket_info['price'],
                quantity=ticket_info['quantity']
            )
        return event

# Serializer cho chi tiết vé
class BookingDetailSerializer(serializers.ModelSerializer):
    ticket = TicketSerializer(read_only=True)

    class Meta:
        model = BookingDetail
        fields = ["id", "ticket", "quantity"]

# -----------------------
# 6. BookingSerializer
# Serializer cho Booking (dùng khi đọc booking)
# -----------------------
class BookingSerializer(serializers.ModelSerializer):
    details = BookingDetailSerializer(many=True, read_only=True)
    qr_code = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "user", "status", "created_at", "expires_at",
                  "qr_code", "payment_code", "details",  "checked_in_at"]

    def get_qr_code(self, booking):
        """
        Hàm này sẽ được gọi tự động để lấy giá trị cho trường qr_code.
        Nó sẽ kiểm tra và trả về public_id một cách an toàn.
        """
        if booking.qr_code and hasattr(booking.qr_code, 'public_id'):
            return booking.qr_code.public_id
        return None

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


# 8. NotificationCreationSerializer
# Dùng cho organizer/admin để tạo thông báo mới
# -----------------------
class NotificationCreationSerializer(serializers.Serializer):
    # Loại đối tượng nhận thông báo: 'all', 'event_attendees', 'specific_users', 'role'
    target_audience = serializers.CharField(max_length=50, default='specific_users')

    # Dữ liệu để lọc theo loại đối tượng
    # Ví dụ: nếu target_audience là 'event_attendees', cần gửi kèm event_id
    filter_data = serializers.JSONField(required=False, default={})

    # Các trường thông tin của thông báo
    subject = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.CharField(max_length=255)
    related_object_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        target = data.get('target_audience')
        filter_data = data.get('filter_data', {})

        if target == 'event_attendees' and 'event_id' not in filter_data:
            raise serializers.ValidationError(
                {"filter_data": "Trường 'event_id' là bắt buộc khi gửi thông báo cho người tham gia sự kiện."}
            )
        return data

# firebase login
class FirebaseLoginSerializer(serializers.Serializer):
    id_token = serializers.CharField()