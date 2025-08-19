from datetime import date
from django.test import TestCase
from django.urls import reverse

from django.contrib.auth.models import User
from decimal import Decimal
from .models import SubscriptionType


class CalendarAlignmentTests(TestCase):
    def test_month_view_aligns_days_correctly(self):
        """August 20, 2024 should fall on a Tuesday in the calendar weeks."""
        response = self.client.get(reverse('home'), {'year': 2024, 'month': 8})
        weeks = response.context['weeks']
        self.assertEqual(weeks[3][1], date(2024, 8, 20))


class SubscriptionTypeEditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.type = SubscriptionType.objects.create(name='Basic', lessons_count=8, price=100)

    def test_edit_subscription_type(self):
        self.client.login(username='admin', password='pass')
        url = reverse('subscription_type_edit', args=[self.type.pk])
        response = self.client.post(url, {
            'name': 'Pro',
            'lessons_count': 12,
            'price': '150.00',
        })
        self.assertRedirects(response, reverse('subscription_types'))
        self.type.refresh_from_db()
        self.assertEqual(self.type.name, 'Pro')
        self.assertEqual(self.type.lessons_count, 12)
        self.assertEqual(self.type.price, Decimal('150.00'))
