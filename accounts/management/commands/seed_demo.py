import os
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image, ImageDraw

from accounts.models import User
from health.models import Hospital
from printing.models import Shop
from services.models import Location

BUILDINGS = {
    'Main Building': {'G': ['101', '102', 'Seminar Hall'], '1': ['201', '202', '203'], '2': ['301', '302']},
    'Academic Complex': {'G': ['AC-001', 'AC-002'], '1': ['AC-101', 'AC-102', 'AC-103'], '2': ['AC-201']},
    'Instrumentation Dept': {'G': ['Lab 1', 'Lab 2'], '1': ['IN-101', 'IN-102']},
    'Library': {'G': ['Reading Hall', 'Issue Counter'], '1': ['Reference Section']},
}

DEMO_USERS = [
    ('student@coeptech.ac.in', 'Demo Student', User.Role.STUDENT, {'department': 'Computer', 'year': 2, 'phone': '9876543210'}),
    ('teacher@coeptech.ac.in', 'Demo Teacher', User.Role.TEACHER, {'department': 'Computer', 'phone': '9876543211'}),
    ('bvg@coeptech.ac.in', 'Demo BVG Staff', User.Role.BVG, {'phone': '9876543212'}),
    ('bvg2@coeptech.ac.in', 'Second BVG Staff', User.Role.BVG, {'phone': '9876543213'}),
    ('shop@coeptech.ac.in', 'Demo Photocopy Shop', User.Role.SHOP, {'phone': '9876543214'}),
    ('shop2@coeptech.ac.in', 'Second Xerox Centre', User.Role.SHOP, {'phone': '9876543215'}),
    ('admin@coeptech.ac.in', 'Demo Admin', User.Role.ADMIN, {'is_staff': True, 'is_superuser': True}),
]


class Command(BaseCommand):
    help = 'Create demo locations and one demo account per role (local development only).'

    def handle(self, *args, **opts):
        password = os.environ.get('DEMO_PASSWORD', 'campus-demo-123')
        n = 0
        for building, floors in BUILDINGS.items():
            for floor, rooms in floors.items():
                for room in rooms:
                    _, created = Location.objects.get_or_create(building=building, floor=floor, classroom=room)
                    n += created
        self.stdout.write(f'Locations added: {n}')

        for email, name, role, extra in DEMO_USERS:
            if User.objects.filter(email=email).exists():
                continue
            User.objects.create_user(email=email, password=password, name=name, role=role, **extra)
            self.stdout.write(f'  {role:8} {email}')
        self.seed_shops()
        self.seed_hospitals()
        self.stdout.write(self.style.SUCCESS('Demo data ready. Password is DEMO_PASSWORD (see README).'))

    def seed_shops(self):
        shops = [
            ('shop@coeptech.ac.in', 'Gate Xerox & Stationery', 'Opposite COEP main gate', True),
            ('shop2@coeptech.ac.in', 'Library Copy Centre', 'Near Shivajinagar station', False),
        ]
        for email, name, location, is_open in shops:
            owner = User.objects.filter(email=email).first()
            if owner is None or Shop.objects.filter(owner=owner).exists():
                continue
            shop = Shop(owner=owner, name=name, location=location, phone=owner.phone, is_open=is_open)
            shop.qr_image.save('demo-qr.png', ContentFile(demo_qr_png()), save=False)
            shop.save()
            self.stdout.write(f'  shop     {name}')

    def seed_hospitals(self):
        # Names and rough distances only. Phone numbers are left blank on purpose:
        # an admin must add verified numbers before anyone relies on this page.
        hospitals = [
            ('Sancheti Hospital', 'Thube Park, Shivajinagar, Pune', '0.8', False),
            ('Sassoon General Hospital', 'Station Road, near Pune Railway Station, Pune', '2.5', True),
            ('Jehangir Hospital', 'Sassoon Road, near Pune Railway Station, Pune', '2.8', True),
            ('Ruby Hall Clinic', 'Sassoon Road, near Pune Railway Station, Pune', '3.2', True),
            ('Deenanath Mangeshkar Hospital', 'Erandwane, Pune', '4.5', True),
        ]
        n = 0
        for name, address, km, blood_bank in hospitals:
            _, created = Hospital.objects.get_or_create(
                name=name, defaults={'address': address, 'distance_km': km, 'has_blood_bank': blood_bank,
                                     'notes': 'Demo entry: verify the phone numbers and distance in admin.'})
            n += created
        self.stdout.write(f'Hospitals added: {n}')


def demo_qr_png():
    """A fake QR-looking image clearly marked as a demo, so nobody pays it."""
    img = Image.new('RGB', (330, 380), 'white')
    d = ImageDraw.Draw(img)
    for x in range(21):
        for y in range(21):
            if (x * 7 + y * 13 + x * y) % 3 == 0 or (x < 7 and y < 7) or (x > 13 and y < 7) or (x < 7 and y > 13):
                d.rectangle([25 + x * 13, 25 + y * 13, 37 + x * 13, 37 + y * 13], fill='black')
    d.rectangle([0, 310, 330, 380], fill='#c62828')
    d.text((60, 330), 'DEMO QR - DO NOT PAY', fill='white')
    buf = BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()
