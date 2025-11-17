from datetime import date, timedelta
from django.test import TestCase
from django.urls import reverse

from datetime import date, timedelta
from django.utils import timezone
from django.contrib.auth.models import User, Group
from decimal import Decimal
from .models import SubscriptionType, Subscription, Child, TrainingSession, Visit


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


class StudentSubscriptionViewTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(name='Student')
        self.user = User.objects.create_user(username='student', password='pass')
        self.user.groups.add(self.group)
        self.child = Child.objects.create(
            first_name='Adult',
            last_name='Learner',
            is_adult=True,
            account_user=self.user,
        )
        self.sub_type = SubscriptionType.objects.create(
            name='Adult Pass',
            lessons_count=8,
            price=Decimal('120.00'),
        )
        self.subscription = Subscription.objects.create(
            child=self.child,
            sub_type=self.sub_type,
            lessons_remaining=5,
            price=Decimal('120.00'),
            paid=True,
        )

    def test_student_can_view_subscription(self):
        self.client.login(username='student', password='pass')
        response = self.client.get(reverse('my_subscription'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Мой абонемент')
        self.assertContains(response, 'Adult Pass (8)')
        self.assertContains(response, '5')
        self.assertContains(response, 'Оплачен')

    def test_student_without_subscription_sees_message(self):
        self.subscription.delete()
        self.client.login(username='student', password='pass')
        response = self.client.get(reverse('my_subscription'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'У вас пока нет оформленного абонемента')


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


class UpcomingBirthdaysBannerTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass", is_staff=True)
        self.child = Child.objects.create(
            first_name="Test", last_name="Kid", birth_date=timezone.localdate() + timedelta(days=1)
        )

    def test_banner_visible_on_children_list(self):
        self.client.login(username="admin", password="pass")
        resp = self.client.get(reverse("children_list"))
        self.assertContains(resp, "Скоро дни рождения")
        self.assertContains(resp, "Test Kid")


class VisitAndPaymentLogicTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username='admin', password='pass', is_staff=True)
        self.child = Child.objects.create(first_name='Test', last_name='Kid')
        self.sub_type = SubscriptionType.objects.create(name='Base', lessons_count=2, price=Decimal('100.00'))
        self.subscription = Subscription.objects.create(
            child=self.child,
            sub_type=self.sub_type,
            lessons_remaining=1,
            paid=True,
        )

    def test_last_paid_visit_marks_subscription_unpaid(self):
        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('add_visit'), {'child_id': self.child.id})
        self.assertRedirects(response, reverse('children_list'))
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, 0)
        self.assertFalse(self.subscription.paid)
        self.assertEqual(Visit.objects.count(), 1)

    def test_visit_can_be_added_when_subscription_unpaid(self):
        self.subscription.lessons_remaining = 0
        self.subscription.paid = False
        self.subscription.save()
        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('add_visit'), {'child_id': self.child.id})
        self.assertRedirects(response, reverse('children_list'))
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, self.sub_type.lessons_count - 1)
        self.assertFalse(self.subscription.paid)
        self.assertEqual(Visit.objects.count(), 1)

    def test_visit_can_be_added_when_subscription_zero_but_marked_paid(self):
        self.subscription.lessons_remaining = 0
        self.subscription.paid = True
        self.subscription.save()

        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('add_visit'), {'child_id': self.child.id})

        self.assertRedirects(response, reverse('children_list'))
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, self.sub_type.lessons_count - 1)
        self.assertFalse(self.subscription.paid)
        self.assertEqual(Visit.objects.count(), 1)

    def test_mark_payment_refills_counter_when_zero(self):
        self.subscription.lessons_remaining = 0
        self.subscription.paid = False
        self.subscription.save()

        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('mark_payment'), {'child_id': self.child.id})

        self.assertRedirects(response, reverse('children_list'))
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.paid)
        self.assertEqual(self.subscription.lessons_remaining, self.sub_type.lessons_count)

    def test_mark_payment_keeps_existing_counter(self):
        self.subscription.lessons_remaining = 1
        self.subscription.paid = False
        self.subscription.save()

        self.client.login(username='admin', password='pass')
        response = self.client.post(reverse('mark_payment'), {'child_id': self.child.id})

        self.assertRedirects(response, reverse('children_list'))
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.paid)
        self.assertEqual(self.subscription.lessons_remaining, 1)

    def test_counter_rolls_over_and_continues_decrementing(self):
        self.subscription.lessons_remaining = 0
        self.subscription.paid = False
        self.subscription.save()

        self.client.login(username='admin', password='pass')
        self.client.post(reverse('add_visit'), {'child_id': self.child.id})
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, self.sub_type.lessons_count - 1)
        self.assertFalse(self.subscription.paid)

        self.client.post(reverse('add_visit'), {'child_id': self.child.id})
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, 0)
        self.assertFalse(self.subscription.paid)
        self.assertEqual(Visit.objects.count(), 2)

    def test_mark_payment_after_rollover_keeps_counter(self):
        self.subscription.lessons_remaining = 0
        self.subscription.paid = False
        self.subscription.save()

        self.client.login(username='admin', password='pass')
        self.client.post(reverse('add_visit'), {'child_id': self.child.id})
        self.subscription.refresh_from_db()
        remaining_after_visit = self.subscription.lessons_remaining

        response = self.client.post(reverse('mark_payment'), {'child_id': self.child.id})
        self.assertRedirects(response, reverse('children_list'))
        self.subscription.refresh_from_db()
        self.assertTrue(self.subscription.paid)
        self.assertEqual(self.subscription.lessons_remaining, remaining_after_visit)

    def test_visit_after_manual_payment_uses_refilled_counter(self):
        self.subscription.lessons_remaining = 0
        self.subscription.paid = False
        self.subscription.save()

        self.client.login(username='admin', password='pass')
        self.client.post(reverse('mark_payment'), {'child_id': self.child.id})

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, self.sub_type.lessons_count)
        self.assertTrue(self.subscription.paid)

        self.client.post(reverse('add_visit'), {'child_id': self.child.id})
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.lessons_remaining, self.sub_type.lessons_count - 1)
        self.assertTrue(self.subscription.paid)
