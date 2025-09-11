from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse

from datetime import date, timedelta
from django.contrib.auth.models import User, Group
from decimal import Decimal
from .models import SubscriptionType, Child, TrainingSession


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


class ScheduleMonthViewTests(TestCase):
    def setUp(self):
        self.parent = User.objects.create_user(username='parent', password='pass')
        group = Group.objects.create(name='Parent')
        self.parent.groups.add(group)

    def test_parent_can_view_month_schedule(self):
        self.client.login(username='parent', password='pass')
        response = self.client.get(reverse('schedule_month'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('weeks', response.context)


class ChildSessionDeleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.child = Child.objects.create(first_name='Test', last_name='Kid')
        self.session1 = TrainingSession.objects.create(start=timezone.now())
        self.session2 = TrainingSession.objects.create(start=timezone.now() + timedelta(days=1))
        self.session1.participants.add(self.child)
        self.session2.participants.add(self.child)

    def test_children_list_has_link_to_detail(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('children_list'))
        self.assertContains(resp, reverse('child_detail', args=[self.child.pk]))

    def test_children_list_has_name_filter(self):
        self.client.login(username='admin', password='pass')
        resp = self.client.get(reverse('children_list'))
        self.assertContains(resp, 'id="child-filter"')

    def test_delete_single_session(self):
        self.client.login(username='admin', password='pass')
        url = reverse('child_sessions_delete', args=[self.child.pk])
        resp = self.client.post(url, {'session_ids': self.session1.id})
        self.assertRedirects(resp, reverse('child_detail', args=[self.child.pk]))
        self.assertFalse(TrainingSession.objects.filter(id=self.session1.id, participants=self.child).exists())

    def test_delete_multiple_sessions(self):
        self.client.login(username='admin', password='pass')
        url = reverse('child_sessions_delete', args=[self.child.pk])
        resp = self.client.post(url, {'session_ids': [self.session1.id, self.session2.id]})
        self.assertRedirects(resp, reverse('child_detail', args=[self.child.pk]))
        self.assertEqual(self.child.sessions.count(), 0)
