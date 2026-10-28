from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from . import views
from .models import ContactReveal, Donor, Hospital


def make_user(email, role=User.Role.STUDENT, **kw):
    return User.objects.create_user(email=email, password='pw-Strong-123', name=email.split('@')[0].title(),
                                    role=role, **kw)


class BloodDirectoryTests(TestCase):
    def setUp(self):
        self.asha = make_user('asha@coeptech.ac.in', phone='9876511111', department='Civil', year=3)
        self.ravi = make_user('ravi@coeptech.ac.in', phone='9876522222')
        self.seeker = make_user('seek@coeptech.ac.in')

    def search(self, **params):
        r = self.client.get(reverse('health:directory'), params)
        return [d.user for d in r.context['donors']], r

    def test_opt_in_requires_consent(self):
        self.client.force_login(self.asha)
        r = self.client.post(reverse('health:me'), {'blood_group': 'O-', 'visible': 'on'})
        self.assertContains(r, 'You must agree')
        self.assertFalse(Donor.objects.exists())
        self.client.post(reverse('health:me'), {'blood_group': 'O-', 'visible': 'on', 'consent': 'on'})
        self.assertEqual(Donor.objects.get().blood_group, 'O-')

    def test_not_listed_unless_opted_in_and_visible(self):
        Donor.objects.create(user=self.asha, blood_group='B+', visible=False)
        self.client.force_login(self.seeker)
        users, r = self.search(group='B+')
        self.assertEqual(users, [])
        self.assertNotContains(r, 'Asha')

    def test_phone_hidden_until_revealed_and_logged(self):
        donor = Donor.objects.create(user=self.asha, blood_group='B+')
        self.client.force_login(self.seeker)
        users, r = self.search(group='B+')
        self.assertEqual(users, [self.asha])
        self.assertNotContains(r, '9876511111')
        self.client.post(reverse('health:reveal', args=[donor.pk]), {'back': '/blood/?group=B%2B'})
        _, r = self.search(group='B+')
        self.assertContains(r, 'tel:9876511111')
        self.assertEqual(ContactReveal.objects.filter(viewer=self.seeker, donor=donor).count(), 1)
        # The donor sees who looked them up.
        self.client.force_login(self.asha)
        self.assertContains(self.client.get(reverse('health:me')), 'Seek')

    def test_compatible_search(self):
        Donor.objects.create(user=self.asha, blood_group='O-')
        Donor.objects.create(user=self.ravi, blood_group='A+')
        self.client.force_login(self.seeker)
        self.assertEqual(self.search(group='A+')[0], [self.ravi])
        self.assertEqual(self.search(group='A+', compatible='1')[0], [self.ravi, self.asha])
        self.assertEqual(self.search(group='O-', compatible='1')[0], [self.asha])

    def test_hide_and_delete(self):
        Donor.objects.create(user=self.asha, blood_group='AB+')
        self.client.force_login(self.asha)
        self.client.post(reverse('health:toggle'))
        self.assertFalse(Donor.objects.get().visible)
        self.client.post(reverse('health:delete'))
        self.assertFalse(Donor.objects.exists())

    def test_reveal_rate_limit(self):
        donors = [Donor.objects.create(user=make_user(f'd{i}@coeptech.ac.in', phone='98765000%02d' % i),
                                       blood_group='O+') for i in range(views.REVEALS_PER_DAY + 1)]
        self.client.force_login(self.seeker)
        for d in donors:
            self.client.post(reverse('health:reveal', args=[d.pk]))
        self.assertEqual(ContactReveal.objects.filter(viewer=self.seeker).count(), views.REVEALS_PER_DAY)

    def test_reveal_back_url_is_not_an_open_redirect(self):
        donor = Donor.objects.create(user=self.asha, blood_group='B+')
        self.client.force_login(self.seeker)
        r = self.client.post(reverse('health:reveal', args=[donor.pk]), {'back': 'https://evil.example/'})
        self.assertEqual(r['Location'], f'/blood/#donor-{donor.pk}')

    def test_access(self):
        teacher = make_user('t@coeptech.ac.in', role=User.Role.TEACHER)
        self.client.force_login(teacher)
        self.assertEqual(self.client.get(reverse('health:directory')).status_code, 200)
        self.assertEqual(self.client.get(reverse('health:me')).status_code, 403)
        for role in (User.Role.BVG, User.Role.SHOP):
            self.client.force_login(make_user(f'{role}@coeptech.ac.in', role=role))
            self.assertEqual(self.client.get(reverse('health:directory')).status_code, 403)
            self.assertEqual(self.client.get(reverse('health:hospitals')).status_code, 200)


class HospitalTests(TestCase):
    def test_sorted_by_distance_and_blood_bank_filter(self):
        far = Hospital.objects.create(name='Far', address='x', distance_km='5.0', has_blood_bank=True)
        near = Hospital.objects.create(name='Near', address='y', distance_km='0.5')
        self.client.force_login(make_user('s@coeptech.ac.in'))
        r = self.client.get(reverse('health:hospitals'))
        self.assertEqual(list(r.context['hospitals']), [near, far])
        r = self.client.get(reverse('health:hospitals'), {'blood_bank': '1'})
        self.assertEqual(list(r.context['hospitals']), [far])
