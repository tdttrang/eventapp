from django.db import models

# Create your models here.
from cloudinary.models import CloudinaryField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta


# -----------------------
# 1. User (Nguoi dung)
# -----------------------
class User(AbstractUser):
    # Avatar nguoi dung, luu tren Cloudinary
    avatar = CloudinaryField("avatar", null=True, blank=True)

    # Vai tro nguoi dung: attendee (nguoi tham gia), organizer (nha to chuc), admin (quan tri vien)
    ROLE_CHOICES = [
        ("attendee", "Nguoi tham gia"),
        ("organizer", "Nha to chuc"),
        ("admin", "Quan tri vien"),
    ]
    role = models.CharField(max_length=20, choices=[('organizer', 'Organizer'), ('attendee', 'Attendee')])
    # Trang thai duyet doi voi nha to chuc (organizer)
    is_approved = models.BooleanField(default=False)

    # Ham kiem tra neu la organizer va da duoc duyet
    def is_organizer(self):
        return self.role == "organizer" and self.is_approved

    # Ham kiem tra neu la attendee
    def is_attendee(self):
        return self.role == "attendee"

    # Ham kiem tra neu la admin
    def is_admin(self):
        return self.role == "admin"

    def __str__(self):
        return f"{self.username} ({self.role})"


# -----------------------
# 2. Event (Su kien)
# -----------------------
class Event(models.Model):
    # Ten su kien
    name = models.CharField(max_length=255)

    # Mo ta chi tiet
    description = models.TextField()

    # Ngay gio to chuc
    date = models.DateTimeField(null=True)

    # Dia diem
    location = models.CharField(max_length=255)

    # So luong toi da nguoi tham gia
    capacity = models.IntegerField(default=100)

    # Nguoi to chuc (FK toi User)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)

    # Luu link anh hoac video gioi thieu su kien tren Cloudinary
    media = CloudinaryField("event_media", null=True, blank=True)

    # The loai su kien (khong tach bang rieng)
    category = models.CharField(max_length=100)

    # Gia ve thuong
    ticket_price_regular = models.DecimalField(max_digits=10, decimal_places=2, default=100000)

    # Gia ve VIP
    ticket_price_vip = models.DecimalField(max_digits=10, decimal_places=2, default=500000)

    # Thoi gian tao & cap nhat
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(reviews.aggregate(models.Avg('rating'))['rating__avg'], 1)
        return None


# -----------------------
# 3. Event Review (Danh gia su kien)
# -----------------------
class EventReview(models.Model):
    # Nguoi viet danh gia
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Su kien duoc danh gia
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews')

    # Diem danh gia (1-5)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    # Binh luan
    comment = models.TextField(blank=True, null=True)

    # Ngay tao
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Moi nguoi dung chi duoc danh gia 1 lan tren moi su kien
        unique_together = ('user', 'event')

    def __str__(self):
        return f"Review cua {self.user.username} cho {self.event.name}"


# -----------------------
# 4. Event Review Reply (Phan hoi danh gia)
# -----------------------
class EventReviewReply(models.Model):
    # Nguoi phan hoi (thuong la nha to chuc)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Danh gia duoc phan hoi
    review = models.ForeignKey(EventReview, on_delete=models.CASCADE, related_name='replies')

    # Noi dung phan hoi
    reply_text = models.TextField()

    # Ngay tao
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Phan hoi cua {self.user.username} cho review {self.review.id}"


# -----------------------
# 5. Ticket (Ve su kien)
# -----------------------
class Ticket(models.Model):
    # Loai ve: thuong hoac VIP
    TICKET_CHOICES = [
        ("normal", "Ve thuong"),
        ("VIP", "Ve VIP"),
    ]
    # Su kien cua ve
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")

    # Gia ve
    price = models.DecimalField(max_digits=10, decimal_places=2)

    # So luong ve co san
    quantity = models.PositiveIntegerField(default=200)

    # Hang ve
    ticket_class = models.CharField(max_length=10, choices=TICKET_CHOICES, default="normal")

    def __str__(self):
        return f"Ve {self.event.name} - {self.price} VND"


# -----------------------
# 6. Booking (Dat ve)
# -----------------------
class Booking(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled")
    ]
    # Nguoi dat ve
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # Ve duoc dat
    ticket = models.ForeignKey("Ticket", on_delete=models.CASCADE)

    # So luong ve
    quantity = models.PositiveIntegerField()

    # Trang thai don hang
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    # Thoi gian tao
    created_at = models.DateTimeField(auto_now_add=True)

    # Thoi gian het han giu cho (10 phut)
    expires_at = models.DateTimeField(default=timezone.now)

    # Luu link anh QR tren Cloudinary
    qr_code = CloudinaryField("qr_code", null=True, blank=True)

    def save(self, *args, **kwargs):
        # Neu tao moi thi dat thoi gian het han = hien tai + 10 phut
        if not self.pk:
            self.expires_at = timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Booking {self.id} - {self.user.username}"


# -----------------------
# 7. Notification (Thong bao)
# -----------------------
class Notification(models.Model):
    # Nguoi nhan thong bao
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')

    # Loai thong bao (new_event, reminder, review_reply, ...)
    notification_type = models.CharField(max_length=255)

    # Tieu de
    subject = models.CharField(max_length=255)

    # Noi dung
    message = models.TextField()

    # ID cua doi tuong lien quan (Event ID, Booking ID, Review ID)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)

    # Trang thai da doc chua
    is_read = models.BooleanField(default=False)

    # Ngay tao
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} - {self.subject} ({self.user.username})"
