"""Email backend for the Resend API (https://resend.com) - no extra package needed.

Supports Resend API key configured via environment variable (RESEND_API_KEY)
or dynamically in the Admin Console (CompanySetting)."""
import json
import logging
import urllib.request
import urllib.error

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend
from django.core.mail.backends.console import EmailBackend as ConsoleBackend

logger = logging.getLogger(__name__)


def _resolve_company_settings():
    try:
        from core.models import CompanySetting
        return CompanySetting.get_settings()
    except Exception:
        return None


def get_active_resend_key():
    cs = _resolve_company_settings()
    if cs and getattr(cs, 'resend_api_key', ''):
        key = cs.resend_api_key.strip()
        if key:
            return key
    return getattr(settings, 'RESEND_API_KEY', '').strip()


def get_active_from_email():
    cs = _resolve_company_settings()
    if cs and getattr(cs, 'sender_email', ''):
        em = cs.sender_email.strip()
        if em:
            return em
    from_setting = getattr(settings, 'DEFAULT_FROM_EMAIL', '').strip()
    if from_setting:
        return from_setting
    if cs:
        return f"{cs.site_name} <support@{cs.domain}>"
    return "Elvarion Holdings <support@elvarionholdings.com>"


class ResendEmailBackend(BaseEmailBackend):
    """Sends email via the Resend HTTPS API using standard library urllib."""

    def __init__(self, api_key=None, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = self.api_key or get_active_resend_key()
        if not api_key:
            err = "Resend API key is not configured. Set RESEND_API_KEY or configure it in the Admin Console."
            logger.error(err)
            if not self.fail_silently:
                raise ValueError(err)
            return 0

        default_from = get_active_from_email()
        sent = 0

        for m in email_messages:
            sender = m.from_email or default_from
            payload = {
                'from': sender,
                'to': list(m.to),
                'subject': m.subject,
                'text': m.body or '',
            }
            if m.cc:
                payload['cc'] = list(m.cc)
            if m.bcc:
                payload['bcc'] = list(m.bcc)
            if m.reply_to:
                payload['reply_to'] = list(m.reply_to)

            for body, mime in getattr(m, 'alternatives', []):
                if mime == 'text/html':
                    payload['html'] = body

            # If no html alternative provided but body starts with markup
            if 'html' not in payload and payload['text'].lstrip().startswith(('<html', '<!DOCTYPE', '<div')):
                payload['html'] = payload['text']

            # Attachments support
            attachments = []
            for attachment in getattr(m, 'attachments', []):
                try:
                    import base64
                    if isinstance(attachment, tuple):
                        filename, content, _mimetype = attachment
                        if isinstance(content, str):
                            content = content.encode('utf-8')
                        attachments.append({
                            'filename': filename,
                            'content': base64.b64encode(content).decode('ascii'),
                        })
                except Exception as att_err:
                    logger.warning("Could not encode attachment: %s", att_err)
            if attachments:
                payload['attachments'] = attachments

            req = urllib.request.Request(
                'https://api.resend.com/emails',
                data=json.dumps(payload).encode('utf-8'),
                method='POST',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'ElvarionHoldings/1.0 (https://elvarionholdings.com)',
                }
            )

            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    resp_body = resp.read().decode('utf-8')
                    logger.info("Resend sent successfully: %s", resp_body)
                    sent += 1
            except urllib.error.HTTPError as e:
                err_body = ''
                try:
                    err_body = e.read().decode('utf-8', errors='ignore')
                    err_json = json.loads(err_body)
                    resend_msg = err_json.get('message', err_body)
                except Exception:
                    resend_msg = err_body or str(e)
                error_text = f"Resend API error ({e.code}): {resend_msg}"
                logger.error(error_text)
                if not self.fail_silently:
                    raise RuntimeError(error_text) from e
            except (urllib.error.URLError, OSError) as e:
                error_text = f"Resend connection failed: {e}"
                logger.error(error_text)
                if not self.fail_silently:
                    raise RuntimeError(error_text) from e

        return sent


class ConfiguredEmailBackend(BaseEmailBackend):
    """Dynamically routes emails to Resend, SMTP, or Console based on active settings."""

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        import sys
        if 'test' in sys.argv:
            from django.core.mail.backends.locmem import EmailBackend as LocmemBackend
            return LocmemBackend(fail_silently=self.fail_silently).send_messages(email_messages)

        # Check Resend first (Admin setting or ENV)
        resend_key = get_active_resend_key()
        if resend_key:
            backend = ResendEmailBackend(api_key=resend_key, fail_silently=self.fail_silently)
            return backend.send_messages(email_messages)

        # Check SMTP settings (Admin setting or ENV)
        cs = _resolve_company_settings()
        host = (cs.smtp_host if cs and cs.smtp_host else getattr(settings, 'EMAIL_HOST', '')).strip()
        if host:
            port = cs.smtp_port if cs and cs.smtp_port else getattr(settings, 'EMAIL_PORT', 587)
            user = cs.smtp_user if cs and cs.smtp_user else getattr(settings, 'EMAIL_HOST_USER', '')
            pwd = cs.smtp_password if cs and cs.smtp_password else getattr(settings, 'EMAIL_HOST_PASSWORD', '')
            use_tls = cs.smtp_use_tls if cs and cs.smtp_host else getattr(settings, 'EMAIL_USE_TLS', True)
            backend = SmtpBackend(
                host=host, port=port, username=user, password=pwd,
                use_tls=use_tls, fail_silently=self.fail_silently
            )
            return backend.send_messages(email_messages)

        # Fallback to console backend
        backend = ConsoleBackend(fail_silently=self.fail_silently)
        return backend.send_messages(email_messages)
