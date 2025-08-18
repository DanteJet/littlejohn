from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Создает группы Admin и Parent'

    def handle(self, *args, **options):
        Group.objects.get_or_create(name='Admin')
        Group.objects.get_or_create(name='Parent')
        Group.objects.get_or_create(name='Student')
        self.stdout.write(self.style.SUCCESS('Группы инициализированы'))