import shutil
import tempfile
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import User

from .models import Listing

TMP = tempfile.mkdtemp()


def photo(name='p.jpg'):
    buf = BytesIO()
    Image.new('RGB', (1600, 1200), 'blue').save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


def make_user(email, role=User.Role.STUDENT, **kw):
    return User.objects.create_user(email=email, password='pw-Strong-123', name=email.split('@')[0].title(),
                                    role=role, **kw)


@override_settings(MEDIA_ROOT=TMP)
class MarketTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.seller = make_user('seller@coeptech.ac.in', phone='9876500011')
        self.buyer = make_user('buyer@coeptech.ac.in')

    def listing(self, **kw):
        data = {'seller': self.seller, 'title': 'Drafter', 'price': 300, 'category': 'lab', 'condition': 'good'}
        data.update(kw)
        return Listing.objects.create(**data)

    def sell(self, photos, **kw):
        data = {'title': 'Casio fx-991EX', 'price': 700, 'category': 'instruments', 'condition': 'like_new',
                'new_photos': photos}
        data.update(kw)
        return self.client.post(reverse('market:sell'), data)

    def test_sell_with_multiple_photos(self):
        self.client.force_login(self.seller)
        r = self.sell([photo('a.jpg'), photo('b.jpg')])
        listing = Listing.objects.get()
        self.assertRedirects(r, reverse('market:detail', args=[listing.pk]))
        self.assertEqual(listing.photos.count(), 2)
        self.assertLessEqual(max(Image.open(listing.cover.image.path).size), 1280)

    def test_photo_rules(self):
        self.client.force_login(self.seller)
        self.assertContains(self.sell([]), 'at least one photo')
        self.assertContains(self.sell([photo() for _ in range(6)]), 'At most 5 photos')
        self.assertFalse(Listing.objects.exists())

    def test_edit_remove_and_add_photos(self):
        self.client.force_login(self.seller)
        self.sell([photo('a.jpg'), photo('b.jpg')])
        listing = Listing.objects.get()
        first = listing.photos.first()
        r = self.client.post(reverse('market:edit', args=[listing.pk]), {
            'title': 'Casio', 'price': 650, 'category': 'instruments', 'condition': 'good',
            'remove_photos': [first.pk], 'new_photos': [photo('c.jpg')]})
        self.assertRedirects(r, reverse('market:detail', args=[listing.pk]))
        listing.refresh_from_db()
        self.assertEqual(listing.price, 650)
        self.assertEqual(listing.photos.count(), 2)
        self.assertFalse(listing.photos.filter(pk=first.pk).exists())

    def test_search_filter_sort_and_sold_hidden(self):
        cheap = self.listing(title='Cycle Hercules', price=1500, category='cycles', condition='fair')
        dear = self.listing(title='Cycle Firefox', price=4000, category='cycles', condition='like_new')
        self.listing(title='DBMS book', price=200, category='books')
        self.listing(title='Cycle sold', price=100, category='cycles', status=Listing.Status.SOLD)
        self.client.force_login(self.buyer)

        def results(**params):
            return list(self.client.get(reverse('market:browse'), params).context['page'].object_list)

        self.assertEqual(results(q='cycle', sort='low'), [cheap, dear])
        self.assertEqual(results(category='cycles', sort='high'), [dear, cheap])
        self.assertEqual(results(category='cycles', max='2000'), [cheap])
        self.assertEqual(results(condition='like_new'), [dear])
        self.assertEqual(results(min='abc', category='cycles', sort='low'), [cheap, dear])

    def test_only_seller_marks_sold(self):
        l = self.listing()
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.post(reverse('market:sold', args=[l.pk])).status_code, 404)
        self.client.force_login(self.seller)
        self.client.post(reverse('market:sold', args=[l.pk]))
        l.refresh_from_db()
        self.assertEqual(l.status, Listing.Status.SOLD)
        self.assertIsNotNone(l.sold_at)

    def test_phone_only_with_consent(self):
        hidden = self.listing()
        shown = self.listing(show_phone=True)
        self.client.force_login(self.buyer)
        self.assertNotContains(self.client.get(reverse('market:detail', args=[hidden.pk])), '9876500011')
        self.assertContains(self.client.get(reverse('market:detail', args=[shown.pk])), '9876500011')

    def test_access(self):
        for role in (User.Role.BVG, User.Role.SHOP, User.Role.TEACHER):
            self.client.force_login(make_user(f'{role}@coeptech.ac.in', role=role))
            self.assertEqual(self.client.get(reverse('market:browse')).status_code, 403)
        admin = make_user('ad@coeptech.ac.in', role=User.Role.ADMIN)
        self.client.force_login(admin)
        l = self.listing()
        self.client.post(reverse('market:remove', args=[l.pk]))
        l.refresh_from_db()
        self.assertEqual(l.status, Listing.Status.REMOVED)
        self.assertEqual(self.client.get(reverse('market:sell')).status_code, 403)
