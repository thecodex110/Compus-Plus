from django.urls import reverse

from .models import User

R = User.Role

# Bottom-nav links per role. Each module adds its entries as it is built.
NAV = {
    R.STUDENT: [('Home', 'home'), ('Request', 'services:new'), ('Lost & Found', 'lostfound:feed'), ('My requests', 'services:mine')],
    R.TEACHER: [('Home', 'home'), ('Request', 'services:new'), ('Lost & Found', 'lostfound:feed'), ('My requests', 'services:mine')],
    R.BVG: [('Queue', 'services:queue'), ('My jobs', 'services:jobs'), ('History', 'services:history')],
    R.SHOP: [('Home', 'home')],
    R.ADMIN: [('Home', 'home'), ('All requests', 'services:history'), ('Lost & Found', 'lostfound:feed')],
}


def nav(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    items = [(label, reverse(name)) for label, name in NAV.get(user.role, [])]
    return {'nav_items': items}
