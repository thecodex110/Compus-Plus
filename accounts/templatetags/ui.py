from django import template
from django.utils.html import format_html

register = template.Library()


@register.simple_tag
def icon(name, cls=''):
    """Inline a line icon from templates/_icons.html: {% icon "medical" %}."""
    return format_html('<svg class="i {}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
                       '<use href="#i-{}"></use></svg>', cls, name)


@register.filter
def sheet_no(obj, prefix):
    """REQ-0042 style record numbers: {{ sr|sheet_no:'REQ' }}."""
    return f'{prefix}-{obj.pk:04d}' if getattr(obj, 'pk', None) else prefix


# Status value -> stamp colour, shared by every module.
STAMP = {
    'pending': 'wait', 'draft': 'wait', 'placed': 'wait',
    'accepted': 'go', 'verified': 'go', 'available': 'go', 'open': 'go',
    'in_progress': 'move', 'printing': 'move', 'out': 'move',
    'done': 'done', 'delivered': 'done', 'returned': 'done', 'sold': 'done',
    'rejected': 'stop',
    'cancelled': 'void', 'removed': 'void',
}


@register.filter
def stamp(status):
    return f'st-{STAMP.get(str(status), "go")}'


SEPARATORS = ('&nbsp;· ', '\xa0· ')


class SegmentsNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        html = self.nodelist.render(context).strip()
        for sep in SEPARATORS[1:]:
            html = html.replace(sep, SEPARATORS[0])
        parts = [p.strip() for p in html.split(SEPARATORS[0]) if p.strip()]
        if len(parts) < 2:
            return html
        inner = ''.join(f'<span class="seg">{p}</span>' for p in parts)
        return f'<span class="segs"><span class="segs-in">{inner}</span></span>'


@register.tag
def segs(parser, token):
    """{% segs %}a · b · c{% endsegs %}: meta-line pieces whose dot separators never
    hang at the end or start of a wrapped line (see .segs in app.css)."""
    nodelist = parser.parse(('endsegs',))
    parser.delete_first_token()
    return SegmentsNode(nodelist)
