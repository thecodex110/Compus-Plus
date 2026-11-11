"""The five lines people log in on: shown on the welcome page and as tabs on the login page."""
from django.utils.translation import gettext_lazy as _

from .models import User

LINES = [
    {
        'id': User.Role.STUDENT, 'label': _('Student'), 'colour': '#3b5bdb', 'tint': '#e8edff', 'icon': 'student',
        'title': _('Hello, student.'),
        'blurb': _('Raise help, post Lost & Found, buy and sell, order prints.'),
        'perks': [_('Medical and Security in two taps'), _('Sell old books to juniors'),
                  _('Prints delivered to Main Gate or Library')],
        'signup': True,
    },
    {
        'id': User.Role.TEACHER, 'label': _('Teacher'), 'colour': '#12857a', 'tint': '#e2f5f0', 'icon': 'teacher',
        'title': _('Welcome, Professor.'),
        'blurb': _('Get a projector remote, cleaning or security sent to your classroom.'),
        'perks': [_('Requests go straight to BVG staff'), _('See every step live'), _('Search blood donors fast')],
        'signup': True,
    },
    {
        'id': User.Role.BVG, 'label': _('BVG Staff'), 'colour': '#c8371f', 'tint': '#fdeae4', 'icon': 'security',
        'title': _('Your queue is ready.'),
        'blurb': _('See the queue, accept a request, mark it done.'),
        'perks': [_('Urgent requests always on top'), _('Big buttons, works in Hindi'), _('Room and floor on every job')],
        'signup': False,
    },
    {
        'id': User.Role.SHOP, 'label': _('Print Shop'), 'colour': '#8a5a00', 'tint': '#fff6e5', 'icon': 'print',
        'title': _('Orders are waiting.'),
        'blurb': _('Check payment proof, print, send to the gate.'),
        'perks': [_('Payment screenshot and last digits'), _('Open or close your shop in one tap'),
                  _('Files delete after delivery')],
        'signup': False,
    },
    {
        'id': User.Role.ADMIN, 'label': _('Admin'), 'colour': '#121630', 'tint': '#e9eaf5', 'icon': 'dashboard',
        'title': _('Run the campus.'),
        'blurb': _('Manage people, rooms, shops and hospitals.'),
        'perks': [_('Add staff, shops and admins'), _('Edit buildings, floors and rooms'),
                  _('Moderate Lost & Found and Market')],
        'signup': False,
    },
]

BY_ID = {line['id']: line for line in LINES}


def line_for(role_id):
    return BY_ID.get(role_id, LINES[0])


def matches(user, role_id):
    """True when `user` belongs on the login tab `role_id`."""
    if role_id == User.Role.ADMIN:
        return user.is_admin_role
    return user.role == role_id
