import json
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
    KYCSubmission
)

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

        if len(password) < 6:
            messages.error(request, 'Security requirement: Password must be at least 6 characters.')
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
        messages.success(request, f'Welcome to Elvarion Holdings Private Wealth, {user.first_name or user.username}. Your secure vault has been provisioned.')
        return redirect('dashboard')

    return render(request, 'auth/register.html')


def login_view(request):
    """User and admin sign-in with session remember option"""
    if request.user.is_authenticated:
        return redirect('dashboard')

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

        if user is not None:
            login(request, user)
            if remember_me:
                request.session.set_expiry(1209600)  # 2 weeks
            else:
                request.session.set_expiry(0)  # On browser close

            # Ensure profile exists
            UserProfile.objects.get_or_create(user=user)
            messages.success(request, f'Vault unlocked. Welcome back, {user.first_name or user.username}.')
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if user.is_staff:
                return redirect('admin_management')
            return redirect('dashboard')
        else:
            messages.error(request, 'Authentication failed. Please verify your credentials or contact Treasury Concierge.')

    return render(request, 'auth/login.html')


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been securely signed out.')
    return redirect('home')


@login_required
def dashboard(request):
    """Client Portal Dashboard with Live ROI reader, portfolio, loan session, and wallet"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
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

    context = {
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
    is_demo_instant = request.POST.get('is_demo_instant') == '1'

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

    # If demo instant funding mode is toggled, credit immediately for testing/demo
    if is_demo_instant:
        deposit.status = 'approved'
        deposit.processed_at = timezone.now()
        deposit.admin_notes = 'Instant Demo Simulation Credit'
        deposit.save()

        profile.wallet_balance += amount
        profile.total_deposited += amount
        profile.save()

        Transaction.objects.create(
            user=request.user,
            txn_type='deposit',
            amount=amount,
            description=f"Instant Test Deposit ({deposit.get_method_display()})",
            is_credit=True
        )
        messages.success(request, f"Instant Demo: Credited ${amount:,.2f} to your account! Cumulative deposit is now ${profile.total_deposited:,.2f}.")
    else:
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

    messages.success(request, f"Withdrawal request for ${amount:,.2f} submitted for treasury dispatch.")
    return redirect('dashboard')


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
            'accrued_roi': round(accrued, 4),
            'progress_percentage': round(inv.get_progress_percentage(), 2),
            'status': inv.status,
        })

    return JsonResponse({
        'status': 'success',
        'server_time': timezone.now().isoformat(),
        'total_accrued_roi': round(total_accrued, 4),
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
    messages.success(request, f'KYC Dossier #{ref_id} submitted successfully. Our Compliance Desk will verify your credentials within 2 business hours.')
    return redirect('dashboard')


# ---------------- ADMIN MANAGEMENT PORTAL ----------------

@user_passes_test(lambda u: u.is_staff)
def admin_management(request):
    """Executive Admin Management View for quick control over areas, plans, loans, KYC, and deposits"""
    pending_loans = LoanApplication.objects.filter(status='pending')
    all_loans = LoanApplication.objects.all()[:20]
    pending_deposits = DepositRequest.objects.filter(status='pending')
    pending_withdrawals = WithdrawalRequest.objects.filter(status='pending')
    pending_kyc = KYCSubmission.objects.filter(status='pending')
    all_kyc = KYCSubmission.objects.all().order_by('-submitted_at')[:25]
    
    investment_areas = InvestmentArea.objects.all()
    plans = InvestmentPlan.objects.all()
    loan_tiers = LoanTierCriteria.objects.all()
    loan_terms = LoanTermConfig.objects.all()
    users = User.objects.all().select_related('profile')

    context = {
        'pending_loans': pending_loans,
        'all_loans': all_loans,
        'pending_deposits': pending_deposits,
        'pending_withdrawals': pending_withdrawals,
        'pending_kyc': pending_kyc,
        'all_kyc': all_kyc,
        'investment_areas': investment_areas,
        'plans': plans,
        'loan_tiers': loan_tiers,
        'loan_terms': loan_terms,
        'users': users,
        'settings': CompanySetting.get_settings(),
    }
    return render(request, 'management/index.html', context)


@user_passes_test(lambda u: u.is_staff)
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

    return redirect('admin_management')


@user_passes_test(lambda u: u.is_staff)
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

    return redirect('admin_management')


@user_passes_test(lambda u: u.is_staff)
def admin_deposit_action(request, deposit_id, action):
    """Admin approves or rejects a deposit"""
    deposit = get_object_or_404(DepositRequest, id=deposit_id)

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
        messages.success(request, f"Deposit #{dep_ref} for ${deposit.amount:,.2f} approved and credited to {deposit.user.username}.")
    elif action == 'reject':
        deposit.status = 'rejected'
        deposit.processed_at = timezone.now()
        deposit.save()
        messages.warning(request, f"Deposit #{str(deposit.reference_id)[:8]} rejected.")

    return redirect('admin_management')


@user_passes_test(lambda u: u.is_staff)
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

    return redirect('admin_management')


@user_passes_test(lambda u: u.is_staff)
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

    return redirect('admin_management')
