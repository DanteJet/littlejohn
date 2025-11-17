from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class Child(models.Model):
    GENDER_CHOICES = (('M', 'Мальчик'), ('F', 'Девочка'), ('U', 'Не указано'))

    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='children', null=True, blank=True)  # для ребёнка
    is_adult = models.BooleanField(default=False, verbose_name='Взрослый')  # если взрослый
    account_user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='student_profile', verbose_name='Аккаунт взрослого')

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='U')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['first_name', 'last_name']
        verbose_name = 'Ученик'
        verbose_name_plural = 'Ученики'

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()

class SubscriptionType(models.Model):
    name = models.CharField(max_length=100)
    lessons_count = models.PositiveIntegerField(default=8)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'Тип абонемента'
        verbose_name_plural = 'Типы абонементов'

    def __str__(self):
        return f"{self.name} ({self.lessons_count} занятий)"

class Subscription(models.Model):
    child = models.OneToOneField(Child, on_delete=models.CASCADE, related_name='subscription')
    sub_type = models.ForeignKey(SubscriptionType, on_delete=models.PROTECT)
    lessons_remaining = models.PositiveIntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Абонемент'
        verbose_name_plural = 'Абонементы'

    def __str__(self):
        status = 'оплачен' if self.paid else 'не оплачен'
        return f"{self.child} — {self.sub_type} | Остаток: {self.lessons_remaining} | {status}"

    @property
    def total_lessons(self):
        return self.sub_type.lessons_count

    @property
    def used_lessons(self):
        return max(0, self.total_lessons - self.lessons_remaining)

    def mark_paid(self):
        """Отмечает абонемент как оплаченный и пополняет счётчик при необходимости."""
        updated_fields = {'paid'}
        if self.lessons_remaining == 0:
            total = self.total_lessons or 0
            if total:
                self.lessons_remaining = total
                updated_fields.add('lessons_remaining')
        self.paid = True
        self.save(update_fields=sorted(updated_fields))

    def add_visit(self):
        """Засчитывает одно посещение и корректирует статус оплаты."""
        updated_fields = set()

        if self.lessons_remaining > 0:
            self.lessons_remaining -= 1
            updated_fields.add('lessons_remaining')
            if self.lessons_remaining == 0 and self.paid:
                self.paid = False
                updated_fields.add('paid')
        else:
            # Начинаем новый цикл абонемента: фиксируем посещение и восстанавливаем
            # счётчик, будто это первое занятие в новом абонементе.
            total_lessons = self.total_lessons
            if total_lessons:
                self.lessons_remaining = max(total_lessons - 1, 0)
            else:
                self.lessons_remaining = 0
            updated_fields.add('lessons_remaining')
            if self.paid:
                self.paid = False
                updated_fields.add('paid')

        if updated_fields:
            self.save(update_fields=sorted(updated_fields))
        return True

class TrainingSession(models.Model):
    start = models.DateTimeField(default=timezone.now)
    duration_minutes = models.PositiveIntegerField(default=60)
    participants = models.ManyToManyField(Child, related_name='sessions', blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['start']
        verbose_name = 'Занятие'
        verbose_name_plural = 'Занятия'

    def __str__(self):
        return f"Занятие {self.start:%d.%m.%Y %H:%M} — {self.end:%H:%M}"

    @property
    def end(self):
        return self.start + timedelta(minutes=self.duration_minutes)


class Visit(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='visits', verbose_name='Ученик')
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата посещения')
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_visits',
        verbose_name='Отметил',
    )

    class Meta:
        ordering = ['-recorded_at']
        verbose_name = 'Посещение'
        verbose_name_plural = 'Посещения'

    def __str__(self):
        return f"Посещение {self.child} от {self.recorded_at:%d.%m.%Y %H:%M}"
