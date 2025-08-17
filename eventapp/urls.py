from django.contrib import admin
from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="Event Management API",
      default_version='v1',
      description="Tài liệu API cho hệ thống quản lý sự kiện",
      contact=openapi.Contact(email="yoonie@example.com"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
   authentication_classes=[],
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('events.urls')),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),  # 👈 thêm dòng này

]

# id CZy7OJ2lLSstjQ2ZDjTa5uesQ0nMfjBScorujxEc
# secret R0S1BR5aUTturGZwfpM9dZsL8JXD3wWg973yzSqvFagnwvxCZJKOayd4QLZkihivSKg1fUtTkrdtr5Z14EtzREHoKQbgrVx85V4XkB6MMVVGPeVuTvcPiHSJCyiVD4RM



