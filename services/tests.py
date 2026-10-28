import re

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Location, ServiceRequest

S = ServiceRequest.Status


def make_user(email, role, **kw):
    return User.objects.create_user(email=email, password='pw-Strong-123', name=email.split('@')[0], role=role, **kw)


class SignupTests(TestCase):
    def signup(self, email):
        return self.client.post(reverse('accounts:signup'), {
            'name': 'Asha', 'email': email, 'phone': '9876543210', 'role': 'student',
            'department': 'Computer', 'year': '2', 'password': 'pw-Strong-123', 'password2': 'pw-Strong-123',
        })

    def test_non_coep_email_rejected(self):
        r = self.signup('asha@gmail.com')
        self.assertContains(r, 'Only COEP emails')
        self.assertEqual(len(mail.outbox), 0)

    def test_otp_flow_creates_user_with_hashed_password(self):
        r = self.signup('asha@coeptech.ac.in')
        self.assertRedirects(r, reverse('accounts:verify'))
        code = re.search(r'\b(\d{6})\b', mail.outbox[0].body).group(1)
        self.assertEqual(self.client.post(reverse('accounts:verify'), {'code': '000000' if code != '000000' else '111111'}).status_code, 200)
        self.assertFalse(User.objects.exists())
        r = self.client.post(reverse('accounts:verify'), {'code': code})
        self.assertRedirects(r, reverse('home'))
        user = User.objects.get()
        self.assertTrue(user.password.startswith('pbkdf2_'))
        self.assertTrue(user.check_password('pw-Strong-123'))
        self.assertEqual(user.role, User.Role.STUDENT)


class ServiceRequestTests(TestCase):
    def setUp(self):
        self.loc = Location.objects.create(building='Main', floor='1', classroom='201')
        self.student = make_user('s@coeptech.ac.in', User.Role.STUDENT)
        self.other = make_user('o@coeptech.ac.in', User.Role.STUDENT)
        self.bvg = make_user('b@coeptech.ac.in', User.Role.BVG)
        self.bvg2 = make_user('b2@coeptech.ac.in', User.Role.BVG)

    def test_priority_and_queue_order(self):
        clean = ServiceRequest.objects.create(user=self.student, category='cleaning', location=self.loc)
        med = ServiceRequest.objects.create(user=self.student, category='medical', location=self.loc)
        self.assertEqual(med.priority, ServiceRequest.Priority.HIGH)
        self.assertEqual(clean.priority, ServiceRequest.Priority.NORMAL)
        self.client.force_login(self.bvg)
        r = self.client.get(reverse('services:queue'))
        self.assertEqual(list(r.context['requests']), [med, clean])

    def test_create_and_full_lifecycle(self):
        self.client.force_login(self.student)
        r = self.client.post(reverse('services:new'), {'category': 'security', 'location': self.loc.pk, 'note': ''})
        sr = ServiceRequest.objects.get()
        self.assertRedirects(r, reverse('services:detail', args=[sr.pk]))

        self.client.force_login(self.bvg)
        for expected in (S.ACCEPTED, S.IN_PROGRESS, S.DONE):
            self.client.post(reverse('services:advance', args=[sr.pk]))
            sr.refresh_from_db()
            self.assertEqual(sr.status, expected)
        self.assertEqual(sr.assigned_staff, self.bvg)
        self.assertEqual(sr.events.count(), 3)
        self.assertIsNotNone(sr.done_at)

    def test_other_staff_cannot_advance_accepted_job(self):
        sr = ServiceRequest.objects.create(user=self.student, category='cleaning', location=self.loc)
        sr.advance(self.bvg)
        self.client.force_login(self.bvg2)
        self.client.post(reverse('services:advance', args=[sr.pk]))
        sr.refresh_from_db()
        self.assertEqual(sr.status, S.ACCEPTED)

    def test_role_isolation(self):
        sr = ServiceRequest.objects.create(user=self.student, category='other', location=self.loc)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('services:detail', args=[sr.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('services:queue')).status_code, 403)
        self.assertEqual(self.client.post(reverse('services:advance', args=[sr.pk])).status_code, 403)
        self.client.force_login(self.bvg)
        self.assertEqual(self.client.get(reverse('services:new')).status_code, 403)
