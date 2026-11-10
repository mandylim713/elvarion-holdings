# Elvarion Holdings - setup notes

## Logins (change the passwords after first sign-in: Settings > Change password)
- Admin: `admin` / `Admin@12345` -> /login/ then /management/
- Demo investor: `vip_investor` / `Investor@12345`

## Automatic ROI and quick-trade results
A background job starts with the web server and runs every minute: it pays ROI into wallets, returns capital
when a plan ends, and settles quick trades. Nothing to configure.
Free hosts put the site to sleep when idle - add the "Automatic jobs" ping URL (Admin > Markets & trading) to
cron-job.org or UptimeRobot at a 5 minute interval so it stays awake. Dashboards also catch up the moment an
investor opens them, so nobody is ever short-changed.
Manual run: `python manage.py run_jobs`

## Email codes (OTP), forgot password, and admin notifications (Resend)
Resend is pre-configured and fully integrated with `elvarionholdings.com`:
- **Admin Console Management:** Go to Admin Console (`/management/#email`) > **Email & Resend** to configure or update your Resend API Key, Sender address, and Admin Alert Email at any time without restarting the server.
- **Instant Test Tool:** Test your email deliverability directly in Admin Console with one click using the built-in "Send Live Test Email" tool.
- **Environment Variable Fallback:** You can also set `RESEND_API_KEY` and `DEFAULT_FROM_EMAIL` in Render environment variables:
  - `RESEND_API_KEY`: your Resend API key (get it from resend.com/api-keys)
  - `DEFAULT_FROM_EMAIL`: `Elvarion Holdings <support@elvarionholdings.com>`
- **Automatic Admin Alerts:** The platform automatically dispatches institutional email alerts to `support@elvarionholdings.com` whenever an investor submits a new deposit, requests a withdrawal, applies for a loan, or submits KYC identity documents.
- Codes: 6 digits, valid 10 minutes, 5 tries, one new code per 60 seconds (resend button + `/auth/resend-otp/`).

## Live prices
Crypto: CryptoCompare (fallback CoinGecko). Stocks, gold, silver: Yahoo Finance. No API keys needed.
Admin > Markets & trading shows whether prices are "live" or "indicative" (fallback to the reference prices).
Switch live prices off there if you prefer fixed reference prices.

## Custom domain: elvarionholdings.com
1. Render dashboard > your web service > Settings > Custom Domains > add `elvarionholdings.com` and `www.elvarionholdings.com`.
2. At your domain registrar's DNS page add exactly the records Render shows (usually an A record or ALIAS for the bare domain and a CNAME for `www` pointing to your `.onrender.com` address). Wait for Render to show "Verified" - it issues the HTTPS certificate by itself.
3. `www.` automatically redirects to `elvarionholdings.com`.
4. Email from your own domain (Resend): Resend > Domains > add `elvarionholdings.com`, add the DNS records it lists (SPF + DKIM), wait for "Verified", then set `DEFAULT_FROM_EMAIL` to `Elvarion Holdings <no-reply@elvarionholdings.com>` in Render.
5. Use the new address in the cron ping (Admin > Markets & trading shows it automatically once you open the admin on the new domain).

## Separate logins

- Investors: `/login/` (staff accounts are rejected here)
- Admins: `/management/login/` (staff only, rate-limited, 8-hour session)
- Admin console: `/management/`
- Django admin: `/management/django-admin/`
