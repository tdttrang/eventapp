from rest_framework import permissions

# -----------------------
# 1. Kiểm tra nếu người dùng là organizer và đã được duyệt
# Dùng cho các hành động tạo/sửa/xóa sự kiện
# -----------------------
class IsApprovedOrganizer(permissions.BasePermission):
    def has_permission(self, request, view):
        # Kiểm tra người dùng đã đăng nhập
        if not request.user.is_authenticated:
            return False
        # Kiểm tra vai trò là organizer và đã được duyệt
        return request.user.role == "organizer" and request.user.is_approved


# -----------------------
# 2. Kiểm tra nếu người dùng là chủ sở hữu của đối tượng
# Dùng cho các hành động sửa/xóa Booking, Review, v.v.
# -----------------------
class IsOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # So sánh người dùng hiện tại với người tạo đối tượng
        return obj.user == request.user


# -----------------------
# 3. Kiểm tra nếu người dùng là admin
# Dùng cho các API quản trị
# -----------------------
class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        # Kiểm tra người dùng đã đăng nhập và có vai trò admin
        return request.user.is_authenticated and request.user.role == "admin"


