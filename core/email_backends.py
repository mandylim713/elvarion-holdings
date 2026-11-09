"""Email backend for the Resend API (https://resend.com) - no extra package needed.

Set RESEND_API_KEY and DEFAULT_FROM_EMAIL (a sender on a domain you verified in Resend)."""
import json
import urllib.request
import urllib.error

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend


class ResendEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for m in email_messages:
            payload = {'from': m.from_email or settings.DEFAULT_FROM_EMAIL, 'to': list(m.to), 'subject': m.subject, 'text': m.body}
            for body, mime in getattr(m, 'alternatives', []):
                if mime == 'text/html':
                    payload['html'] = body
            if m.reply_to:
                payload['reply_to'] = list(m.reply_to)
            req = urllib.request.Request(
                'https://api.resend.com/emails', data=json.dumps(payload).encode(), method='POST',
                headers={'Authorization': f'Bearer {settings.RESEND_API_KEY}', 'Content-Type': 'application/json',
                         'User-Agent': 'elvarion-holdings/1.0'})
            try:
                urllib.request.urlopen(req, timeout=10).read()
                sent += 1
            except (urllib.error.URLError, OSError) as e:
                if not self.fail_silently:
                    raise
        return sent
