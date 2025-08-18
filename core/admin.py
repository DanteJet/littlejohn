from django.contrib import admin
from .models import Child, SubscriptionType, Subscription, TrainingSession

@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "parent", "get_gender_display")  # <-- показываем человекочитаемо
    search_fields = ("first_name", "last_name", "parent__username", "parent__email")

@admin.register(SubscriptionType)
class SubscriptionTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "lessons_count", "price")

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("child", "sub_type", "lessons_remaining", "paid")

@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ("start", "duration_minutes")
    filter_horizontal = ("participants",)