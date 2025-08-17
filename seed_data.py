# seed_events.py
# Vị trí: đặt ở cùng cấp với manage.py
from django.utils import timezone
from django.contrib.auth import get_user_model
from events.models import Event

# 1) Tạo (hoặc lấy) organizer dùng để gán cho tất cả sự kiện
User = get_user_model()
organizer, created = User.objects.get_or_create(
    username="organizer_demo",
    defaults={
        "email": "organizer@example.com",
        "is_staff": True,
        "is_active": True,
    },
)
if created:
    # đặt mật khẩu đúng chuẩn (hash)
    organizer.set_password("123456")
    # nếu User của cậu có các field role/is_approved thì set luôn
    try:
        organizer.role = "organizer"      # nếu không có field này thì bỏ qua
        organizer.is_approved = True      # nếu không có field này thì bỏ qua
    except Exception:
        pass
    organizer.save()

# 2) Danh sách 10 sự kiện mẫu (ngày đều ở tương lai)
events_data = [
    {
        "name": "Hội Chợ Ẩm Thực Quốc Tế",
        "description": "Thưởng thức các món ăn đặc sắc từ khắp nơi trên thế giới.",
        "date": timezone.now() + timezone.timedelta(days=7),
        "location": "Công viên 23/9, TP.HCM",
        "capacity": 800,
        "media": None,  # Có thể thay bằng public_id Cloudinary nếu muốn
        "category": "Ẩm Thực",
        "ticket_price_regular": 50000,
        "ticket_price_vip": 100000,
    },
    {
        "name": "Live Concert Sơn Tùng M-TP",
        "description": "Đêm nhạc bùng nổ với những bản hit đình đám.",
        "date": timezone.now() + timezone.timedelta(days=14),
        "location": "SVĐ Mỹ Đình, Hà Nội",
        "capacity": 20000,
        "media": None,
        "category": "Âm Nhạc",
        "ticket_price_regular": 300000,
        "ticket_price_vip": 800000,
    },
    {
        "name": "Triển Lãm Công Nghệ TechXpo 2025",
        "description": "Cập nhật xu hướng và công nghệ mới nhất trong lĩnh vực AI, IoT.",
        "date": timezone.now() + timezone.timedelta(days=21),
        "location": "SECC, Quận 7, TP.HCM",
        "capacity": 1200,
        "media": None,
        "category": "Công Nghệ",
        "ticket_price_regular": 100000,
        "ticket_price_vip": 200000,
    },
    {
        "name": "Giải Marathon Thành Phố",
        "description": "Sự kiện thể thao cộng đồng với nhiều cự ly cho mọi lứa tuổi.",
        "date": timezone.now() + timezone.timedelta(days=30),
        "location": "Quận 1, TP.HCM",
        "capacity": 5000,
        "media": None,
        "category": "Thể Thao",
        "ticket_price_regular": 150000,
        "ticket_price_vip": 300000,
    },
    {
        "name": "Festival Văn Hóa Nhật Bản",
        "description": "Trải nghiệm ẩm thực, nghệ thuật, cosplay và văn hóa Nhật Bản.",
        "date": timezone.now() + timezone.timedelta(days=10),
        "location": "AEON Mall Tân Phú, TP.HCM",
        "capacity": 2000,
        "media": None,
        "category": "Văn Hóa",
        "ticket_price_regular": 90000,
        "ticket_price_vip": 180000,
    },
    {
        "name": "Đêm Nhạc Trịnh Công Sơn",
        "description": "Những ca khúc bất hủ qua phần trình diễn của nhiều nghệ sĩ.",
        "date": timezone.now() + timezone.timedelta(days=18),
        "location": "Nhà hát Lớn Hà Nội",
        "capacity": 1500,
        "media": None,
        "category": "Âm Nhạc",
        "ticket_price_regular": 200000,
        "ticket_price_vip": 400000,
    },
    {
        "name": "Workshop Lập Trình Python",
        "description": "Khóa học nền tảng về Python cho người mới bắt đầu.",
        "date": timezone.now() + timezone.timedelta(days=5),
        "location": "Trung tâm Công nghệ Số, TP.HCM",
        "capacity": 200,
        "media": None,
        "category": "Giáo Dục",
        "ticket_price_regular": 100000,
        "ticket_price_vip": 180000,
    },
    {
        "name": "Liên Hoan Phim Việt Nam",
        "description": "Trình chiếu và vinh danh các tác phẩm điện ảnh xuất sắc.",
        "date": timezone.now() + timezone.timedelta(days=25),
        "location": "CGV Landmark 81, TP.HCM",
        "capacity": 1000,
        "media": None,
        "category": "Phim Ảnh",
        "ticket_price_regular": 150000,
        "ticket_price_vip": 300000,
    },
    {
        "name": "Triển Lãm Mỹ Thuật Đương Đại",
        "description": "Các tác phẩm mới của những nghệ sĩ trẻ tài năng.",
        "date": timezone.now() + timezone.timedelta(days=12),
        "location": "Bảo tàng Mỹ thuật TP.HCM",
        "capacity": 600,
        "media": None,
        "category": "Nghệ Thuật",
        "ticket_price_regular": 70000,
        "ticket_price_vip": 140000,
    },
    {
        "name": "Lễ Hội Ánh Sáng",
        "description": "Không gian ánh sáng nghệ thuật rực rỡ bên bờ hồ.",
        "date": timezone.now() + timezone.timedelta(days=40),
        "location": "Hồ Hoàn Kiếm, Hà Nội",
        "capacity": 3000,
        "media": None,
        "category": "Lễ Hội",
        "ticket_price_regular": 80000,
        "ticket_price_vip": 160000,
    },
]

# 3) Upsert 10 sự kiện (update_or_create để idempotent)
for data in events_data:
    Event.objects.update_or_create(
        name=data["name"],
        defaults={
            "description": data["description"],
            "date": data["date"],
            "location": data["location"],
            "capacity": data["capacity"],
            "organizer": organizer,
            "media": data["media"],
            "category": data["category"],
            "ticket_price_regular": data["ticket_price_regular"],
            "ticket_price_vip": data["ticket_price_vip"],
        },
    )

print("✅ Đã seed 10 sự kiện thành công.")
