import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfWriter

from accounts.models import User

from .forms import parse_page_range
from .models import PrintOrder, Shop

S = PrintOrder.Status
TMP = tempfile.mkdtemp()


def pdf_upload(pages=4, name='notes.pdf'):
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=595, height=842)
    buf = BytesIO()
    w.write(buf)
    return SimpleUploadedFile(name, buf.getvalue(), content_type='application/pdf')


def png_upload(name='shot.png'):
    buf = BytesIO()
    Image.new('RGB', (300, 600), 'white').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def make_user(email, role):
    return User.objects.create_user(email=email, password='pw-Strong-123', name=email.split('@')[0], role=role)


class PageRangeTests(TestCase):
    def test_parse(self):
        self.assertEqual(parse_page_range('', 3), [1, 2, 3])
        self.assertEqual(parse_page_range('1-3, 5, 2', 10), [1, 2, 3, 5])
        for bad in ('0-2', '3-1', '1-11', 'a', '1,,2'):
            with self.assertRaises(forms.ValidationError):
                parse_page_range(bad, 10)


@override_settings(MEDIA_ROOT=TMP + '/pub', PRIVATE_MEDIA_ROOT=TMP + '/priv')
class PrintFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.student = make_user('stu@coeptech.ac.in', User.Role.STUDENT)
        self.other = make_user('other@coeptech.ac.in', User.Role.STUDENT)
        self.owner = make_user('shop@coeptech.ac.in', User.Role.SHOP)
        self.owner2 = make_user('shop2@coeptech.ac.in', User.Role.SHOP)
        self.shop = Shop.objects.create(owner=self.owner, name='Gate Xerox', is_open=True,
                                        qr_image=png_upload('qr.png'))
        self.shop2 = Shop.objects.create(owner=self.owner2, name='Other', is_open=True, qr_image=png_upload('qr.png'))

    def place_order(self, **opts):
        self.client.force_login(self.student)
        data = {'upload': pdf_upload(10), 'color': 'bw', 'sides': 'single', 'paper_size': 'A4',
                'binding': 'none', 'copies': 2, 'page_range': '1-3,5'}
        data.update(opts)
        r = self.client.post(reverse('printing:new', args=[self.shop.pk]), data)
        order = PrintOrder.objects.latest('pk')
        self.assertRedirects(r, reverse('printing:pay', args=[order.pk]))
        r = self.client.post(reverse('printing:pay', args=[order.pk]), {
            'payment_screenshot': png_upload(), 'txn_last_digits': '4821', 'delivery_point': 'library'})
        self.assertRedirects(r, reverse('printing:order', args=[order.pk]))
        order.refresh_from_db()
        return order

    def test_quote(self):
        total, b = self.shop.quote(4, 'color', 'double', 'A3', 'spiral', 2)
        # 4 pages × (4.50 × 2) + 25 spiral = 61 per copy, × 2 copies
        self.assertEqual(total, Decimal('122'))
        self.assertEqual(b['per_copy'], '61.00')

    def test_full_flow_and_file_deleted_on_delivery(self):
        order = self.place_order()
        self.assertEqual(order.status, S.PLACED)
        self.assertEqual((order.page_count, order.pages_to_print), (10, 4))
        self.assertEqual(order.price, Decimal('8'))  # 4 pages × ₹1 × 2 copies
        self.assertEqual(order.delivery_point, 'library')
        self.assertTrue(order.file)

        self.client.force_login(self.owner)
        for expected in (S.VERIFIED, S.PRINTING, S.OUT, S.DELIVERED):
            self.client.post(reverse('printing:shop_advance', args=[order.pk]))
            order.refresh_from_db()
            self.assertEqual(order.status, expected)
        self.assertFalse(order.file)
        self.assertIsNotNone(order.file_deleted_at)
        self.assertEqual(order.events.count(), 5)

    def test_closed_shop_and_bad_inputs(self):
        self.shop.is_open = False
        self.shop.save()
        self.client.force_login(self.student)
        r = self.client.get(reverse('printing:new', args=[self.shop.pk]))
        self.assertRedirects(r, reverse('printing:shops'))

        self.shop.is_open = True
        self.shop.save()
        r = self.client.post(reverse('printing:new', args=[self.shop.pk]), {
            'upload': SimpleUploadedFile('x.docx', b'hello'), 'color': 'bw', 'sides': 'single',
            'paper_size': 'A4', 'binding': 'none', 'copies': 1})
        self.assertContains(r, 'Convert Word/PPT')
        r = self.client.post(reverse('printing:new', args=[self.shop.pk]), {
            'upload': pdf_upload(2), 'color': 'bw', 'sides': 'single', 'paper_size': 'A4',
            'binding': 'none', 'copies': 1, 'page_range': '1-5'})
        self.assertContains(r, 'between 1 and 2')
        self.assertFalse(PrintOrder.objects.exists())

    def test_txn_digits_required(self):
        self.client.force_login(self.student)
        self.client.post(reverse('printing:new', args=[self.shop.pk]), {
            'upload': pdf_upload(1), 'color': 'bw', 'sides': 'single', 'paper_size': 'A4',
            'binding': 'none', 'copies': 1})
        order = PrintOrder.objects.get()
        r = self.client.post(reverse('printing:pay', args=[order.pk]), {
            'payment_screenshot': png_upload(), 'txn_last_digits': '12', 'delivery_point': 'main_gate'})
        self.assertContains(r, 'last 4 to 6 digits')
        order.refresh_from_db()
        self.assertEqual(order.status, S.DRAFT)

    def test_shop_sees_only_its_orders_and_drafts_are_hidden(self):
        order = self.place_order()
        self.client.force_login(self.owner2)
        self.assertEqual(self.client.get(reverse('printing:shop_order', args=[order.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('printing:download', args=[order.pk, 'file'])).status_code, 403)
        self.client.force_login(self.owner)
        r = self.client.get(reverse('printing:download', args=[order.pk, 'file']))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(self.client.get(reverse('printing:shop_dashboard')).context['orders']), [order])

    def test_other_student_cannot_see_order_or_file(self):
        order = self.place_order()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('printing:order', args=[order.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('printing:download', args=[order.pk, 'screenshot'])).status_code, 403)

    def test_reject_deletes_file(self):
        order = self.place_order()
        self.client.force_login(self.owner)
        self.client.post(reverse('printing:shop_reject', args=[order.pk]), {'reason': 'Payment not received'})
        order.refresh_from_db()
        self.assertEqual(order.status, S.REJECTED)
        self.assertFalse(order.file)

    def test_cannot_open_without_qr(self):
        self.shop.is_open = False
        self.shop.qr_image = ''
        self.shop.save()
        self.client.force_login(self.owner)
        self.client.post(reverse('printing:toggle_open'))
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.is_open)

    def test_purge_command(self):
        order = self.place_order()
        PrintOrder.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=30))
        call_command('purge_print_files', stdout=BytesIO() and None)
        order.refresh_from_db()
        self.assertFalse(order.file)
        self.assertFalse(order.payment_screenshot)
