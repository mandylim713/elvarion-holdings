"""Email one-time codes (sign-up verification, sign-in, password reset) and notification emails."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import EmailOTP, CompanySetting

CODE_TTL = 10          # minutes
RESEND_WAIT = 60       # seconds between codes
MAX_PER_HOUR = 6
MAX_ATTEMPTS = 5

PURPOSE_TEXT = {
    'verify': ('Confirm your email', 'Use this code to confirm your email address.'),
    'login': ('Your sign-in code', 'Use this code to finish signing in.'),
    'reset': ('Reset your password', 'Use this code to choose a new password.'),
}


def email_configured():
    return bool(getattr(settings, 'RESEND_API_KEY', '') or getattr(settings, 'EMAIL_HOST', ''))


def codes_available():
    """Codes can be sent (a real email service is set up) - or we are in local development."""
    return email_configured() or settings.DEBUG


def verification_enforced():
    return codes_available() and CompanySetting.get_settings().require_email_verification


def _hash(user, purpose, code):
    msg = f"{user.id}:{purpose}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def wait_seconds(user, purpose):
    last = EmailOTP.objects.filter(user=user, purpose=purpose).first()
    if not last:
        return 0
    left = RESEND_WAIT - (timezone.now() - last.created_at).total_seconds()
    return max(0, int(left + 0.999))


def _brand_html(title, intro, code, minutes):
    name = CompanySetting.get_settings().site_name
    return f"""<div style="background:#f4f1ea;padding:32px 12px;font-family:Arial,Helvetica,sans-serif">
<div style="max-width:480px;margin:0 auto;background:#fff;border:1px solid #e5dcc8;border-radius:12px;overflow:hidden">
<div style="background:#0a1424;color:#d9c08a;padding:22px;text-align:center;font-family:Georgia,serif;font-size:22px;letter-spacing:3px">{name.upper()}</div>
<div style="padding:30px 28px;color:#1b2434">
<h2 style="margin:0 0 10px;font-family:Georgia,serif;font-weight:600">{title}</h2>
<p style="margin:0 0 22px;line-height:1.6;color:#4a5568">{intro}</p>
<div style="text-align:center;font-size:34px;letter-spacing:10px;font-weight:700;background:#f4f1ea;border-radius:10px;padding:16px 0;color:#0a1424">{code}</div>
<p style="margin:22px 0 0;font-size:13px;color:#718096;line-height:1.6">This code expires in {minutes} minutes. If you did not ask for it you can ignore this email - nobody can use it without your password.</p>
</div></div></div>"""


def send_code(user, purpose):
    """Create and email a code. Returns (ok, wait_seconds, message)."""
    if not user.email:
        return False, 0, 'This account has no email address.'
    wait = wait_seconds(user, purpose)
    if wait:
        return False, wait, f'Please wait {wait} seconds before asking for another code.'
    since = timezone.now() - timedelta(hours=1)
    if EmailOTP.objects.filter(user=user, created_at__gte=since).count() >= MAX_PER_HOUR:
        return False, 600, 'Too many codes requested. Please try again later.'
    EmailOTP.objects.filter(user=user, purpose=purpose, used=False).update(used=True)
    code = f"{secrets.randbelow(1000000):06d}"
    EmailOTP.objects.create(user=user, purpose=purpose, code_hash=_hash(user, purpose, code),
                            expires_at=timezone.now() + timedelta(minutes=CODE_TTL))
    title, intro = PURPOSE_TEXT[purpose]
    name = CompanySetting.get_settings().site_name
    msg = EmailMultiAlternatives(f"{code} is your {name} code", f"{title}\n\n{intro}\n\nCode: {code}\nIt expires in {CODE_TTL} minutes.",
                                 settings.DEFAULT_FROM_EMAIL, [user.email])
    msg.attach_alternative(_brand_html(title, intro, code, CODE_TTL), 'text/html')
    try:
        msg.send()
    except Exception as e:
        print('[otp] email failed:', e)
        return False, 0, 'We could not send the email right now. Please try again in a moment.'
    if not email_configured():
        print(f"[otp] (no email service configured) code for {user.email} / {purpose}: {code}")
    return True, RESEND_WAIT, f'We sent a 6-digit code to {mask_email(user.email)}.'


def check_code(user, purpose, code):
    code = (code or '').strip().replace(' ', '')
    otp = EmailOTP.objects.filter(user=user, purpose=purpose, used=False).first()
    if not otp or otp.expires_at < timezone.now() or not code.isdigit():
        return False
    otp.attempts += 1
    if otp.attempts > MAX_ATTEMPTS:
        otp.used = True
        otp.save()
        return False
    ok = hmac.compare_digest(otp.code_hash, _hash(user, purpose, code))
    if ok:
        otp.used = True
    otp.save()
    return ok


def mask_email(email):
    name, _, domain = email.partition('@')
    return (name[:2] + '***' if len(name) > 2 else name[:1] + '***') + '@' + domain


def notify(user, subject, message):
    """Plain notification email, if the investor allows it and email is set up."""
    try:
        if not (email_configured() and user.email and user.profile.email_notifications):
            return
        name = CompanySetting.get_settings().site_name
        EmailMultiAlternatives(f"{subject} - {name}", message, settings.DEFAULT_FROM_EMAIL, [user.email]).send(fail_silently=True)
    except Exception:
        pass
