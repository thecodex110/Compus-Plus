import os

from django.core.management.base import BaseCommand

from accounts.models import User
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
        self.stdout.write(self.style.SUCCESS('Demo data ready. Password is DEMO_PASSWORD (see README).'))
