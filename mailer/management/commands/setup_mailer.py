"""
management command: python manage.py setup_mailer

Runs automatically in build.sh on every Render deploy.
Seeds CompanySetting with Resend API key + email config from environment variables.
Also creates default email templates if none exist.
Safe to run multiple times (idempotent).
"""
import os
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Seed Resend API key and default email templates into the database.'

    def handle(self, *args, **options):
        self.stdout.write('[mailer] Running setup_mailer...')

        # ── 1. Seed CompanySetting with Resend credentials ───────────────────
        tables = connection.introspection.table_names()
        if 'core_companysetting' not in tables:
            self.stdout.write(self.style.WARNING(
                '[mailer] core_companysetting table not found — skipping email config seed.'
            ))
        else:
            from core.models import CompanySetting
            cs, created = CompanySetting.objects.get_or_create(id=1)

            env_key    = os.environ.get('RESEND_API_KEY', '').strip()
            env_from   = os.environ.get('DEFAULT_FROM_EMAIL',
                                        'Elvarion Holdings <support@elvarionholdings.com>').strip()
            env_admin  = 'support@elvarionholdings.com'

            changed = False
            # Always update from env if env has a value (env is authoritative)
            if env_key and cs.resend_api_key != env_key:
                cs.resend_api_key = env_key
                changed = True
            if not cs.sender_email:
                cs.sender_email = env_from
                changed = True
            if not cs.admin_email:
                cs.admin_email = env_admin
                changed = True
            if not cs.site_name:
                cs.site_name = 'Elvarion Holdings'
                cs.domain    = 'elvarionholdings.com'
                cs.support_email = env_admin
                changed = True

            if changed:
                cs.save()
                self.stdout.write(self.style.SUCCESS(
                    f'[mailer] CompanySetting updated — resend_api_key={"SET" if cs.resend_api_key else "EMPTY"}'
                ))
            else:
                self.stdout.write('[mailer] CompanySetting already configured — no changes.')

        # ── 2. Seed default email templates ──────────────────────────────────
        if 'mailer_emailtemplate' not in tables:
            self.stdout.write(self.style.WARNING(
                '[mailer] mailer_emailtemplate table not found — skipping template seed.'
            ))
            return

        from mailer.models import EmailTemplate

        defaults = [
            {
                'name': 'Welcome — Investor Onboarding',
                'subject': 'Welcome to Elvarion Holdings, {{first_name}}!',
                'body_html': """<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:32px;border:1px solid #e8e8e8;border-radius:8px">
  <div style="text-align:center;margin-bottom:28px">
    <h1 style="color:#1a1a2e;font-size:24px;margin:0">Elvarion Holdings</h1>
    <p style="color:#888;font-size:13px;margin:4px 0">Institutional Investment Platform</p>
  </div>
  <h2 style="color:#4f46e5;font-size:18px">Welcome, {{first_name}}!</h2>
  <p style="color:#374151;line-height:1.7">
    Your Elvarion Holdings investor account is now active. You have access to our full suite
    of institutional investment products — real estate, commodities, private equity, and more.
  </p>
  <div style="background:#f8faff;border-left:4px solid #4f46e5;padding:16px 20px;border-radius:4px;margin:20px 0">
    <b>Your Account</b><br>
    Email: {{email}}<br>
    Username: {{username}}
  </div>
  <div style="text-align:center;margin:28px 0">
    <a href="https://elvarionholdings.com/dashboard/"
       style="background:#4f46e5;color:#fff;padding:13px 32px;border-radius:6px;text-decoration:none;font-weight:600;font-size:15px">
      Go to Dashboard
    </a>
  </div>
  <p style="color:#6b7280;font-size:13px">
    If you have any questions, reply to this email or visit our support centre at
    <a href="https://elvarionholdings.com" style="color:#4f46e5">elvarionholdings.com</a>.
  </p>
  <hr style="border:1px solid #e8e8e8;margin:28px 0">
  <p style="font-size:11px;color:#9ca3af;text-align:center">
    Elvarion Holdings &bull; Tower 49, 12 East 49th Street, New York, NY 10017<br>
    This is a system-generated message. Do not reply directly to this address.
  </p>
</div>""",
            },
            {
                'name': 'Deposit Confirmed',
                'subject': 'Deposit Confirmed — Elvarion Holdings',
                'body_html': """<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:32px;border:1px solid #e8e8e8;border-radius:8px">
  <div style="text-align:center;margin-bottom:28px">
    <h1 style="color:#1a1a2e;font-size:24px;margin:0">Elvarion Holdings</h1>
    <p style="color:#888;font-size:13px;margin:4px 0">Institutional Investment Platform</p>
  </div>
  <h2 style="color:#22c55e;font-size:18px">Deposit Confirmed</h2>
  <p style="color:#374151;line-height:1.7">Dear {{first_name}},</p>
  <p style="color:#374151;line-height:1.7">
    Your deposit has been received and confirmed. The funds will be allocated to your
    portfolio within 1-2 business days.
  </p>
  <div style="text-align:center;margin:28px 0">
    <a href="https://elvarionholdings.com/dashboard/"
       style="background:#22c55e;color:#fff;padding:13px 32px;border-radius:6px;text-decoration:none;font-weight:600">
      View Portfolio
    </a>
  </div>
  <hr style="border:1px solid #e8e8e8;margin:28px 0">
  <p style="font-size:11px;color:#9ca3af;text-align:center">Elvarion Holdings &bull; Tower 49, New York, NY 10017</p>
</div>""",
            },
            {
                'name': 'Monthly Portfolio Update',
                'subject': 'Your Monthly Portfolio Report — Elvarion Holdings',
                'body_html': """<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:32px;border:1px solid #e8e8e8;border-radius:8px">
  <div style="text-align:center;margin-bottom:28px">
    <h1 style="color:#1a1a2e;font-size:24px;margin:0">Elvarion Holdings</h1>
    <p style="color:#888;font-size:13px;margin:4px 0">Monthly Portfolio Update</p>
  </div>
  <h2 style="color:#4f46e5;font-size:18px">Hello {{first_name}},</h2>
  <p style="color:#374151;line-height:1.7">
    Here is a summary of your Elvarion Holdings portfolio performance for this month.
    Our institutional team continues to execute across all asset classes.
  </p>
  <div style="background:#f8faff;border-radius:8px;padding:20px;margin:20px 0">
    <p style="margin:0;color:#374151;font-size:14px">Log in to your dashboard to see full returns, transaction history, and upcoming distributions.</p>
  </div>
  <div style="text-align:center;margin:28px 0">
    <a href="https://elvarionholdings.com/dashboard/"
       style="background:#4f46e5;color:#fff;padding:13px 32px;border-radius:6px;text-decoration:none;font-weight:600">
      View Full Report
    </a>
  </div>
  <hr style="border:1px solid #e8e8e8;margin:28px 0">
  <p style="font-size:11px;color:#9ca3af;text-align:center">Elvarion Holdings &bull; Tower 49, New York, NY 10017</p>
</div>""",
            },
            {
                'name': 'KYC Approved',
                'subject': 'Identity Verified — Your Account is Fully Activated',
                'body_html': """<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:32px;border:1px solid #e8e8e8;border-radius:8px">
  <div style="text-align:center;margin-bottom:28px">
    <h1 style="color:#1a1a2e;font-size:24px;margin:0">Elvarion Holdings</h1>
    <p style="color:#888;font-size:13px;margin:4px 0">Compliance &amp; Verification</p>
  </div>
  <h2 style="color:#22c55e;font-size:18px">Identity Verified</h2>
  <p style="color:#374151;line-height:1.7">Dear {{first_name}},</p>
  <p style="color:#374151;line-height:1.7">
    Your identity documents have been reviewed and approved. Your Elvarion Holdings account
    is now fully verified and activated for all investment products.
  </p>
  <div style="text-align:center;margin:28px 0">
    <a href="https://elvarionholdings.com/dashboard/"
       style="background:#22c55e;color:#fff;padding:13px 32px;border-radius:6px;text-decoration:none;font-weight:600">
      Start Investing
    </a>
  </div>
  <hr style="border:1px solid #e8e8e8;margin:28px 0">
  <p style="font-size:11px;color:#9ca3af;text-align:center">Elvarion Holdings &bull; Tower 49, New York, NY 10017</p>
</div>""",
            },
        ]

        created_count = 0
        for tpl_data in defaults:
            _, created = EmailTemplate.objects.get_or_create(
                name=tpl_data['name'],
                defaults={
                    'subject':   tpl_data['subject'],
                    'body_html': tpl_data['body_html'],
                }
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'[mailer] Templates: {created_count} created, {len(defaults) - created_count} already existed.'
        ))
        self.stdout.write(self.style.SUCCESS('[mailer] setup_mailer complete.'))
