
from django.utils import timezone

from .models import Child

def user_roles(request):
    user = request.user
    is_admin = user.is_authenticated and (
        user.is_staff or user.groups.filter(name="Admin").exists()
    )
    is_parent = (
        user.is_authenticated
        and user.groups.filter(name="Parent").exists()
        and not is_admin
    )
    is_student = (
        user.is_authenticated
        and user.groups.filter(name="Student").exists()
        and not (is_admin or is_parent)
    )
    return {"IS_ADMIN": is_admin, "IS_PARENT": is_parent, "IS_STUDENT": is_student}

def upcoming_birthdays(request):
    upcoming = []
    user = request.user
    if user.is_authenticated and (
        user.is_staff or user.groups.filter(name="Admin").exists()
    ):
        today = timezone.localdate()
        for child in Child.objects.filter(birth_date__isnull=False):
            bd = child.birth_date.replace(year=today.year)
            if bd < today:
                bd = bd.replace(year=today.year + 1)
            days_left = (bd - today).days
            if 0 <= days_left <= 3:
                upcoming.append({"child": child, "date": bd, "days_left": days_left})
        upcoming.sort(key=lambda x: x["date"])
    return {"upcoming_birthdays": upcoming}
