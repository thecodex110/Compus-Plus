from django.urls import reverse

from .models import User

R = User.Role

# Bottom-nav links per role. Each module adds its entries as it is built.
NAV = {
    R.STUDENT: [('Home', 'home'), ('Requests', 'services:mine'), ('Market', 'market:browse'), ('Lost & Found', 'lostfound:feed'), ('Print', 'printing:shops')],
    R.TEACHER: [('Home', 'home'), ('Requests', 'services:mine'), ('Lost & Found', 'lostfound:feed')],
    R.BVG: [('Queue', 'services:queue'), ('My jobs', 'services:jobs'), ('History', 'services:history')],
    R.SHOP: [('Orders', 'printing:shop_dashboard'), ('Settings', 'printing:shop_settings')],
    R.ADMIN: [('Home', 'home'), ('All requests', 'services:history'), ('Lost & Found', 'lostfound:feed'), ('Market', 'market:browse')],
}


def nav(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    items = [(label, reverse(name)) for label, name in NAV.get(user.role, [])]
    return {'nav_items': items}
