from django.test import TestCase
from django.urls import reverse
from django.utils.translation import gettext

from accounts.models import User
from notify.models import Notification, notify


class LanguageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='s@coeptech.ac.in', password='pw-Strong-123', name='Asha',
                                             role=User.Role.STUDENT)

    def test_staff_switch_to_hindi_is_saved_on_account(self):
        staff = User.objects.create_user(email='b@coeptech.ac.in', password='pw-Strong-123', name='Ganesh',
                                         role=User.Role.BVG)
        self.client.force_login(staff)
        r = self.client.post(reverse('accounts:language'), {'language': 'hi', 'next': '/'})
        self.assertRedirects(r, '/', fetch_redirect_response=False)
        staff.refresh_from_db()
        self.assertEqual(staff.language, 'hi')
        page = self.client.get(reverse('services:queue'))
        self.assertContains(page, '<html lang="hi">')

    def test_students_stay_in_english(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:language'), {'language': 'hi', 'next': '/'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, 'en')
        page = self.client.get(reverse('home'))
        self.assertContains(page, 'Hello, Asha')
        self.assertNotContains(page, 'name="language"')

    def test_signed_out_visitor_uses_cookie(self):
        self.client.post(reverse('accounts:language'), {'language': 'hi'})
        self.assertContains(self.client.get(reverse('accounts:login')), 'लॉग इन')
        self.client.post(reverse('accounts:language'), {'language': 'en'})
        self.assertContains(self.client.get(reverse('accounts:login')), 'Log in')

    def test_language_next_is_not_an_open_redirect(self):
        r = self.client.post(reverse('accounts:language'), {'language': 'hi', 'next': 'https://evil.example/'})
        self.assertEqual(r['Location'], '/')

    def test_notifications_use_each_recipients_language(self):
        hindi = User.objects.create_user(email='h@coeptech.ac.in', password='x-Strong-123', name='Ravi',
                                         role=User.Role.BVG, language='hi')
        notify([self.user, hindi], lambda: gettext('Pending'))
        self.assertEqual(Notification.objects.get(user=self.user).title, 'Pending')
        self.assertEqual(Notification.objects.get(user=hindi).title, 'बाकी')


class SegmentsTagTests(TestCase):
    def render(self, body, **ctx):
        from django.template import Context, Template
        return Template('{% load ui %}{% segs %}' + body + '{% endsegs %}').render(Context(ctx))

    def test_splits_on_separators_including_variables(self):
        html = self.render('{{ a }}&nbsp;· {{ b }}', a='₹150', b='Main Gate\xa0· Floor 1')
        self.assertEqual(html.count('class="seg"'), 3)
        self.assertNotIn('&nbsp;·', html)

    def test_single_piece_is_left_alone(self):
        self.assertEqual(self.render('{{ a }}', a='Only'), 'Only')


class WelcomeAndRoleLoginTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(email='g@coeptech.ac.in', password='pw-Strong-123', name='Ganesh',
                                              role=User.Role.BVG)

    def test_visitors_see_the_welcome_page_with_a_login_per_role(self):
        r = self.client.get(reverse('home'))
        self.assertTemplateUsed(r, 'accounts/welcome.html')
        for role in User.Role.values:
            self.assertContains(r, f'?role={role}')

    def test_login_on_the_wrong_role_tab_is_refused(self):
        r = self.client.post(reverse('accounts:login') + '?role=student',
                             {'email': 'g@coeptech.ac.in', 'password': 'pw-Strong-123', 'role': 'student'})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(r, 'This is a BVG Staff account.')

    def test_login_on_the_right_role_tab_works(self):
        r = self.client.post(reverse('accounts:login') + '?role=bvg',
                             {'email': 'g@coeptech.ac.in', 'password': 'pw-Strong-123', 'role': 'bvg'})
        self.assertEqual(self.client.session['_auth_user_id'], str(self.staff.pk))
        self.assertRedirects(r, reverse('home'), fetch_redirect_response=False)
