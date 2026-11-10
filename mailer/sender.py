"""
mailer/sender.py
~~~~~~~~~~~~~~~~
Core send function that wraps the Resend HTTP API (stdlib only — no extra packages).
Logs every dispatch to EmailLog. Reads API key from CompanySetting DB first,
then falls back to RESEND_API_KEY env var, then to Django console backend.
"""
import json
import logging
import re as _re
import urllib.error
import urllib.request
from html.parser import HTMLParser

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"
USER_AGENT     = "ElvarionHoldings-Mailer/1.0 (https://elvarionholdings.com)"


# ── helpers ────────────────────────────────────────────────────────────────────

class _StripHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def html_to_text(html: str) -> str:
    """Convert HTML to plain text (best-effort strip)."""
    p = _StripHTML()
    p.feed(html)
    text = p.get_text()
    # Collapse whitespace
    text = _re.sub(r'\s+', ' ', text).strip()
    return text


def _get_api_key() -> str:
    """Return active Resend API key: DB → env → empty."""
    try:
        from core.models import CompanySetting
        cs = CompanySetting.objects.filter(id=1).first()
        if cs and cs.resend_api_key:
            return cs.resend_api_key.strip()
    except Exception:
        pass
    return getattr(settings, 'RESEND_API_KEY', '').strip()


def _get_from_email() -> str:
    """Return active sender address: DB → env → default."""
    try:
        from core.models import CompanySetting
        cs = CompanySetting.objects.filter(id=1).first()
        if cs and cs.sender_email:
            return cs.sender_email.strip()
    except Exception:
        pass
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'Elvarion Holdings <support@elvarionholdings.com>')


def _apply_placeholders(text: str, context: dict) -> str:
    """Replace {{key}} placeholders in text with context values."""
    for k, v in context.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text


# ── main send function ─────────────────────────────────────────────────────────

def send_email(
    to_address:  str,
    subject:     str,
    body_html:   str,
    *,
    to_name:     str  = "",
    body_text:   str  = "",
    reply_to:    str  = "",
    cc:          list = None,
    sent_by:     str  = "system",
    template=None,
    broadcast=None,
    context:     dict = None,
) -> "EmailLog":
    """
    Send a single email via Resend and log the result.

    Returns the saved EmailLog instance.
    """
    from mailer.models import EmailLog

    # Apply placeholder substitution
    if context:
        body_html = _apply_placeholders(body_html, context)
        subject   = _apply_placeholders(subject, context)
        if body_text:
            body_text = _apply_placeholders(body_text, context)

    if not body_text:
        body_text = html_to_text(body_html)

    log = EmailLog(
        to_address=to_address,
        to_name=to_name,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        reply_to=reply_to,
        cc=", ".join(cc) if cc else "",
        sent_by=sent_by,
        template=template,
        broadcast=broadcast,
    )

    api_key = _get_api_key()
    from_addr = _get_from_email()

    if not api_key:
        # Fallback: log to console and mark failed
        logger.warning("[Mailer] No Resend API key configured. Email not sent: %s → %s", subject, to_address)
        log.status = EmailLog.STATUS_FAILED
        log.error_msg = "No Resend API key configured. Set it in Admin → Email & Resend panel."
        log.save()
        return log

    # Build recipient with optional display name
    to_field = f"{to_name} <{to_address}>" if to_name else to_address

    payload = {
        "from":    from_addr,
        "to":      [to_field],
        "subject": subject,
        "html":    body_html,
        "text":    body_text,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    if cc:
        payload["cc"] = cc

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(RESEND_API_URL, data=data, method="POST")
    req.add_header("Authorization",  f"Bearer {api_key}")
    req.add_header("Content-Type",   "application/json")
    req.add_header("User-Agent",     USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            log.resend_id = result.get("id", "")
            log.status    = EmailLog.STATUS_SENT
            logger.info("[Mailer] Sent OK id=%s subject=%r to=%s", log.resend_id, subject, to_address)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        log.status    = EmailLog.STATUS_FAILED
        log.error_msg = f"HTTP {exc.code}: {body}"
        logger.error("[Mailer] Resend HTTP %s: %s  subject=%r to=%s", exc.code, body, subject, to_address)
    except Exception as exc:
        log.status    = EmailLog.STATUS_FAILED
        log.error_msg = str(exc)
        logger.exception("[Mailer] Unexpected error sending email subject=%r to=%s", subject, to_address)

    log.save()
    return log


# ── broadcast helper ───────────────────────────────────────────────────────────

def send_broadcast(broadcast_id: int, sent_by: str = "system") -> "Broadcast":
    """
    Dispatch a saved Broadcast to all resolved recipients.
    Updates Broadcast.status, total_sent, total_failed, sent_at.
    """
    from django.contrib.auth.models import User
    from mailer.models import Broadcast

    bc = Broadcast.objects.get(pk=broadcast_id)

    # Resolve recipients
    if bc.audience == Broadcast.AUDIENCE_ALL:
        users = User.objects.filter(is_active=True, is_staff=False)
    elif bc.audience == Broadcast.AUDIENCE_VERIFIED:
        users = User.objects.filter(is_active=True, is_staff=False, profile__email_verified=True)
    elif bc.audience == Broadcast.AUDIENCE_ACTIVE:
        # Investors who have at least one portfolio entry
        try:
            from core.models import Portfolio
            investor_ids = Portfolio.objects.values_list('user_id', flat=True).distinct()
            users = User.objects.filter(pk__in=investor_ids, is_active=True)
        except Exception:
            users = User.objects.filter(is_active=True, is_staff=False)
    else:
        # Custom list
        users = []

    sent = failed = 0

    # Send to resolved user accounts
    for user in users:
        ctx = {
            "first_name": user.first_name or user.username,
            "last_name":  user.last_name,
            "email":      user.email,
            "username":   user.username,
        }
        log = send_email(
            to_address=user.email,
            subject=bc.subject,
            body_html=bc.body_html,
            to_name=f"{user.first_name} {user.last_name}".strip() or user.username,
            body_text=bc.body_text,
            sent_by=sent_by,
            template=bc.template,
            broadcast=bc,
            context=ctx,
        )
        if log.status == "sent":
            sent += 1
        else:
            failed += 1

    # Custom email list (plain addresses, no user record needed)
    if bc.audience == Broadcast.AUDIENCE_CUSTOM:
        for addr in bc.custom_emails.split(","):
            addr = addr.strip()
            if not addr:
                continue
            log = send_email(
                to_address=addr,
                subject=bc.subject,
                body_html=bc.body_html,
                body_text=bc.body_text,
                sent_by=sent_by,
                template=bc.template,
                broadcast=bc,
            )
            if log.status == "sent":
                sent += 1
            else:
                failed += 1

    bc.total_sent   = sent
    bc.total_failed = failed
    bc.status       = Broadcast.STATUS_SENT if sent > 0 else Broadcast.STATUS_FAILED
    bc.sent_at      = timezone.now()
    bc.save()
    return bc
