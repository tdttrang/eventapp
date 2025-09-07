from .models import Notification, BookingDetail
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import qrcode
from cloudinary.uploader import upload
import os
from io import BytesIO
import matplotlib
matplotlib.use('Agg') # su dung backend kh can display
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from django.utils import timezone
from django.db.models import Sum, F, ExpressionWrapper, DecimalField


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

def generate_event_report_pdf(event, from_date=None, to_date=None):
    # 1) lay du lieu thong ke tu DB (booking da 'paid')
    details = BookingDetail.objects.filter(ticket__event=event, booking__status='paid')

    if from_date:
        details = details.filter(booking__created_at__date__gte=from_date)
    if to_date:
        details = details.filter(booking__created_at__date__lte=to_date)

    # Tinh revenue tren tung dong: price * quantity
    revenue_expr = ExpressionWrapper(F('ticket__price') * F('quantity'),
                                     output_field=DecimalField(max_digits=12, decimal_places=2))
    # .aggregate(..): tinh tong tren toan bo queryset
    totals = details.aggregate(
        tickets_sold=Sum('quantity'), # tong so luong ve
        revenue=Sum(revenue_expr) # tong doanh thu
    )

    tickets_sold = totals.get('tickets_sold') or 0
    revenue = float(totals.get('revenue') or 0)

    # 2) Tao series theo ngay de ve bieu do (group by ngay)
    # Lay data theo ngay
    from django.db.models.functions import TruncDay
    #
    series_qs = details.annotate(day=TruncDay('booking__created_at')) \
        .values('day') \
        .annotate(tickets=Sum('quantity'), # annotate: them cot tam 'day' để group theo ngay tao booking
                  revenue=Sum(revenue_expr)) \
        .order_by('day')

    dates = []
    tickets_series = []
    revenue_series = []
    for row in series_qs:
        # Lay ngay tu truong 'day' va chuyen sang chuoi ISO (YYYY-MM-DD)
        dates.append(row['day'].date().isoformat())
        tickets_series.append(int(row['tickets'] or 0))
        revenue_series.append(float(row['revenue'] or 0))

    # 3) Ve bieu do bang matplotlib (tickets per day)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(dates, tickets_series)
    ax.set_title(f"Tickets sold per day - {event.name}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Tickets sold")
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    img_buffer = BytesIO()
    plt.savefig(img_buffer, format='png')
    plt.close(fig)
    img_buffer.seek(0)

    # 4) Tao PDF va chen thong tin + bieu do
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    width, height = A4

    # header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, height - 60, f"EventApp - Report for: {event.name}")

    # metadata: date range + totals
    c.setFont("Helvetica", 11)
    y = height - 90
    c.drawString(40, y, f"Report generated: {timezone.now().isoformat()}")
    y -= 18
    if from_date or to_date:
        c.drawString(40, y, f"Date range: {from_date or 'all'}  -  {to_date or 'all'}")
        y -= 18

    c.drawString(40, y, f"Total tickets sold: {tickets_sold}")
    y -= 16
    c.drawString(40, y, f"Total revenue (VND): {int(revenue)}")
    y -= 30

    # draw chart image
    img = ImageReader(img_buffer)
    img_w = width - 80
    img_h = 250
    c.drawImage(img, 40, y - img_h, width=img_w, height=img_h)
    y = y - img_h - 30

    # footer / note
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(40, 40, "Generated by EventApp")

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer