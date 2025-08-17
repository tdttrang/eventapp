# events/tasks.py
import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Event, Booking, Notification
from django.db import connections


# Tao logger rieng cho app events
logger = logging.getLogger(__name__)

@shared_task
def send_event_reminders():
    # Đóng tất cả các kết nối database cũ
    #connections.close_all()
    # Lay thoi gian hien tai
    now = timezone.now()

    # Xac dinh khoang thoi gian [24h, 25h) nua
    reminder_start = now + timedelta(hours=24)
    reminder_end = now + timedelta(hours=25)


    # Lay cac su kien sap dien ra trong khoang thoi gian tren
    events = Event.objects.filter(date__gte=reminder_start, date__lt=reminder_end)

    for event in events:
        # Tim cac booking da thanh toan cua su kien nay
        bookings = Booking.objects.filter(ticket__event=event, status="paid").select_related("user")

        for booking in bookings:
            user = booking.user
            if not user.email:  # neu khong co email thi bo qua
                continue

            # Kiem tra neu da gui thong bao reminder cho user nay roi thi bo qua
            already_sent = Notification.objects.filter(
                user=user,
                notification_type="reminder",
                related_object_id=event.id
            ).exists()

            if already_sent:
                continue

            subject = f"Nhắc nhở tham gia sự kiện: {event.name}"
            message = (
                f"Xin chào {user.username},\n\n"
                f"Sự kiện '{event.name}' bạn đã đặt vé sẽ diễn ra vào "
                f"{timezone.localtime(event.date).strftime('%d/%m/%Y %H:%M')} tại {event.location}.\n\n"
                f"Hẹn gặp bạn tại sự kiện!\n\n"
                f"Trân trọng,\nEventApp"
            )
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@eventapp.com")

            # gui mail
            send_mail(
                subject,
                message,
                from_email,
                [user.email],
                fail_silently=False,
            )

            # Log thanh cong
            logger.info(f"Da gui reminder: User {user.username} <{user.email}> - Event {event.name}")

            # Luu thong tin da gui vao Notification de tranh gui lai
            Notification.objects.create(
                user=user,
                notification_type="reminder",
                subject=subject,
                message=message,
                related_object_id=event.id,
                is_read=False
            )
