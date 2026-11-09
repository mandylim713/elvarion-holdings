from django.shortcuts import redirect

from . import otp

OPEN_PREFIXES = ('/verify-email', '/auth/', '/logout', '/static/', '/media/', '/login', '/register',
                 '/forgot-password', '/reset-password', '/cron/', '/management', '/robots.txt', '/privacy', '/terms')


class EmailVerificationMiddleware:
    """Investors must confirm their email with a code before using the portal (when codes can be sent)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        u = request.user
        if u.is_authenticated and not u.is_staff and not request.path.startswith(OPEN_PREFIXES) and request.path != '/':
            try:
                verified = u.profile.email_verified
            except Exception:
                verified = True
            if not verified and otp.verification_enforced():
                return redirect('verify_email')
        return self.get_response(request)


class WwwRedirectMiddleware:
    """www.elvarionholdings.com -> elvarionholdings.com (one canonical address)"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()
        if host == 'www.elvarionholdings.com':
            from django.http import HttpResponsePermanentRedirect
            return HttpResponsePermanentRedirect('https://elvarionholdings.com' + request.get_full_path())
        return self.get_response(request)
