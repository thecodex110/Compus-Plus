import re

from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from health.models import Donor, Hospital
from lostfound.models import Post
from notify.models import Notification
from printing.models import Shop
from services.models import Location, ServiceRequest


def make_user(email, role=User.Role.STUDENT, **kw):
    return User.objects.create_user(email=email, password='pw-Strong-123', name=email.split('@')[0].title(),
                                    role=role, **kw)


class NotificationTests(TestCase):
    def setUp(self):
        self.loc = Location.objects.create(building='Main', floor='1', classroom='201')
        self.student = make_user('s@coeptech.ac.in')
        self.bvg = make_user('b@coeptech.ac.in', role=User.Role.BVG)
        self.bvg2 = make_user('b2@coeptech.ac.in', role=User.Role.BVG)

    def test_new_request_notifies_all_bvg_and_status_notifies_requester(self):
        self.client.force_login(self.student)
        self.client.post(reverse('services:new'), {'category': 'medical', 'location': self.loc.pk})
        sr = ServiceRequest.objects.get()
        for staff in (self.bvg, self.bvg2):
            n = Notification.objects.get(user=staff)
            self.assertTrue(n.urgent)
            self.assertIn('Medical', n.title)
        self.client.force_login(self.bvg)
        self.client.post(reverse('services:advance', args=[sr.pk]))
        n = Notification.objects.get(user=self.student)
        self.assertIn('Accepted', n.title)

    def test_poll_inbox_and_open(self):
        Notification.objects.create(user=self.student, title='Hello', url='/services/mine/')
        Notification.objects.create(user=self.bvg, title='Not yours')
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('notify:poll')).json()['unread'], 1)
        r = self.client.get(reverse('notify:inbox'))
        self.assertContains(r, 'Hello')
        self.assertNotContains(r, 'Not yours')
        self.assertEqual(self.client.get(reverse('notify:poll')).json()['unread'], 0)
        other = Notification.objects.get(user=self.bvg)
        self.assertEqual(self.client.get(reverse('notify:open', args=[other.pk])).status_code, 404)

    def test_donor_told_when_number_viewed(self):
        donor = Donor.objects.create(user=self.student, blood_group='A+')
        seeker = make_user('seek@coeptech.ac.in', role=User.Role.TEACHER)
        self.client.force_login(seeker)
        self.client.post(reverse('health:reveal', args=[donor.pk]))
        self.assertTrue(Notification.objects.filter(user=self.student, title__contains='viewed your number').exists())


class PanelTests(TestCase):
    def setUp(self):
        self.admin = make_user('admin@coeptech.ac.in', role=User.Role.ADMIN)
        self.client.force_login(self.admin)

    def test_only_admins(self):
        self.client.force_login(make_user('s@coeptech.ac.in'))
        for name in ('panel:dashboard', 'panel:users', 'panel:locations', 'panel:moderate', 'panel:hospitals'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_dashboard_and_home_redirect(self):
        self.assertRedirects(self.client.get(reverse('home')), reverse('panel:dashboard'))
        self.assertEqual(self.client.get(reverse('panel:dashboard')).status_code, 200)

    def test_create_shop_account_creates_shop(self):
        r = self.client.post(reverse('panel:create_user'), {
            'name': 'Xerox Point', 'email': 'xerox@example.com', 'phone': '9876543299', 'role': 'shop',
            'password1': 'Strong-pass-981', 'password2': 'Strong-pass-981'})
        self.assertRedirects(r, reverse('panel:users'))
        user = User.objects.get(email='xerox@example.com')
        self.assertTrue(user.check_password('Strong-pass-981'))
        self.assertTrue(Shop.objects.filter(owner=user).exists())

    def test_deactivate_user_blocks_login(self):
        u = make_user('x@coeptech.ac.in')
        self.client.post(reverse('panel:toggle_active', args=[u.pk]))
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        self.client.logout()
        r = self.client.post(reverse('accounts:login'), {'email': 'x@coeptech.ac.in', 'password': 'pw-Strong-123'})
        self.assertContains(r, 'Wrong email or password')

    def test_bulk_locations_and_protected_delete(self):
        self.client.post(reverse('panel:locations'), {'building': 'Mech', 'floor': '2', 'classrooms': '201, 202,203'})
        self.assertEqual(Location.objects.filter(building='Mech').count(), 3)
        used = Location.objects.get(classroom='201')
        ServiceRequest.objects.create(user=make_user('s@coeptech.ac.in'), category='other', location=used)
        self.client.post(reverse('panel:delete_location', args=[used.pk]))
        self.assertTrue(Location.objects.filter(pk=used.pk).exists())
        free = Location.objects.get(classroom='202')
        self.client.post(reverse('panel:delete_location', args=[free.pk]))
        self.assertFalse(Location.objects.filter(pk=free.pk).exists())

    def test_hospital_crud(self):
        self.client.post(reverse('panel:hospital_new'), {'name': 'City Hospital', 'address': 'FC Road',
                                                          'distance_km': '1.2', 'emergency_phone': '020-1234',
                                                          'is_24x7': 'on'})
        h = Hospital.objects.get()
        self.client.post(reverse('panel:hospital_edit', args=[h.pk]), {'name': 'City Hospital', 'address': 'FC Road',
                                                                        'distance_km': '1.5'})
        h.refresh_from_db()
        self.assertEqual(str(h.distance_km), '1.5')
        self.client.post(reverse('panel:hospital_delete', args=[h.pk]))
        self.assertFalse(Hospital.objects.exists())

    def test_shop_counts_are_not_multiplied_by_stationery(self):
        from printing.models import PrintOrder, StationeryItem
        owner = make_user('sh@coeptech.ac.in', role=User.Role.SHOP)
        shop = Shop.objects.create(owner=owner, name='Gate')
        for i in range(3):
            StationeryItem.objects.create(shop=shop, name=f'Item {i}', price=5)
        student = make_user('st@coeptech.ac.in')
        for status in ('placed', 'verified', 'delivered'):
            PrintOrder.objects.create(student=student, shop=shop, price=10, status=status)
        row = self.client.get(reverse('panel:shops')).context['shops'][0]
        self.assertEqual((row.active, row.delivered, row.items), (2, 1, 3))

    def test_moderate_remove(self):
        p = Post.objects.create(user=make_user('s@coeptech.ac.in'), type='lost', title='Bag', place='Gate')
        self.client.post(reverse('panel:remove_item', args=['post', p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, Post.Status.REMOVED)


class AccountPolishTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user('s@coeptech.ac.in')

    def test_login_next_is_not_an_open_redirect(self):
        r = self.client.post(reverse('accounts:login') + '?next=https://evil.example/',
                             {'email': 's@coeptech.ac.in', 'password': 'pw-Strong-123'})
        self.assertRedirects(r, reverse('home'), fetch_redirect_response=False)
        self.client.logout()
        r = self.client.post(reverse('accounts:login') + '?next=/market/',
                             {'email': 's@coeptech.ac.in', 'password': 'pw-Strong-123'})
        self.assertEqual(r['Location'], '/market/')

    def test_login_lockout_after_many_failures(self):
        for _ in range(10):
            self.client.post(reverse('accounts:login'), {'email': 's@coeptech.ac.in', 'password': 'nope'})
        r = self.client.post(reverse('accounts:login'), {'email': 's@coeptech.ac.in', 'password': 'pw-Strong-123'})
        self.assertContains(r, 'Too many wrong attempts')

    def test_profile_update_and_password_change(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:profile'), {'form': 'details', 'name': 'New Name', 'phone': '9123456789',
                                                       'department': 'IT', 'year': '3'})
        self.user.refresh_from_db()
        self.assertEqual((self.user.name, self.user.year), ('New Name', 3))
        self.client.post(reverse('accounts:profile'), {'form': 'password', 'old_password': 'pw-Strong-123',
                                                       'new_password1': 'Another-pass-77',
                                                       'new_password2': 'Another-pass-77'})
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Another-pass-77'))

    def test_password_reset_email_flow(self):
        self.client.post(reverse('accounts:password_reset'), {'email': 's@coeptech.ac.in'})
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r'http://testserver(/accounts/reset/\S+)', mail.outbox[0].body).group(1)
        r = self.client.get(link, follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {'new_password1': 'Reset-pass-55', 'new_password2': 'Reset-pass-55'})
        self.assertRedirects(r, reverse('accounts:password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Reset-pass-55'))
