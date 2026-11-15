"""Email one-time codes (sign-up verification, sign-in, password reset) and notification emails."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from .models import EmailOTP, CompanySetting
from .email_backends import get_active_resend_key, get_active_from_email

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
    """True if either Resend API or SMTP is configured via CompanySetting or environment."""
    try:
        cs = CompanySetting.get_settings()
        if cs.is_email_configured():
            return True
    except Exception:
        pass
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
    cs = CompanySetting.get_settings()
    name = cs.site_name or 'Elvarion Holdings'
    return f"""<div style="background:#f4f1ea;padding:32px 12px;font-family:Arial,Helvetica,sans-serif">
<div style="max-width:480px;margin:0 auto;background:#fff;border:1px solid #e5dcc8;border-radius:12px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,0.04)">
<div style="background:#0a1424;color:#d9c08a;padding:22px;text-align:center;font-family:Georgia,serif;font-size:22px;letter-spacing:3px">{name.upper()}</div>
<div style="padding:30px 28px;color:#1b2434">
<h2 style="margin:0 0 10px;font-family:Georgia,serif;font-weight:600">{title}</h2>
<p style="margin:0 0 22px;line-height:1.6;color:#4a5568">{intro}</p>
<div style="text-align:center;font-size:34px;letter-spacing:10px;font-weight:700;background:#f4f1ea;border-radius:10px;padding:16px 0;color:#0a1424">{code}</div>
<p style="margin:22px 0 0;font-size:13px;color:#718096;line-height:1.6">This code expires in {minutes} minutes. If you did not ask for it you can ignore this email - nobody can use it without your password.</p>
</div></div></div>"""


def _brand_notification_html(title, message, cta_url=None, cta_text=None):
    cs = CompanySetting.get_settings()
    name = cs.site_name or 'Elvarion Holdings'
    domain = cs.domain or 'elvarionholdings.com'
    button_html = ''
    if cta_url and cta_text:
        button_html = f"""<div style="text-align:center;margin:26px 0 10px">
<a href="{cta_url}" style="background:#0a1424;color:#d9c08a;text-decoration:none;padding:12px 28px;border-radius:8px;font-weight:600;display:inline-block;border:1px solid #c9aa66;font-size:14px;letter-spacing:1px">{cta_text}</a>
</div>"""
    return f"""<div style="background:#f4f1ea;padding:32px 12px;font-family:Arial,Helvetica,sans-serif">
<div style="max-width:520px;margin:0 auto;background:#fff;border:1px solid #e5dcc8;border-radius:12px;overflow:hidden;box-shadow:0 4px 18px rgba(0,0,0,0.04)">
<div style="background:#0a1424;color:#d9c08a;padding:22px;text-align:center;font-family:Georgia,serif;font-size:20px;letter-spacing:3px">{name.upper()}</div>
<div style="padding:30px 28px;color:#1b2434">
<h2 style="margin:0 0 14px;font-family:Georgia,serif;font-weight:600;font-size:20px;color:#0a1424">{title}</h2>
<div style="margin:0 0 20px;line-height:1.7;color:#374151;font-size:15px;white-space:pre-line">{message}</div>
{button_html}
<div style="margin-top:28px;padding-top:18px;border-top:1px solid #f0e9dc;font-size:12px;color:#8c95a6;line-height:1.5">
This is an institutional transmission from {name} ({domain}). If you require assistance, contact our executive concierge at {cs.support_email}.
</div></div></div></div>"""


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
    cs = CompanySetting.get_settings()
    name = cs.site_name or 'Elvarion Holdings'
    from_email = cs.get_sender_email()
    msg = EmailMultiAlternatives(f"{code} is your {name} code", f"{title}\n\n{intro}\n\nCode: {code}\nIt expires in {CODE_TTL} minutes.",
                                 from_email, [user.email])
    msg.attach_alternative(_brand_html(title, intro, code, CODE_TTL), 'text/html')
    try:
        msg.send()
    except Exception as e:
        print('[otp] email failed:', e)
        return False, 0, f'We could not send the email right now ({e}). Please try again in a moment.'
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


def notify(user, subject, message, cta_url=None, cta_text=None):
    """Institutional notification email, sent to an investor."""
    try:
        if not (email_configured() and user.email and getattr(user.profile, 'email_notifications', True)):
            return
        cs = CompanySetting.get_settings()
        name = cs.site_name or 'Elvarion Holdings'
        from_email = cs.get_sender_email()
        msg = EmailMultiAlternatives(f"{subject} | {name}", f"{subject}\n\n{message}\n\n{name}", from_email, [user.email])
        msg.attach_alternative(_brand_notification_html(subject, message, cta_url, cta_text), 'text/html')
        msg.send(fail_silently=True)
    except Exception as e:
        print('[otp notify] failed:', e)


def notify_admin(subject, message, cta_url=None):
    """Send immediate alert to company administrator(s) when transactions, KYC, or loans occur."""
    try:
        if not email_configured():
            return
        from django.contrib.auth.models import User
        cs = CompanySetting.get_settings()
        recipients = []
        if cs.admin_email:
            recipients.append(cs.admin_email.strip())
        else:
            staff_emails = list(User.objects.filter(is_staff=True, is_active=True).exclude(email='').values_list('email', flat=True))
            if staff_emails:
                recipients.extend(staff_emails)

        if not recipients:
            return

        name = cs.site_name or 'Elvarion Holdings'
        from_email = cs.get_sender_email()
        cta_text = "Review in Admin Console" if cta_url else None
        msg = EmailMultiAlternatives(f"[ADMIN ALERT] {subject} - {name}", f"ADMIN ALERT:\n\n{subject}\n\n{message}", from_email, recipients)
        msg.attach_alternative(_brand_notification_html(f"Admin Alert: {subject}", message, cta_url, cta_text), 'text/html')
        msg.send(fail_silently=True)
    except Exception as e:
        print('[otp notify_admin] failed:', e)


def send_test_email(to_email):
    """Send a live test message to verify Resend or mail backend delivery."""
    cs = CompanySetting.get_settings()
    name = cs.site_name or 'Elvarion Holdings'
    key = cs.get_resend_api_key()
    provider = "Resend API" if key else "Configured SMTP Mailer"
    from_email = cs.get_sender_email()

    subject = f"Resend Connection Test - {name}"
    body = (
        f"Congratulations!\n\n"
        f"Your mailing system ({provider}) is successfully connected to {cs.domain}.\n\n"
        f"Active Sender: {from_email}\n"
        f"Recipient: {to_email}\n"
        f"Server Timestamp: {timezone.now():%Y-%m-%d %H:%M:%S UTC}\n"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=from_email,
        to=[to_email]
    )
    msg.attach_alternative(
        _brand_notification_html(
            "Resend Email System Connected",
            f"Your Resend mailing system has been verified and is operational for <strong>{cs.domain}</strong>.<br><br>"
            f"<strong>Sender:</strong> {from_email}<br>"
            f"<strong>Provider:</strong> {provider}<br><br>"
            f"Your platform is now equipped to seamlessly deliver investor OTP verification codes, deposit receipts, withdrawal updates, and instant administrator alerts.",
            cta_url=f"https://{cs.domain}/management/#email",
            cta_text="Open Admin Console"
        ),
        'text/html'
    )
    msg.send(fail_silently=False)
    return True, f"Test email successfully dispatched to {to_email} via {provider}."
