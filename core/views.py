import json
import os
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.db import transaction as db_transaction

from .models import (
    UserProfile, InvestmentArea, InvestmentPlan, UserInvestment,
    LoanTierCriteria, LoanTermConfig, LoanApplication,
    DepositRequest, WithdrawalRequest, Transaction, CompanySetting,
    KYCSubmission, TradingAsset, Holding, Trade
)
from .market import quote, quote_full, feed_status
from . import accrual, otp
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import OptionTrade

staff_required = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/management/login/')


def home(request):
    """Public luxury landing page for elvarionholdings.com"""
    areas = InvestmentArea.objects.filter(is_active=True).prefetch_related('plans')
    featured_plans = InvestmentPlan.objects.filter(is_active=True, is_featured=True)
    loan_tiers = LoanTierCriteria.objects.filter(is_active=True).order_by('min_deposit_required')
    loan_terms = LoanTermConfig.objects.filter(is_active=True).order_by('term_months')
    settings = CompanySetting.get_settings()

    context = {
        'areas': areas,
        'featured_plans': featured_plans,
        'loan_tiers': loan_tiers,
        'loan_terms': loan_terms,
        'settings': settings,
    }
    return render(request, 'index.html', context)


def register_view(request):
    """Institutional User Account Onboarding"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        account_type = request.POST.get('account_type', 'individual')
        username = request.POST.get('username', '').strip().lower()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        country = request.POST.get('country', 'United States').strip()
        phone_code = request.POST.get('phone_code', '+1').strip()
        phone_number = request.POST.get('phone', '').strip()
        phone = f"{phone_code} {phone_number}" if phone_number else ''

        if not username or not email or not password:
            messages.error(request, 'Please complete all required fields.')
            return render(request, 'auth/register.html')

        if password != password_confirm:
            messages.error(request, 'Passwords do not match. Please re-enter.')
            return render(request, 'auth/register.html')

        try:
            validate_password(password)
        except ValidationError as e:
            messages.error(request, ' '.join(e.messages))
            return render(request, 'auth/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" is already registered. Please select another.')
            return render(request, 'auth/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An institutional account with this corporate email already exists.')
            return render(request, 'auth/register.html')

        # Split full name
        names = full_name.split(' ', 1)
        first_name = names[0] if names else ''
        last_name = names[1] if len(names) > 1 else ''

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        UserProfile.objects.create(
            user=user,
            account_type=account_type,
            phone=phone,
            country=country,
            kyc_status='unverified',
            wallet_balance=Decimal('0.00'),
            total_deposited=Decimal('0.00')
        )

        login(request, user)
        if otp.verification_enforced():
            ok, _w, msg = otp.send_code(user, 'verify')
            messages.success(request, 'Account created. ' + msg if ok else 'Account created. ' + msg)
            return redirect('verify_email')
        messages.success(request, f'Welcome to Elvarion Holdings, {user.first_name or user.username}. Your account is ready.')
        return redirect('dashboard')

    return render(request, 'auth/register.html')


def login_view(request):
    """Investor sign-in (administrators use /management/login/)"""
    if request.user.is_authenticated:
        return redirect('admin_management' if request.user.is_staff else 'dashboard')

    if request.method == 'POST':
        identifier = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == '1'

        # Allow username or email login
        user = authenticate(request, username=identifier, password=password)
        if not user and '@' in identifier:
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is not None and user.is_staff:
            messages.error(request, 'Administrators sign in through the admin portal, not here.')
            return render(request, 'auth/login.html')
        if user is not None:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            nxt = request.GET.get('next') or request.POST.get('next') or ''
            if profile.two_factor and otp.codes_available() and user.email:
                request.session['pending_2fa'] = {'uid': user.id, 'remember': remember_me, 'next': nxt}
                ok, _w, msg = otp.send_code(user, 'login')
                messages.info(request, msg)
                return redirect('login_verify')
            return _finish_login(request, user, remember_me, nxt)
        else:
            messages.error(request, 'Authentication failed. Please verify your credentials or contact Treasury Concierge.')

    return render(request, 'auth/login.html')


def _finish_login(request, user, remember_me, next_url=''):
    login(request, user)
    request.session.set_expiry(1209600 if remember_me else 0)
    messages.success(request, f'Welcome back, {user.first_name or user.username}.')
    from django.utils.http import url_has_allowed_host_and_scheme
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('dashboard')


def login_verify(request):
    """Second step of sign-in for accounts that turned on sign-in codes"""
    pending = request.session.get('pending_2fa')
    if not pending:
        return redirect('login')
    user = User.objects.filter(id=pending['uid'], is_active=True).first()
    if not user:
        request.session.pop('pending_2fa', None)
        return redirect('login')
    if request.method == 'POST':
        if otp.check_code(user, 'login', request.POST.get('code')):
            request.session.pop('pending_2fa', None)
            return _finish_login(request, user, pending.get('remember'), pending.get('next', ''))
        messages.error(request, 'That code is not right or has expired.')
    return render(request, 'auth/otp.html', {
        'mode': 'login', 'title': 'Enter your sign-in code', 'email': otp.mask_email(user.email),
        'purpose': 'login', 'wait': otp.wait_seconds(user, 'login'), 'back_url': 'login'})


@login_required
def verify_email(request):
    """Confirm the email address with a 6-digit code"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if profile.email_verified:
        return redirect('dashboard')
    if request.method == 'POST':
        if otp.check_code(request.user, 'verify', request.POST.get('code')):
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            messages.success(request, 'Email confirmed. Welcome aboard.')
            return redirect('dashboard')
        messages.error(request, 'That code is not right or has expired.')
    elif not request.user.otp_codes.filter(purpose='verify', used=False, expires_at__gt=timezone.now()).exists():
        ok, _w, msg = otp.send_code(request.user, 'verify')
        (messages.info if ok else messages.error)(request, msg)
    return render(request, 'auth/otp.html', {
        'mode': 'verify', 'title': 'Confirm your email', 'email': otp.mask_email(request.user.email or ''),
        'purpose': 'verify', 'wait': otp.wait_seconds(request.user, 'verify'), 'back_url': 'logout'})


def forgot_password(request):
    """Step 1 of password reset: ask for the account email or username"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        ident = request.POST.get('identifier', '').strip()
        user = (User.objects.filter(email__iexact=ident).first() if '@' in ident
                else User.objects.filter(username__iexact=ident).first())
        request.session['reset_ident'] = ident
        if user and user.is_active and user.email:
            if otp.codes_available():
                otp.send_code(user, 'reset')
            request.session['reset_uid'] = user.id
        else:
            request.session.pop('reset_uid', None)
        messages.info(request, 'If that account exists, we have sent a 6-digit code to its email.')
        return redirect('reset_password')
    return render(request, 'auth/forgot.html', {'ready': otp.codes_available()})


def reset_password(request):
    """Step 2: enter the emailed code and choose a new password"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if 'reset_ident' not in request.session:
        return redirect('forgot_password')
    uid = request.session.get('reset_uid')
    user = User.objects.filter(id=uid).first() if uid else None
    if request.method == 'POST':
        pw, pw2 = request.POST.get('new_password', ''), request.POST.get('confirm_password', '')
        if pw != pw2:
            messages.error(request, 'The two passwords do not match.')
        else:
            try:
                validate_password(pw, user)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
            else:
                if user and otp.check_code(user, 'reset', request.POST.get('code')):
                    user.set_password(pw)
                    user.save()
                    for k in ('reset_uid', 'reset_ident'):
                        request.session.pop(k, None)
                    otp.notify(user, 'Your password was changed', 'Your password was just changed. If this was not you, contact support right away.')
                    messages.success(request, 'Password updated. You can sign in now.')
                    return redirect('login')
                messages.error(request, 'That code is not right or has expired.')
    return render(request, 'auth/reset.html', {
        'ident': request.session.get('reset_ident', ''), 'wait': otp.wait_seconds(user, 'reset') if user else 0})


def resend_otp(request):
    """Resend a code. POST purpose=verify|login|reset. JSON reply so pages can use it without reloading."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'POST only'}, status=405)
    purpose = request.POST.get('purpose')
    user = None
    if purpose == 'verify' and request.user.is_authenticated:
        user = request.user
    elif purpose == 'login' and request.session.get('pending_2fa'):
        user = User.objects.filter(id=request.session['pending_2fa']['uid']).first()
    elif purpose == 'reset' and request.session.get('reset_uid'):
        user = User.objects.filter(id=request.session['reset_uid']).first()
    elif purpose == 'reset':
        return JsonResponse({'ok': True, 'wait': 60, 'message': 'If that account exists, a new code is on its way.'})
    if not user:
        return JsonResponse({'ok': False, 'message': 'Please start again.'}, status=400)
    ok, wait, msg = otp.send_code(user, purpose)
    return JsonResponse({'ok': ok, 'wait': wait, 'message': msg})


# ---------------- ACCOUNT SETTINGS ----------------

@login_required
def settings_profile(request):
    if request.method == 'POST':
        u, p = request.user, request.user.profile
        u.first_name = request.POST.get('first_name', '').strip()[:60]
        u.last_name = request.POST.get('last_name', '').strip()[:60]
        u.save()
        p.phone = request.POST.get('phone', '').strip()[:30]
        p.country = request.POST.get('country', '').strip()[:100]
        p.email_notifications = request.POST.get('email_notifications') == '1'
        p.save()
        messages.success(request, 'Profile saved.')
    return redirect('/dashboard/#tab-settings')


@login_required
def settings_password(request):
    if request.method == 'POST':
        cur, new, new2 = request.POST.get('current_password', ''), request.POST.get('new_password', ''), request.POST.get('confirm_password', '')
        if not request.user.check_password(cur):
            messages.error(request, 'Your current password is not right.')
        elif new != new2:
            messages.error(request, 'The new passwords do not match.')
        else:
            try:
                validate_password(new, request.user)
            except ValidationError as e:
                messages.error(request, ' '.join(e.messages))
            else:
                request.user.set_password(new)
                request.user.save()
                update_session_auth_hash(request, request.user)
                otp.notify(request.user, 'Your password was changed', 'Your password was just changed. If this was not you, contact support right away.')
                messages.success(request, 'Password changed.')
    return redirect('/dashboard/#tab-settings')


@login_required
def settings_security(request):
    if request.method == 'POST':
        p = request.user.profile
        want = request.POST.get('two_factor') == '1'
        if want and not p.email_verified:
            messages.error(request, 'Confirm your email first, then you can turn on sign-in codes.')
        elif want and not otp.codes_available():
            messages.error(request, 'Email sending is not set up yet, so sign-in codes are unavailable.')
        else:
            p.two_factor = want
            p.save(update_fields=['two_factor'])
            messages.success(request, 'Sign-in codes are now ' + ('on.' if want else 'off.'))
    return redirect('/dashboard/#tab-settings')


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been securely signed out.')
    return redirect('home')


@login_required
def dashboard(request):
    """Client Portal Dashboard with Live ROI reader, portfolio, loan session, and wallet"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    for _iid in list(UserInvestment.objects.filter(user=request.user, status='active').values_list('id', flat=True)):
        accrual.accrue_investment(_iid)
    accrual.settle_options(user=request.user)
    profile.refresh_from_db()
    active_investments = UserInvestment.objects.filter(user=request.user, status='active')
    completed_investments = UserInvestment.objects.filter(user=request.user, status='completed')
    all_investments = UserInvestment.objects.filter(user=request.user)
    
    investment_areas = InvestmentArea.objects.filter(is_active=True).prefetch_related('plans')
    loan_tiers = LoanTierCriteria.objects.filter(is_active=True).order_by('min_deposit_required')
    loan_terms = LoanTermConfig.objects.filter(is_active=True).order_by('term_months')
    user_loans = LoanApplication.objects.filter(user=request.user)
    recent_txns = Transaction.objects.filter(user=request.user)[:10]
    
    # Loan eligibility evaluation
    eligible_tier = profile.get_eligible_loan_tier()
    next_tier = profile.get_next_loan_tier()
    next_tier_remaining = (next_tier.min_deposit_required - profile.total_deposited) if next_tier else Decimal('0.00')

    # Calculate real-time live ROI totals across all active investments
    total_live_roi = Decimal('0.00')
    active_investments_data = []
    for inv in active_investments:
        current_accrued = Decimal(str(round(inv.get_realtime_accrued_roi(), 2)))
        total_live_roi += current_accrued
        active_investments_data.append({
            'obj': inv,
            'accrued_roi': current_accrued,
            'progress_pct': round(inv.get_progress_percentage(), 1),
        })

    # Deposits history for user
    user_deposits = DepositRequest.objects.filter(user=request.user).order_by('-created_at')[:15]
    latest_kyc = KYCSubmission.objects.filter(user=request.user).order_by('-submitted_at').first()

    # Markets + holdings (indicative live prices)
    prices = {}
    markets = []
    for a in TradingAsset.objects.filter(is_active=True):
        pr, ch = quote(a)
        prices[a.id] = pr
        markets.append({'asset': a, 'price': pr, 'change': ch})
    holdings_data = []
    holdings_value = Decimal('0.00')
    holdings_cost = Decimal('0.00')
    for h in Holding.objects.filter(user=request.user, quantity__gt=0).select_related('asset'):
        pr = prices.get(h.asset_id) or quote(h.asset)[0]
        value = (h.quantity * pr).quantize(Decimal('0.01'))
        cost = (h.quantity * h.avg_price).quantize(Decimal('0.01'))
        holdings_value += value
        holdings_cost += cost
        holdings_data.append({
            'obj': h, 'price': pr, 'value': value, 'cost': cost,
            'pl': value - cost,
            'pl_pct': ((value - cost) / cost * 100).quantize(Decimal('0.01')) if cost else Decimal('0.00'),
        })
    recent_trades = Trade.objects.filter(user=request.user).select_related('asset')[:12]

    context = {
        'markets': markets,
        'holdings': holdings_data,
        'holdings_value': holdings_value,
        'holdings_pl': holdings_value - holdings_cost,
        'recent_trades': recent_trades,
        'open_options': OptionTrade.objects.filter(user=request.user, status='open').select_related('asset'),
        'recent_options': OptionTrade.objects.filter(user=request.user).exclude(status='open').select_related('asset')[:8],
        'option_assets': [m for m in markets if m['asset'].category == 'crypto'] or markets[:5],
        'option_durations': [(d, (f'{d}s' if d < 60 else f'{d // 60}m' if d < 3600 else f'{d // 3600}h')) for d in accrual.OPTION_DURATIONS],
        'codes_available': otp.codes_available(),
        'feed': feed_status(),
        'profile': profile,
        'active_investments': active_investments_data,
        'completed_investments': completed_investments,
        'all_investments': all_investments,
        'investment_areas': investment_areas,
        'loan_tiers': loan_tiers,
        'loan_terms': loan_terms,
        'eligible_tier': eligible_tier,
        'next_tier': next_tier,
        'next_tier_remaining': next_tier_remaining,
        'user_loans': user_loans,
        'recent_txns': recent_txns,
        'user_deposits': user_deposits,
        'latest_kyc': latest_kyc,
        'total_live_roi': total_live_roi,
        'settings': CompanySetting.get_settings(),
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def create_investment(request):
    """User initiates an investment in a specific plan across any area"""
    if request.method != 'POST':
        return redirect('dashboard')

    plan_id = request.POST.get('plan_id')
    amount_str = request.POST.get('amount', '0')

    try:
        amount = Decimal(amount_str)
    except Exception:
        messages.error(request, 'Invalid investment amount entered.')
        return redirect('dashboard')

    plan = get_object_or_404(InvestmentPlan, id=plan_id, is_active=True)
    profile = request.user.profile

    if amount < plan.min_deposit:
        messages.error(request, f'Minimum deposit for {plan.title} is ${plan.min_deposit:,.2f}.')
        return redirect('dashboard')

    if amount > plan.max_deposit:
        messages.error(request, f'Maximum deposit for {plan.title} is ${plan.max_deposit:,.2f}.')
        return redirect('dashboard')

    if profile.wallet_balance < amount:
        messages.error(request, f'Insufficient wallet balance (${profile.wallet_balance:,.2f}). Please fund your wallet first.')
        return redirect('dashboard')

    # Deduct wallet balance and create investment atomically
    with db_transaction.atomic():
        profile.wallet_balance -= amount
        profile.save()

        now = timezone.now()
        end_date = now + timedelta(seconds=plan.total_duration_seconds)
        total_roi_pct = (plan.roi_percentage * plan.duration_count) / Decimal('100.0')
        projected_roi = amount * total_roi_pct

        investment = UserInvestment.objects.create(
            user=request.user,
            plan=plan,
            amount=amount,
            start_date=now,
            end_date=end_date,
            total_projected_roi=projected_roi,
            status='active'
        )

        Transaction.objects.create(
            user=request.user,
            txn_type='investment',
            amount=amount,
            description=f"Investment in {plan.title} ({plan.area.name} - {plan.roi_percentage}% {plan.duration_unit})",
            is_credit=False
        )

    messages.success(request, f'Successfully activated ${amount:,.2f} investment in {plan.title}! Your ROI is now reading live.')
    return redirect('dashboard')


@login_required
def apply_loan(request):
    """User submits a loan application based on deposit qualification criteria"""
    if request.method != 'POST':
        return redirect('dashboard')

    profile = request.user.profile
    eligible_tier = profile.get_eligible_loan_tier()

    if not eligible_tier:
        messages.error(request, 'You do not meet the minimum deposit criteria ($25,000) for private credit access.')
        return redirect('dashboard')

    amount_str = request.POST.get('loan_amount', '0')
    term_months_str = request.POST.get('term_months', '6')
    purpose = request.POST.get('purpose', 'Private Portfolio Liquidity & Expansion')

    try:
        amount = Decimal(amount_str)
        term_months = int(term_months_str)
    except Exception:
        messages.error(request, 'Invalid loan parameters.')
        return redirect('dashboard')

    # Validate amount against eligible tier
    if amount < eligible_tier.min_loan_amount or amount > eligible_tier.max_loan_amount:
        messages.error(request, f"Your eligible tier ({eligible_tier.tier_name}) qualifies for loans between ${eligible_tier.min_loan_amount:,.2f} and ${eligible_tier.max_loan_amount:,.2f}.")
        return redirect('dashboard')

    # Retrieve configured term interest rate
    term_config = LoanTermConfig.objects.filter(term_months=term_months, is_active=True).first()
    if term_config:
        monthly_rate = term_config.monthly_interest_rate
    else:
        # Default fallback: 0.5% for 6m, 1.0% for 12m
        monthly_rate = Decimal('0.50') if term_months == 6 else Decimal('1.00')

    loan = LoanApplication(
        user=request.user,
        tier=eligible_tier,
        term_months=term_months,
        monthly_interest_rate=monthly_rate,
        amount_requested=amount,
        purpose=purpose
    )
    loan.calculate_loan_breakdown()
    loan.save()

    otp.notify(request.user, 'Loan Application Received', f"Your loan application for ${amount:,.2f} has been submitted for underwriter review.")
    otp.notify_admin(f"New Loan Application: ${amount:,.2f}", f"Investor @{request.user.username} submitted a loan request of ${amount:,.2f} ({term_months} Months).", cta_url="/management/#loans")

    messages.success(request, f"Your loan application for ${amount:,.2f} ({term_months} Months @ {monthly_rate}%/mo) has been submitted for VIP underwriter approval.")
    return redirect('dashboard')


@login_required
def submit_deposit(request):
    """User submits a hybrid deposit (Crypto or Bank Wire) with proof"""
    if request.method != 'POST':
        return redirect('dashboard')

    profile = request.user.profile
    amount_str = request.POST.get('amount', '0')
    method = request.POST.get('method', 'USDT_TRC20')
    proof_hash = request.POST.get('proof_hash', '').strip()
    receipt_file = request.FILES.get('receipt_image')

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError()
    except Exception:
        messages.error(request, 'Please enter a valid positive deposit amount.')
        return redirect('dashboard')

    deposit = DepositRequest.objects.create(
        user=request.user,
        method=method,
        amount=amount,
        proof_hash=proof_hash or 'Direct Portal Submission',
        receipt_image=receipt_file,
        status='pending'
    )

    otp.notify(request.user, 'Deposit Received', f"Your deposit of ${amount:,.2f} via {method} has been received and is pending confirmation.")
    otp.notify_admin(f"New Deposit: ${amount:,.2f} ({method})", f"Investor @{request.user.username} submitted a deposit of ${amount:,.2f} via {method}. Ref: {deposit.reference_id}.", cta_url="/management/#deposits")

    messages.success(request, f"Deposit request for ${amount:,.2f} received. Our treasury desk will confirm receipt and credit your balance.")

    return redirect('dashboard')


@login_required
def submit_withdrawal(request):
    """User requests fund withdrawal"""
    if request.method != 'POST':
        return redirect('dashboard')

    profile = request.user.profile
    amount_str = request.POST.get('amount', '0')
    method = request.POST.get('payout_method', 'USDT (TRC-20)')
    details = request.POST.get('destination_details', '').strip()

    if method == 'Bank Transfer':
        f = lambda k: request.POST.get(k, '').strip()
        if not (f('bank_name') and f('account_name') and f('account_number')):
            messages.error(request, 'Please fill in the bank name, account name and account number.')
            return redirect('/dashboard/#tab-investments')
        details = (f"Bank: {f('bank_name')} | Account name: {f('account_name')} | "
                   f"Account no / IBAN: {f('account_number')} | SWIFT / routing: {f('swift') or '-'} | Country: {f('bank_country') or '-'}")
    elif method in ('Zelle', 'PayPal', 'Venmo', 'Cash App', 'Wise'):
        handle = request.POST.get('app_handle', '').strip()
        if not handle:
            messages.error(request, f'Please enter the {method} email, phone or username to send to.')
            return redirect('/dashboard/#tab-investments')
        details = f"{method}: {handle} | Name on account: {request.POST.get('app_name', '').strip() or '-'}"
    elif not details:
        messages.error(request, 'Please enter the wallet address to send to.')
        return redirect('/dashboard/#tab-investments')

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError()
    except Exception:
        messages.error(request, 'Invalid withdrawal amount.')
        return redirect('dashboard')

    if profile.wallet_balance < amount:
        messages.error(request, f'Insufficient wallet balance (${profile.wallet_balance:,.2f}).')
        return redirect('dashboard')

    with db_transaction.atomic():
        profile.wallet_balance -= amount
        profile.total_withdrawn += amount
        profile.save()

        w = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            payout_method=method,
            destination_details=details,
            status='pending'
        )

        Transaction.objects.create(
            user=request.user,
            txn_type='withdrawal',
            amount=amount,
            description=f"Withdrawal Request to {details[:30]}",
            is_credit=False
        )

    otp.notify(request.user, 'Withdrawal Requested', f"Your withdrawal request of ${amount:,.2f} via {method} has been submitted for processing.")
    otp.notify_admin(f"New Withdrawal: ${amount:,.2f}", f"Investor @{request.user.username} submitted a withdrawal request of ${amount:,.2f} via {method} to {details}.", cta_url="/management/#withdrawals")

    messages.success(request, f"Withdrawal request for ${amount:,.2f} submitted for treasury dispatch.")
    return redirect('dashboard')


# ---------------- TRADING ----------------

@login_required
def trade_order(request):
    """Buy or sell a market asset using the wallet balance at the current indicative price"""
    back = '/dashboard/#tab-trade'
    if request.method != 'POST':
        return redirect(back)
    asset = get_object_or_404(TradingAsset, id=request.POST.get('asset_id'), is_active=True)
    side = request.POST.get('side')
    try:
        amount = Decimal(request.POST.get('amount', '0')).quantize(Decimal('0.01'))
    except Exception:
        amount = Decimal('0')
    if side not in ('buy', 'sell') or amount < Decimal('10'):
        messages.error(request, 'Enter an amount of at least $10.')
        return redirect(back)

    price, _ = quote(asset, wait=True)
    q8 = Decimal('0.00000001')
    with db_transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(user=request.user)
        holding, _ = Holding.objects.select_for_update().get_or_create(user=request.user, asset=asset)
        if side == 'buy':
            if profile.wallet_balance < amount:
                messages.error(request, f'Not enough balance (${profile.wallet_balance:,.2f}). Add funds in Deposit first.')
                return redirect(back)
            qty = (amount / price).quantize(q8)
            new_total = holding.quantity + qty
            holding.avg_price = ((holding.quantity * holding.avg_price) + (qty * price)) / new_total if new_total else price
            holding.quantity = new_total
            holding.save()
            profile.wallet_balance -= amount
            profile.save()
            Trade.objects.create(user=request.user, asset=asset, side='buy', quantity=qty, price=price, total=amount)
            Transaction.objects.create(user=request.user, txn_type='trade', amount=amount, is_credit=False,
                                       description=f"Bought {qty.normalize():f} {asset.symbol} @ ${price:,.2f}")
            messages.success(request, f"Bought {qty.normalize():f} {asset.symbol} for ${amount:,.2f}.")
        else:
            if request.POST.get('sell_all') == '1' or (holding.quantity * price) - amount < Decimal('0.01'):
                qty = holding.quantity
            else:
                qty = (amount / price).quantize(q8)
            if qty <= 0 or qty > holding.quantity:
                messages.error(request, f'You do not hold enough {asset.symbol} to sell that amount.')
                return redirect(back)
            proceeds = (qty * price).quantize(Decimal('0.01'))
            pl = proceeds - (qty * holding.avg_price).quantize(Decimal('0.01'))
            holding.quantity -= qty
            if holding.quantity <= 0:
                holding.quantity = Decimal('0')
                holding.avg_price = Decimal('0')
            holding.save()
            profile.wallet_balance += proceeds
            profile.save()
            Trade.objects.create(user=request.user, asset=asset, side='sell', quantity=qty, price=price,
                                 total=proceeds, realized_pl=pl)
            Transaction.objects.create(user=request.user, txn_type='trade', amount=proceeds, is_credit=True,
                                       description=f"Sold {qty.normalize():f} {asset.symbol} @ ${price:,.2f}")
            messages.success(request, f"Sold {qty.normalize():f} {asset.symbol} for ${proceeds:,.2f} ({'+' if pl >= 0 else '-'}${abs(pl):,.2f}).")
    return redirect(back)


@login_required
def api_market(request):
    """Live indicative quotes for the trading screen"""
    out = []
    for a in TradingAsset.objects.filter(is_active=True):
        pr, ch, live = quote_full(a)
        out.append({'id': a.id, 'symbol': a.symbol, 'price': str(pr), 'change': str(ch), 'live': live})
    return JsonResponse({'status': 'success', 'source': feed_status(), 'quotes': out})


# ---------------- QUICK TRADE (up / down) ----------------

@login_required
def option_place(request):
    """Open a Quick Trade: call whether the price will be higher or lower when the timer ends"""
    back = '/dashboard/#tab-trade'
    if request.method != 'POST':
        return redirect(back)
    cs = CompanySetting.get_settings()
    asset = get_object_or_404(TradingAsset, id=request.POST.get('asset_id'), is_active=True)
    direction = request.POST.get('direction')
    try:
        stake = Decimal(request.POST.get('stake', '0')).quantize(Decimal('0.01'))
        duration = int(request.POST.get('duration', '60'))
    except Exception:
        stake, duration = Decimal('0'), 0
    if direction not in ('up', 'down') or duration not in accrual.OPTION_DURATIONS:
        messages.error(request, 'Choose Up or Down and a timer.')
        return redirect(back)
    if stake < cs.option_min_stake:
        messages.error(request, f'The minimum Quick Trade is ${cs.option_min_stake:,.2f}.')
        return redirect(back)
    price, _ = quote(asset, wait=True)
    with db_transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(user=request.user)
        if OptionTrade.objects.filter(user=request.user, status='open').count() >= accrual.MAX_OPEN_OPTIONS:
            messages.error(request, f'You can have up to {accrual.MAX_OPEN_OPTIONS} open Quick Trades at once.')
            return redirect(back)
        if profile.wallet_balance < stake:
            messages.error(request, f'Not enough balance (${profile.wallet_balance:,.2f}). Add money first.')
            return redirect(back)
        profile.wallet_balance -= stake
        profile.save()
        now = timezone.now()
        OptionTrade.objects.create(user=request.user, asset=asset, direction=direction, stake=stake,
                                   payout_pct=cs.option_payout_pct, entry_price=price, duration=duration,
                                   opened_at=now, expires_at=now + timedelta(seconds=duration))
        Transaction.objects.create(user=request.user, txn_type='option', amount=stake, is_credit=False,
                                   description=f"Quick Trade {asset.symbol} {direction} - ${stake:,.2f} for {duration}s")
    messages.success(request, f"{asset.symbol} {direction.upper()} trade placed at ${price:,.2f}. Result in {duration} seconds.")
    return redirect(back)


@login_required
def api_options(request):
    """Open Quick Trades with time left; settles anything that has finished"""
    accrual.settle_options(user=request.user)
    now = timezone.now()
    opens = []
    for o in OptionTrade.objects.filter(user=request.user, status='open').select_related('asset'):
        price = quote(o.asset)[0]
        opens.append({'id': o.id, 'symbol': o.asset.symbol, 'direction': o.direction, 'stake': str(o.stake),
                      'entry': str(o.entry_price), 'price': str(price), 'payout_pct': o.payout_pct,
                      'left': max(0, int((o.expires_at - now).total_seconds())), 'duration': o.duration})
    done = [{'id': o.id, 'symbol': o.asset.symbol, 'direction': o.direction, 'stake': str(o.stake),
             'status': o.status, 'result': str(o.result_amount), 'entry': str(o.entry_price), 'exit': str(o.exit_price or '')}
            for o in OptionTrade.objects.filter(user=request.user).exclude(status='open').select_related('asset')[:8]]
    profile = UserProfile.objects.get(user=request.user)
    return JsonResponse({'status': 'success', 'open': opens, 'done': done, 'balance': str(profile.wallet_balance)})


def cron_tick(request):
    """Ping URL for an external scheduler (cron-job.org, UptimeRobot...). Also keeps a sleeping free host awake."""
    if request.GET.get('key') != accrual_token():
        return JsonResponse({'status': 'forbidden'}, status=403)
    return JsonResponse({'status': 'ok', **accrual.run_all_jobs()})


def accrual_token():
    import hashlib
    from django.conf import settings as dj
    return os.environ.get('CRON_SECRET') or hashlib.sha256(('cron:' + dj.SECRET_KEY).encode()).hexdigest()[:24]


# ---------------- API ENDPOINTS ----------------

@login_required
def api_realtime_roi(request):
    """Live JSON API returning accrued ROI ticker values for all active investments"""
    investments = UserInvestment.objects.filter(user=request.user, status='active')
    data = []
    total_accrued = 0.0

    for inv in investments:
        accrued = inv.get_realtime_accrued_roi()
        total_accrued += accrued
        data.append({
            'id': inv.id,
            'reference': inv.reference_id,
            'plan_title': inv.plan.title,
            'area': inv.plan.area.name,
            'amount': float(inv.amount),
            'roi_percentage': float(inv.plan.roi_percentage),
            'duration_unit': inv.plan.duration_unit,
            'duration_count': inv.plan.duration_count,
            'projected_roi': float(inv.total_projected_roi),
            'accrued_roi': round(accrued, 2),
            'progress_percentage': round(inv.get_progress_percentage(), 2),
            'status': inv.status,
        })

    return JsonResponse({
        'status': 'success',
        'server_time': timezone.now().isoformat(),
        'total_accrued_roi': round(total_accrued, 2),
        'investments': data,
    })


def api_loan_calculator(request):
    """Computes loan breakdown dynamically based on amount and term"""
    try:
        amount = Decimal(request.GET.get('amount', '300000'))
        term_months = int(request.GET.get('term', '6'))
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid inputs'}, status=400)

    term_cfg = LoanTermConfig.objects.filter(term_months=term_months, is_active=True).first()
    rate = term_cfg.monthly_interest_rate if term_cfg else (Decimal('0.50') if term_months == 6 else Decimal('1.00'))

    total_interest = amount * (rate / Decimal('100.0')) * Decimal(term_months)
    total_repayable = amount + total_interest
    monthly_installment = total_repayable / Decimal(term_months)

    return JsonResponse({
        'status': 'success',
        'amount': float(amount),
        'term_months': term_months,
        'monthly_rate': float(rate),
        'total_interest': float(round(total_interest, 2)),
        'total_repayable': float(round(total_repayable, 2)),
        'monthly_installment': float(round(monthly_installment, 2)),
    })


@login_required
def submit_kyc(request):
    """Investor submits institutional KYC identification and verification documents"""
    if request.method != 'POST':
        return redirect('dashboard')

    profile = request.user.profile
    full_legal_name = request.POST.get('full_legal_name', '').strip()
    dob_str = request.POST.get('date_of_birth', '').strip()
    residential_address = request.POST.get('residential_address', '').strip()
    city = request.POST.get('city', '').strip()
    postal_code = request.POST.get('postal_code', '').strip()
    country = request.POST.get('country', profile.country).strip()

    id_type = request.POST.get('id_type', 'passport')
    id_number = request.POST.get('id_number', '').strip()
    source_of_wealth = request.POST.get('source_of_wealth', 'employment')
    estimated_net_worth = request.POST.get('estimated_net_worth', '$1,000,000 - $5,000,000')
    pep_status = request.POST.get('pep_status') == '1'

    id_front_image = request.FILES.get('id_front_image')
    id_back_image = request.FILES.get('id_back_image')
    proof_of_address = request.FILES.get('proof_of_address')
    selfie_image = request.FILES.get('selfie_image')

    if not full_legal_name or not id_number or not residential_address:
        messages.error(request, 'Please complete all required identity and address fields.')
        return redirect('dashboard')

    date_of_birth = None
    if dob_str:
        try:
            from datetime import datetime
            date_of_birth = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    submission = KYCSubmission.objects.create(
        user=request.user,
        full_legal_name=full_legal_name,
        date_of_birth=date_of_birth,
        residential_address=residential_address,
        city=city,
        postal_code=postal_code,
        country=country,
        id_type=id_type,
        id_number=id_number,
        id_front_image=id_front_image,
        id_back_image=id_back_image,
        proof_of_address=proof_of_address,
        selfie_image=selfie_image,
        source_of_wealth=source_of_wealth,
        estimated_net_worth=estimated_net_worth,
        pep_status=pep_status,
        status='pending'
    )

    profile.kyc_status = 'pending'
    profile.save()
    ref_id = str(submission.submission_id)[:8]
    otp.notify(request.user, 'KYC Documents Received', f"Your identity documents (Dossier #{ref_id}) have been received and are undergoing compliance review.")
    otp.notify_admin(f"New KYC Submission: {submission.full_legal_name}", f"Investor @{request.user.username} submitted identity verification documents ({submission.get_id_type_display()}) for review.", cta_url="/management/#kyc")
    messages.success(request, f'KYC Dossier #{ref_id} submitted successfully. Our Compliance Desk will verify your credentials within 2 business hours.')
    return redirect('dashboard')


# ---------------- ADMIN MANAGEMENT PORTAL ----------------

@staff_required
def admin_management(request):
    """Admin console: overview, queues (deposits, withdrawals, loans, KYC), investors, plans and config"""
    from django.db.models import Sum

    def total(qs, field):
        return qs.aggregate(t=Sum(field))['t'] or Decimal('0.00')

    pending_loans = LoanApplication.objects.filter(status='pending').select_related('user', 'user__profile')
    all_loans = LoanApplication.objects.select_related('user').order_by('-applied_at')[:100]
    pending_deposits = DepositRequest.objects.filter(status='pending').select_related('user')
    all_deposits = DepositRequest.objects.select_related('user').order_by('-created_at')[:100]
    pending_withdrawals = WithdrawalRequest.objects.filter(status='pending').select_related('user')
    all_withdrawals = WithdrawalRequest.objects.select_related('user').order_by('-created_at')[:100]
    pending_kyc = KYCSubmission.objects.filter(status='pending')
    all_kyc = KYCSubmission.objects.select_related('user').order_by('-submitted_at')[:100]
    investments = UserInvestment.objects.select_related('user', 'plan', 'plan__area').order_by('-created_at')[:100]
    transactions = Transaction.objects.select_related('user').order_by('-created_at')[:100]

    investment_areas = InvestmentArea.objects.all()
    plans = InvestmentPlan.objects.select_related('area').order_by('area__order', 'title')
    loan_tiers = LoanTierCriteria.objects.order_by('min_deposit_required')
    loan_terms = LoanTermConfig.objects.order_by('term_months')
    users = User.objects.all().select_related('profile').order_by('-date_joined')

    # 7-day approved-deposit bars
    today = timezone.now().date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    daily = []
    for d in days:
        amt = total(DepositRequest.objects.filter(status='approved', processed_at__date=d), 'amount')
        daily.append({'label': d.strftime('%a'), 'value': amt})
    peak = max([x['value'] for x in daily] + [Decimal('1')])
    for x in daily:
        x['pct'] = int((x['value'] / peak) * 100) if peak else 0

    stats = {
        'aum': total(UserInvestment.objects.filter(status='active'), 'amount'),
        'active_investments': UserInvestment.objects.filter(status='active').count(),
        'deposits_total': total(DepositRequest.objects.filter(status='approved'), 'amount'),
        'wallets_total': total(UserProfile.objects.all(), 'wallet_balance'),
        'loans_out': total(UserProfile.objects.all(), 'loan_balance'),
        'withdrawn_total': total(WithdrawalRequest.objects.filter(status='approved'), 'amount'),
        'pending_deposit_value': total(pending_deposits, 'amount'),
        'pending_withdrawal_value': total(pending_withdrawals, 'amount'),
        'pending_loan_value': total(pending_loans, 'amount_requested'),
        'users': users.count(),
        'new_users_7d': users.filter(date_joined__gte=timezone.now() - timedelta(days=7)).count(),
    }
    queue_total = (pending_loans.count() + pending_deposits.count()
                   + pending_withdrawals.count() + pending_kyc.count())

    context = {
        'pending_loans': pending_loans,
        'all_loans': all_loans,
        'pending_deposits': pending_deposits,
        'all_deposits': all_deposits,
        'pending_withdrawals': pending_withdrawals,
        'all_withdrawals': all_withdrawals,
        'pending_kyc': pending_kyc,
        'all_kyc': all_kyc,
        'investments': investments,
        'transactions': transactions,
        'investment_areas': investment_areas,
        'plans': plans,
        'loan_tiers': loan_tiers,
        'loan_terms': loan_terms,
        'users': users,
        'assets': TradingAsset.objects.all(),
        'recent_trades': Trade.objects.select_related('user', 'asset').order_by('-created_at')[:50],
        'recent_options': OptionTrade.objects.select_related('user', 'asset').order_by('-opened_at')[:50],
        'cron_url': request.build_absolute_uri('/cron/tick/') + '?key=' + accrual_token(),
        'feed': feed_status(),
        'stats': stats,
        'daily': daily,
        'queue_total': queue_total,
        'settings': CompanySetting.get_settings(),
        'resend_configured': bool(CompanySetting.get_settings().get_resend_api_key()),
        'email_configured': CompanySetting.get_settings().is_email_configured(),
        'active_sender': CompanySetting.get_settings().get_sender_email(),
    }
    return render(request, 'management/index.html', context)


@staff_required
def admin_withdrawal_action(request, withdrawal_id, action):
    """Approve (mark dispatched) or decline (refund wallet) a withdrawal"""
    if request.method != 'POST':
        return redirect('admin_management')
    w = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    if w.status != 'pending':
        messages.warning(request, 'That withdrawal was already processed.')
        return redirect('/management/#withdrawals')
    note = request.POST.get('admin_notes', '').strip()
    ref = str(w.reference_id)[:8]
    with db_transaction.atomic():
        if action == 'approve':
            w.status = 'approved'
            w.processed_at = timezone.now()
            w.admin_notes = note or 'Dispatched by treasury'
            w.save()
            otp.notify(w.user, 'Withdrawal sent', f"Your withdrawal of ${w.amount:,.2f} has been sent.")
            messages.success(request, f"Withdrawal #{ref} for ${w.amount:,.2f} marked as dispatched to {w.user.username}.")
        elif action == 'reject':
            w.status = 'rejected'
            w.processed_at = timezone.now()
            w.admin_notes = note or 'Declined by treasury'
            w.save()
            profile = w.user.profile
            profile.wallet_balance += w.amount
            profile.total_withdrawn = max(Decimal('0.00'), profile.total_withdrawn - w.amount)
            profile.save()
            Transaction.objects.create(
                user=w.user, txn_type='withdrawal', amount=w.amount,
                description=f"Withdrawal #{ref} declined - funds returned", is_credit=True)
            otp.notify(w.user, 'Withdrawal declined', f"Your withdrawal of ${w.amount:,.2f} was declined and the money is back in your wallet.")
            messages.warning(request, f"Withdrawal #{ref} declined and ${w.amount:,.2f} returned to {w.user.username}'s wallet.")
    return redirect('/management/#withdrawals')


@staff_required
def admin_user_action(request, user_id, action):
    """Suspend / reactivate an investor, or credit / debit their wallet"""
    if request.method != 'POST':
        return redirect('admin_management')
    target = get_object_or_404(User, id=user_id)
    if action == 'toggle_active':
        if target.id == request.user.id:
            messages.error(request, 'You cannot suspend your own account.')
        else:
            target.is_active = not target.is_active
            target.save()
            messages.success(request, f"{target.username} {'reactivated' if target.is_active else 'suspended'}.")
    elif action == 'reset_password':
        import secrets
        temp = secrets.token_urlsafe(9)
        target.set_password(temp)
        target.save()
        messages.success(request, f"New temporary password for {target.username}: {temp}  (share it privately - they should change it in Settings).")
    elif action in ('credit', 'debit'):
        try:
            amount = Decimal(request.POST.get('amount', '0'))
            if amount <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, 'Enter a valid amount.')
            return redirect('/management/#users')
        note = (request.POST.get('note') or '').strip()[:150] or 'Manual adjustment'
        profile = target.profile
        with db_transaction.atomic():
            if action == 'credit':
                profile.wallet_balance += amount
            else:
                if profile.wallet_balance < amount:
                    messages.error(request, f"{target.username} only has ${profile.wallet_balance:,.2f} available.")
                    return redirect('/management/#users')
                profile.wallet_balance -= amount
            profile.save()
            Transaction.objects.create(
                user=target, txn_type='deposit', amount=amount,
                description=f"Admin {action}: {note}", is_credit=(action == 'credit'))
        messages.success(request, f"{'Credited' if action == 'credit' else 'Debited'} ${amount:,.2f} {'to' if action == 'credit' else 'from'} {target.username}'s wallet.")
    return redirect('/management/#users')


@staff_required
def admin_toggle_plan(request, plan_id):
    """Activate / deactivate an investment plan"""
    if request.method == 'POST':
        plan = get_object_or_404(InvestmentPlan, id=plan_id)
        plan.is_active = not plan.is_active
        plan.save()
        messages.success(request, f"Plan '{plan.title}' {'activated' if plan.is_active else 'deactivated'}.")
    return redirect('/management/#plans')


@staff_required
def admin_investment_action(request, investment_id, action):
    """Pause or resume a client's investment"""
    if request.method == 'POST':
        inv = get_object_or_404(UserInvestment, id=investment_id)
        if action == 'pause' and inv.status == 'active':
            accrual.accrue_investment(inv.id)
            inv.refresh_from_db()
            if inv.status != 'active':
                return redirect('/management/#investments')
            inv.status = 'paused'
            inv.last_roi_update = timezone.now()
        elif action == 'resume' and inv.status == 'paused':
            gap = timezone.now() - inv.last_roi_update
            inv.start_date += gap          # the paused time does not earn ROI
            inv.end_date += gap
            inv.status = 'active'
            inv.last_roi_update = timezone.now()
        else:
            return redirect('/management/#investments')
        inv.save()
        messages.success(request, f"Investment for {inv.user.username} is now {inv.get_status_display().split(' (')[0].lower()}.")
    return redirect('/management/#investments')


@staff_required
def admin_kyc_action(request, submission_id, action):
    """Compliance Director approves or declines a KYC submission"""
    submission = get_object_or_404(KYCSubmission, id=submission_id)
    notes = request.POST.get('admin_notes', '').strip()

    if action == 'approve':
        submission.status = 'approved'
        submission.reviewed_at = timezone.now()
        submission.admin_notes = notes or 'Verified and Approved by Compliance Officer'
        submission.save()

        profile = submission.user.profile
        profile.kyc_status = 'verified'
        profile.save()

        otp.notify(submission.user, 'Identity verified', 'Your identity check was approved. Withdrawals and loans are now unlocked.')
        messages.success(request, f"KYC for {submission.full_legal_name} ({submission.user.username}) approved as Tier-1 Verified.")
    elif action == 'reject':
        submission.status = 'rejected'
        submission.reviewed_at = timezone.now()
        submission.admin_notes = notes or 'Document did not meet regulatory standards. Please resubmit.'
        submission.save()

        profile = submission.user.profile
        profile.kyc_status = 'unverified'
        profile.save()

        messages.warning(request, f"KYC for {submission.full_legal_name} was declined.")

    return redirect('/management/#kyc')


@staff_required
def admin_loan_action(request, loan_id, action):
    """Admin approves or rejects a loan request"""
    loan = get_object_or_404(LoanApplication, id=loan_id)
    admin_note = request.POST.get('admin_note', '')

    if action == 'approve':
        loan.status = 'approved'
        loan.reviewed_at = timezone.now()
        loan.disbursed_at = timezone.now()
        loan.disbursed_to_wallet = True
        loan.admin_notes = admin_note or 'Approved by Investment Committee'
        loan.save()

        # Credit user's loan balance
        profile = loan.user.profile
        profile.loan_balance += loan.amount_requested
        profile.save()

        loan_ref = str(loan.loan_reference)[:8]
        Transaction.objects.create(
            user=loan.user,
            txn_type='loan_disbursement',
            amount=loan.amount_requested,
            description=f"Approved Private Credit Loan #{loan_ref}",
            is_credit=True
        )
        messages.success(request, f"Loan #{loan_ref} for ${loan.amount_requested:,.2f} approved and disbursed to {loan.user.username}'s loan balance.")
    elif action == 'reject':
        loan.status = 'rejected'
        loan.reviewed_at = timezone.now()
        loan.admin_notes = admin_note or 'Declined based on underwriting review.'
        loan.save()
        messages.warning(request, f"Loan #{str(loan.loan_reference)[:8]} declined.")

    return redirect('/management/#loans')


@staff_required
def admin_deposit_action(request, deposit_id, action):
    """Admin approves or rejects a deposit"""
    if request.method != 'POST':
        return redirect('/management/#deposits')
    deposit = get_object_or_404(DepositRequest, id=deposit_id)
    if deposit.status != 'pending':
        messages.warning(request, 'That deposit was already processed.')
        return redirect('/management/#deposits')

    if action == 'approve':
        deposit.status = 'approved'
        deposit.processed_at = timezone.now()
        deposit.save()

        profile = deposit.user.profile
        profile.wallet_balance += deposit.amount
        profile.total_deposited += deposit.amount
        profile.save()

        Transaction.objects.create(
            user=deposit.user,
            txn_type='deposit',
            amount=deposit.amount,
            description=f"Approved Deposit ({deposit.get_method_display()})",
            is_credit=True
        )
        dep_ref = str(deposit.reference_id)[:8]
        otp.notify(deposit.user, 'Deposit confirmed', f"Your deposit of ${deposit.amount:,.2f} has been confirmed and added to your wallet.")
        messages.success(request, f"Deposit #{dep_ref} for ${deposit.amount:,.2f} approved and credited to {deposit.user.username}.")
    elif action == 'reject':
        deposit.status = 'rejected'
        deposit.processed_at = timezone.now()
        deposit.save()
        otp.notify(deposit.user, 'Deposit not confirmed', f"We could not confirm your deposit of ${deposit.amount:,.2f}. Please contact support or submit the payment proof again.")
        messages.warning(request, f"Deposit #{str(deposit.reference_id)[:8]} rejected.")

    return redirect('/management/#deposits')


@staff_required
def admin_save_plan(request):
    """Quick edit or create investment plan directly from admin dashboard"""
    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        title = request.POST.get('title')
        area_id = request.POST.get('area_id')
        roi_percentage = Decimal(request.POST.get('roi_percentage', '5.0'))
        duration_unit = request.POST.get('duration_unit', 'monthly')
        duration_count = int(request.POST.get('duration_count', '1'))
        min_deposit = Decimal(request.POST.get('min_deposit', '1000'))
        max_deposit = Decimal(request.POST.get('max_deposit', '50000'))

        area = get_object_or_404(InvestmentArea, id=area_id)

        if plan_id:
            plan = get_object_or_404(InvestmentPlan, id=plan_id)
            plan.title = title
            plan.area = area
            plan.roi_percentage = roi_percentage
            plan.duration_unit = duration_unit
            plan.duration_count = duration_count
            plan.min_deposit = min_deposit
            plan.max_deposit = max_deposit
            plan.save()
            messages.success(request, f"Plan '{plan.title}' updated successfully.")
        else:
            InvestmentPlan.objects.create(
                title=title,
                area=area,
                roi_percentage=roi_percentage,
                duration_unit=duration_unit,
                duration_count=duration_count,
                min_deposit=min_deposit,
                max_deposit=max_deposit
            )
            messages.success(request, f"New plan '{title}' created successfully.")

    return redirect('/management/#plans')


@staff_required
def admin_save_tier(request):
    """Quick edit or add loan tier criteria"""
    if request.method == 'POST':
        tier_id = request.POST.get('tier_id')
        tier_name = request.POST.get('tier_name')
        min_dep = Decimal(request.POST.get('min_deposit_required', '25000'))
        min_loan = Decimal(request.POST.get('min_loan_amount', '300000'))
        max_loan = Decimal(request.POST.get('max_loan_amount', '799000'))
        badge = request.POST.get('badge', 'TIER')

        if tier_id:
            tier = get_object_or_404(LoanTierCriteria, id=tier_id)
            tier.tier_name = tier_name
            tier.min_deposit_required = min_dep
            tier.min_loan_amount = min_loan
            tier.max_loan_amount = max_loan
            tier.badge = badge
            tier.save()
            messages.success(request, f"Loan criteria tier '{tier.tier_name}' updated.")
        else:
            LoanTierCriteria.objects.create(
                tier_name=tier_name,
                min_deposit_required=min_dep,
                min_loan_amount=min_loan,
                max_loan_amount=max_loan,
                badge=badge
            )
            messages.success(request, f"New loan tier '{tier_name}' created.")

    return redirect('/management/#tiers')


@staff_required
def admin_save_settings(request):
    """Edit bank, wallet and payment-app details shown on the Add money page"""
    if request.method == 'POST':
        cs = CompanySetting.get_settings()
        fields = ['zelle_email', 'zelle_name', 'paypal_email', 'venmo_handle', 'cashapp_tag', 'wise_email',
                  'bank_name', 'bank_account_name', 'bank_account_number', 'bank_routing_swift',
                  'btc_wallet_address', 'eth_wallet_address', 'usdt_trc20_address', 'usdt_erc20_address']
        for k in fields:
            if k in request.POST:
                setattr(cs, k, request.POST.get(k, '').strip()[:150])
        if request.POST.get('form') == 'platform':
            cs.use_live_prices = request.POST.get('use_live_prices') == '1'
            cs.require_email_verification = request.POST.get('require_email_verification') == '1'
            try:
                cs.option_payout_pct = max(1, min(500, int(request.POST.get('option_payout_pct', cs.option_payout_pct))))
                cs.option_min_stake = max(Decimal('1'), Decimal(request.POST.get('option_min_stake', cs.option_min_stake)))
            except Exception:
                pass
            cs.save()
            messages.success(request, 'Platform settings saved.')
            return redirect('/management/#markets')
        cs.save()
        messages.success(request, 'Payment details saved.')
    return redirect('/management/#payments')


@staff_required
def admin_save_email_settings(request):
    """Save Resend API key, sender email, admin alert email, and verification options"""
    if request.method == 'POST':
        cs = CompanySetting.get_settings()
        cs.resend_api_key = request.POST.get('resend_api_key', '').strip()
        cs.sender_email = request.POST.get('sender_email', '').strip()
        cs.admin_email = request.POST.get('admin_email', '').strip()
        cs.require_email_verification = request.POST.get('require_email_verification') == '1'
        
        # Optional SMTP fallback
        cs.smtp_host = request.POST.get('smtp_host', '').strip()
        try:
            cs.smtp_port = int(request.POST.get('smtp_port', '587'))
        except (ValueError, TypeError):
            cs.smtp_port = 587
        cs.smtp_user = request.POST.get('smtp_user', '').strip()
        if request.POST.get('smtp_password'):
            cs.smtp_password = request.POST.get('smtp_password', '').strip()
        cs.smtp_use_tls = request.POST.get('smtp_use_tls') == '1'
        
        cs.save()
        messages.success(request, 'Mailing system & Resend configuration saved successfully.')
    return redirect('/management/#email')


@staff_required
def admin_send_test_email(request):
    """Trigger a live test message to verify Resend or SMTP delivery"""
    if request.method == 'POST':
        to_email = request.POST.get('test_email', '').strip()
        if not to_email:
            to_email = request.user.email or CompanySetting.get_settings().admin_email
        if not to_email:
            messages.error(request, 'Please provide a destination email address to send the test message.')
            return redirect('/management/#email')
        
        try:
            ok, msg_text = otp.send_test_email(to_email)
            messages.success(request, msg_text)
        except Exception as e:
            messages.error(request, f'Failed to send test email: {e}')
    return redirect('/management/#email')


@staff_required
def admin_save_asset(request):
    """Create / edit a tradable asset, or switch it on / off"""
    if request.method == 'POST':
        asset_id = request.POST.get('asset_id')
        try:
            price = Decimal(request.POST.get('base_price', '0'))
            vol = Decimal(request.POST.get('volatility', '1'))
            if price <= 0:
                raise ValueError()
        except Exception:
            messages.error(request, 'Enter a valid price.')
            return redirect('/management/#markets')
        data = dict(
            name=request.POST.get('name', '').strip(),
            category=request.POST.get('category', 'crypto'),
            base_price=price, volatility=vol,
            is_active=request.POST.get('is_active') == '1',
        )
        if asset_id:
            a = get_object_or_404(TradingAsset, id=asset_id)
            for k, v in data.items():
                setattr(a, k, v)
            a.save()
            messages.success(request, f"{a.symbol} updated.")
        else:
            sym = request.POST.get('symbol', '').strip().upper()[:12]
            if not sym or TradingAsset.objects.filter(symbol=sym).exists():
                messages.error(request, 'Pick a unique symbol.')
                return redirect('/management/#markets')
            TradingAsset.objects.create(symbol=sym, decimals=4 if price < 10 else 3, **data)
            messages.success(request, f"{sym} added to the markets.")
    return redirect('/management/#markets')


# ---------------- STATIC PAGES ----------------

def privacy(request):
    return render(request, 'legal.html', {'page': 'privacy', 'settings': CompanySetting.get_settings()})


def terms(request):
    return render(request, 'legal.html', {'page': 'terms', 'settings': CompanySetting.get_settings()})


def robots_txt(request):
    from django.http import HttpResponse
    return HttpResponse("User-agent: *\nAllow: /\nDisallow: /dashboard/\nDisallow: /management/\nDisallow: /admin/\nDisallow: /api/\n", content_type='text/plain')


def error_404(request, exception=None):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)


# ---------------- ADMIN PORTAL SIGN-IN (separate from investors) ----------------

def _admin_throttle_key(request, ident):
    ip = (request.META.get('HTTP_X_FORWARDED_FOR', '') or request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
    return f"adminlogin:{ip}:{ident.lower()[:60]}"


def admin_login(request):
    """Admin / staff sign-in at /management/login/. Investors cannot use it."""
    from django.core.cache import cache
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_management')
    if request.method == 'POST':
        ident = request.POST.get('identifier', '').strip()
        password = request.POST.get('password', '')
        key = _admin_throttle_key(request, ident)
        if cache.get(key, 0) >= 5:
            messages.error(request, 'Too many attempts. Please wait 15 minutes and try again.')
            return render(request, 'management/login.html', {'ident': ident}, status=429)
        user = authenticate(request, username=ident, password=password)
        if not user and '@' in ident:
            u = User.objects.filter(email__iexact=ident).first()
            user = authenticate(request, username=u.username, password=password) if u else None
        if user is not None and user.is_staff and user.is_active:
            cache.delete(key)
            login(request, user)
            request.session.set_expiry(60 * 60 * 8)   # admin sessions last one working day
            nxt = request.GET.get('next', '')
            from django.utils.http import url_has_allowed_host_and_scheme
            if (nxt.startswith('/management') or nxt.startswith('/mail')) and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect('admin_management')
        cache.set(key, cache.get(key, 0) + 1, 15 * 60)
        messages.error(request, 'Those details are not right, or this account is not an administrator.')
        return render(request, 'management/login.html', {'ident': ident}, status=200)
    return render(request, 'management/login.html')


def admin_logout(request):
    logout(request)
    messages.info(request, 'You have signed out of the admin portal.')
    return redirect('admin_login')
