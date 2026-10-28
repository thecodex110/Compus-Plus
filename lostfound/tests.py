import shutil
import tempfile
from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import User

from .models import Post

MEDIA = tempfile.mkdtemp()


def jpeg_bytes(size=(2400, 1600)):
    buf = BytesIO()
    exif = Image.Exif()
    exif[0x010F] = 'TestCam'  # Make
    Image.new('RGB', size, 'red').save(buf, 'JPEG', exif=exif)
    return buf.getvalue()


def make_user(email, role=User.Role.STUDENT, **kw):
    return User.objects.create_user(email=email, password='pw-Strong-123', name=email.split('@')[0].title(),
                                    role=role, **kw)


@override_settings(MEDIA_ROOT=MEDIA)
class LostFoundTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.asha = make_user('asha@coeptech.ac.in', phone='9876500001')
        self.ravi = make_user('ravi@coeptech.ac.in', phone='9876500002')

    def post(self, user=None, **kw):
        data = {'user': user or self.asha, 'type': 'lost', 'title': 'Charger', 'place': 'Library'}
        data.update(kw)
        return Post.objects.create(**data)

    def test_create_found_post_compresses_photo_and_strips_exif(self):
        self.client.force_login(self.asha)
        photo = SimpleUploadedFile('p.jpg', jpeg_bytes(), content_type='image/jpeg')
        r = self.client.post(reverse('lostfound:new'), {
            'type': 'found', 'title': 'Blue bottle', 'place': 'Canteen',
            'date': timezone.localdate().isoformat(), 'photo': photo,
        })
        post = Post.objects.get()
        self.assertRedirects(r, reverse('lostfound:detail', args=[post.pk]))
        img = Image.open(post.photo.path)
        self.assertLessEqual(max(img.size), 1280)
        self.assertEqual(len(img.getexif()), 0)

    def test_found_needs_photo_and_date_not_in_future(self):
        self.client.force_login(self.asha)
        r = self.client.post(reverse('lostfound:new'), {
            'type': 'found', 'title': 'Keys', 'place': 'Gate',
            'date': (timezone.localdate() + timedelta(days=1)).isoformat(),
        })
        self.assertFalse(Post.objects.exists())
        self.assertContains(r, 'Add a photo')
        self.assertContains(r, 'cannot be in the future')

    def test_feed_newest_first_and_hides_returned(self):
        old = self.post(title='Old')
        new = self.post(title='New', user=self.ravi)
        gone = self.post(title='Gone', status=Post.Status.RETURNED)
        self.client.force_login(self.asha)
        posts = list(self.client.get(reverse('lostfound:feed')).context['page'].object_list)
        self.assertEqual(posts, [new, old])
        self.assertNotIn(gone, posts)

    def test_filter_and_search(self):
        lost = self.post(title='Calculator')
        self.post(type='found', title='Umbrella')
        self.client.force_login(self.asha)
        r = self.client.get(reverse('lostfound:feed'), {'type': 'lost'})
        self.assertEqual(list(r.context['page'].object_list), [lost])
        r = self.client.get(reverse('lostfound:feed'), {'q': 'umbr'})
        self.assertEqual([p.title for p in r.context['page'].object_list], ['Umbrella'])

    def test_only_owner_can_mark_returned(self):
        p = self.post()
        self.client.force_login(self.ravi)
        self.assertEqual(self.client.post(reverse('lostfound:returned', args=[p.pk])).status_code, 404)
        self.client.force_login(self.asha)
        self.client.post(reverse('lostfound:returned', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, Post.Status.RETURNED)

    def test_phone_shown_only_with_consent(self):
        hidden = self.post()
        shown = self.post(show_phone=True)
        self.client.force_login(self.ravi)
        self.assertNotContains(self.client.get(reverse('lostfound:detail', args=[hidden.pk])), '9876500001')
        self.assertContains(self.client.get(reverse('lostfound:detail', args=[shown.pk])), '9876500001')

    def test_bvg_and_shop_have_no_access(self):
        for role in (User.Role.BVG, User.Role.SHOP):
            self.client.force_login(make_user(f'{role}@coeptech.ac.in', role=role))
            self.assertEqual(self.client.get(reverse('lostfound:feed')).status_code, 403)

    def test_admin_can_remove(self):
        p = self.post()
        self.client.force_login(make_user('ad@coeptech.ac.in', role=User.Role.ADMIN))
        self.client.post(reverse('lostfound:remove', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.status, Post.Status.REMOVED)
