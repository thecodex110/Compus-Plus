from django.utils import translation


class UserLanguageMiddleware:
    """Signed-in users get the language saved on their account, so the choice
    follows them across devices; only BVG staff and print shops may pick Hindi.
    Signed-out visitors use the cookie (LocaleMiddleware)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            translation.activate(user.ui_language)
            request.LANGUAGE_CODE = user.ui_language
        return self.get_response(request)
