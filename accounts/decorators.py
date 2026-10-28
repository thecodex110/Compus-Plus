from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
