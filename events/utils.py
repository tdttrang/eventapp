from .models import Notification
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import qrcode
from cloudinary.uploader import upload
import os
from io import BytesIO

def create_notification(user, notification_type, subject, message, related_object_id=None):
    """
    Tạo thông báo cho người dùng với đầy đủ thông tin.
    """
    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        subject=subject,
        message=message,
        related_object_id=related_object_id
    )

def send_booking_email_brevo(to_email, subject, message):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = os.getenv('BREVO_API_KEY')

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        sender={"name": "EventApp", "email": "duongtrangthuy147012@gmail.com"},
        subject=subject,
        text_content=message
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
    except ApiException as e:
        print(f"Lỗi gửi email qua Brevo: {e}")


def generate_qr_code(data):
    """
    Tạo mã QR trong bộ nhớ và upload trực tiếp lên Cloudinary.
    """
    # 1. Tạo ảnh QR như bình thường
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    # 2. Tạo một buffer trong bộ nhớ (thay vì lưu file thật)
    buffer = BytesIO()

    # 3. Lưu ảnh vào buffer dưới định dạng PNG
    img.save(buffer, format="PNG")

    # 4. Đưa con trỏ về đầu buffer để chuẩn bị upload
    buffer.seek(0)

    # 5. Upload trực tiếp từ buffer trong bộ nhớ
    response = upload(buffer, resource_type='image')

    # 6. Trả về public_id như cũ
    return response['public_id']