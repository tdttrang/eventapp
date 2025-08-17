from .models import Notification
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import qrcode
from cloudinary.uploader import upload


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
    configuration.api_key['api-key'] = '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'

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
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img.save('qr_code.png')
    response = upload('qr_code.png', resource_type='image')
    return response['public_id']