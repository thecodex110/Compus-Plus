from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .models import User

R = User.Role

# (label, url name, icon, module hue) per role. Module decides the tab colour.
HOME = (_('Home'), 'home', 'home', '')
REQUESTS = (_('Requests'), 'services:mine', 'requests', 'req')
MARKET = (_('Market'), 'market:browse', 'market', 'mkt')
LOSTFOUND = (_('Lost & Found'), 'lostfound:feed', 'lostfound', 'lf')
PRINT = (_('Print'), 'printing:shops', 'print', 'print')
BLOOD = (_('Blood'), 'health:directory', 'blood', 'blood')

NAV = {
    R.STUDENT: [HOME, REQUESTS, MARKET, LOSTFOUND, PRINT],
    R.TEACHER: [HOME, REQUESTS, LOSTFOUND, BLOOD],
    R.BVG: [(_('Queue'), 'services:queue', 'queue', 'req'), (_('My jobs'), 'services:jobs', 'requests', 'req'),
            (_('History'), 'services:history', 'history', 'req'), (_('Hospitals'), 'health:hospitals', 'hospital', 'blood')],
    R.SHOP: [(_('Orders'), 'printing:shop_dashboard', 'print', 'print'),
             (_('Stationery'), 'printing:shop_stationery', 'pencil', 'print'),
             (_('Settings'), 'printing:shop_settings', 'settings', 'print')],
    R.ADMIN: [(_('Dashboard'), 'panel:dashboard', 'dashboard', ''), (_('Users'), 'panel:users', 'users', ''),
              (_('Requests'), 'services:history', 'requests', 'req'), (_('Moderate'), 'panel:moderate', 'shield', ''),
              (_('Campus'), 'panel:locations', 'campus', '')],
}

# URL prefix -> module hue for the page itself.
MODULES = [('/services/', 'req'), ('/lost-found/', 'lf'), ('/market/', 'mkt'), ('/print/', 'print'),
           ('/blood/', 'blood')]


def nav(request):
    path = request.path
    module = next((m for prefix, m in MODULES if path.startswith(prefix)), '')
    asset_file = getattr(settings, 'ASSET_VERSION_FILE', None)
    ctx = {'module': module, 'asset_v': int(asset_file.stat().st_mtime) if asset_file else ''}
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return ctx
    items = []
    for label, name, icon, hue in NAV.get(user.role, []):
        url = reverse(name)
        items.append({'label': label, 'url': url, 'icon': icon, 'hue': hue,
                      'current': path == url or (url != '/' and path.startswith(url))})
    # Only one tab is current: prefer the longest matching URL.
    current = [i for i in items if i['current']]
    if not current and module:
        # Inside a module page with no exact tab (e.g. a detail page): light the module's tab.
        current = [next((i for i in items if i['hue'] == module), None)]
        current = [c for c in current if c]
        for c in current:
            c['current'] = True
    if len(current) > 1:
        best = max(current, key=lambda i: len(i['url']))
        for i in items:
            i['current'] = i is best
    ctx.update({'nav_items': items, 'unread_count': user.notifications.filter(read=False).count()})
    return ctx
