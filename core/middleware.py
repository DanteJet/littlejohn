from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    """Перенаправляет на смену пароля, если она обязательна."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get('force_password_change'):
            allowed = {
                reverse('password_change'),
                reverse('password_change_done'),
                reverse('logout'),
            }
            static_url = '/' + settings.STATIC_URL.lstrip('/')
            if request.path not in allowed and not request.path.startswith(static_url):
                return redirect('password_change')
        return self.get_response(request)
