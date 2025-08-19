from datetime import date
from django.test import TestCase
from django.urls import reverse


class CalendarAlignmentTests(TestCase):
    def test_month_view_aligns_days_correctly(self):
        """August 20, 2024 should fall on a Tuesday in the calendar weeks."""
        response = self.client.get(reverse('home'), {'year': 2024, 'month': 8})
        weeks = response.context['weeks']
        self.assertEqual(weeks[3][1], date(2024, 8, 20))
