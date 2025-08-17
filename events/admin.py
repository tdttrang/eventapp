from django.contrib import admin

# Register your models here.
from .models import User, Event, EventReview, EventReviewReply, Ticket, Booking, Notification

admin.site.register(User)
admin.site.register(Event)
admin.site.register(EventReview)
admin.site.register(EventReviewReply)
admin.site.register(Ticket)
admin.site.register(Booking)
admin.site.register(Notification)