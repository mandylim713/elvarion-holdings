import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class UserProfile(models.Model):
    KYC_CHOICES = (
        ('unverified', 'Unverified'),
        ('pending', 'Pending Verification'),
        ('verified', 'Verified Tier-1'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=30, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='United States')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    
    # Financial Balances
    wallet_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    loan_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_deposited = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_withdrawn = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    total_roi_earned = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    
    kyc_status = models.CharField(max_length=20, choices=KYC_CHOICES, default='verified')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Profile (${self.wallet_balance:,.2f})"

    def get_eligible_loan_tier(self):
        """Calculates highest loan tier the user qualifies for based on cumulative deposits"""
        return LoanTierCriteria.objects.filter(
            is_active=True,
            min_deposit_required__lte=self.total_deposited
        ).order_by('-min_deposit_required').first()

    def get_all_eligible_tiers(self):
        return LoanTierCriteria.objects.filter(
            is_active=True,
            min_deposit_required__lte=self.total_deposited
        ).order_by('min_deposit_required')

    def get_next_loan_tier(self):
        """Returns the next tier to unlock if any"""
        return LoanTierCriteria.objects.filter(
            is_active=True,
            min_deposit_required__gt=self.total_deposited
        ).order_by('min_deposit_required').first()


class InvestmentArea(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    tagline = models.CharField(max_length=255)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='chart-line', help_text='Icon identifier e.g. building, coins, shield-alt, chart-pie')
    hero_image = models.CharField(max_length=255, blank=True, default='')
    risk_level = models.CharField(max_length=50, default='Low - Moderate')
    expected_roi_range = models.CharField(max_length=60, default='8% - 35%')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class InvestmentPlan(models.Model):
    DURATION_UNITS = (
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    )
    area = models.ForeignKey(InvestmentArea, on_delete=models.CASCADE, related_name='plans')
    title = models.CharField(max_length=150)
    min_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('1000.00'))
    max_deposit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('100000.00'))
    roi_percentage = models.DecimalField(max_digits=7, decimal_places=2, help_text='ROI percentage e.g. 5.5 for 5.5%')
    duration_unit = models.CharField(max_length=20, choices=DURATION_UNITS, default='monthly')
    duration_count = models.PositiveIntegerField(default=1, help_text='Number of duration units (e.g., 30 daily, 12 weekly, 6 monthly, 1 yearly)')
    capital_returned = models.BooleanField(default=True, help_text='Return initial capital at end of cycle')
    description = models.TextField(blank=True)
    features_list = models.TextField(blank=True, help_text='Newline-separated feature bullet points')
    badge = models.CharField(max_length=50, blank=True, default='POPULAR')
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['area', 'min_deposit']

    def __str__(self):
        return f"{self.title} ({self.area.name} - {self.roi_percentage}% {self.duration_unit.capitalize()})"

    @property
    def total_duration_seconds(self):
        """Converts duration to seconds for high-precision live ticking"""
        if self.duration_unit == 'daily':
            return self.duration_count * 86400
        elif self.duration_unit == 'weekly':
            return self.duration_count * 7 * 86400
        elif self.duration_unit == 'monthly':
            return self.duration_count * 30 * 86400
        elif self.duration_unit == 'yearly':
            return self.duration_count * 365 * 86400
        return 86400

    @property
    def total_expected_roi(self):
        """Total ROI percentage over the complete term"""
        return self.roi_percentage * self.duration_count


class UserInvestment(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active (Reading Live)'),
        ('paused', 'Paused'),
        ('completed', 'Completed & Matured'),
        ('cancelled', 'Cancelled'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.PROTECT, related_name='user_investments')
    reference_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    last_roi_update = models.DateTimeField(default=timezone.now)
    accumulated_roi = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal('0.0000'))
    total_projected_roi = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.plan.title} (${self.amount:,.2f})"

    def save(self, *args, **kwargs):
        if not self.end_date:
            duration_secs = self.plan.total_duration_seconds
            self.end_date = self.start_date + timedelta(seconds=duration_secs)
        if not self.total_projected_roi:
            total_pct = (self.plan.roi_percentage * self.plan.duration_count) / Decimal('100.0')
            self.total_projected_roi = self.amount * total_pct
        super().save(*args, **kwargs)

    def get_realtime_accrued_roi(self):
        """Calculates exact accrued ROI up to the current second"""
        if self.status != 'active':
            return float(self.accumulated_roi)
        now = timezone.now()
        if now >= self.end_date:
            return float(self.total_projected_roi)
        elapsed = (now - self.start_date).total_seconds()
        total_secs = (self.end_date - self.start_date).total_seconds()
        if total_secs <= 0:
            return 0.0
        fraction = min(1.0, max(0.0, elapsed / total_secs))
        return float(self.total_projected_roi) * fraction

    def get_progress_percentage(self):
        now = timezone.now()
        if now >= self.end_date:
            return 100.0
        elapsed = (now - self.start_date).total_seconds()
        total_secs = (self.end_date - self.start_date).total_seconds()
        if total_secs <= 0:
            return 0.0
        return min(100.0, max(0.0, (elapsed / total_secs) * 100.0))


class LoanTierCriteria(models.Model):
    """
    Admin-configured criteria: deposit threshold qualifies for loan range
    E.g.:
    $25k deposit -> $300k - $799k
    $50k deposit -> $800k - $1M
    $100k deposit -> $2M - $4.99M
    $150k deposit -> $5M
    """
    tier_name = models.CharField(max_length=100)
    min_deposit_required = models.DecimalField(max_digits=14, decimal_places=2, help_text='Cumulative deposit needed to unlock')
    min_loan_amount = models.DecimalField(max_digits=16, decimal_places=2)
    max_loan_amount = models.DecimalField(max_digits=16, decimal_places=2)
    badge = models.CharField(max_length=50, default='TIER 1')
    perks_description = models.TextField(blank=True, help_text='Privileges and terms included')
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['min_deposit_required']

    def __str__(self):
        return f"{self.tier_name}: Dep ${self.min_deposit_required:,.0f}+ -> Loan ${self.min_loan_amount:,.0f} - ${self.max_loan_amount:,.0f}"


class LoanTermConfig(models.Model):
    """
    Admin-configured loan terms:
    - 6 months repayment: 0.5% interest per month
    - 12 months repayment: 1.0% interest per month
    """
    term_months = models.PositiveIntegerField(unique=True, help_text='Duration in months, e.g. 6 or 12')
    monthly_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text='Monthly interest rate in %, e.g. 0.5 or 1.0')
    label = models.CharField(max_length=100, default='Standard Plan')
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['term_months']

    def __str__(self):
        return f"{self.term_months} Months ({self.monthly_interest_rate}% / month)"

    @property
    def total_interest_rate(self):
        return self.monthly_interest_rate * self.term_months


class LoanApplication(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Under Review'),
        ('approved', 'Approved & Disbursed'),
        ('rejected', 'Declined'),
        ('active', 'Active Repayment'),
        ('completed', 'Fully Repaid'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    loan_reference = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    tier = models.ForeignKey(LoanTierCriteria, on_delete=models.SET_NULL, null=True, blank=True)
    term_months = models.PositiveIntegerField(default=6)
    monthly_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.50'))
    
    amount_requested = models.DecimalField(max_digits=16, decimal_places=2)
    total_interest = models.DecimalField(max_digits=16, decimal_places=2)
    total_repayable = models.DecimalField(max_digits=16, decimal_places=2)
    monthly_installment = models.DecimalField(max_digits=16, decimal_places=2)
    total_repaid = models.DecimalField(max_digits=16, decimal_places=2, default=Decimal('0.00'))
    
    purpose = models.CharField(max_length=255, default='Portfolio Liquidity & Expansion')
    collateral_note = models.TextField(blank=True, help_text='Secured against investor asset portfolio')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True, default='')
    disbursed_to_wallet = models.BooleanField(default=False)
    
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-applied_at']

    def __str__(self):
        return f"Loan {self.loan_reference[:8]} - {self.user.username} (${self.amount_requested:,.2f}) [{self.status}]"

    def calculate_loan_breakdown(self):
        """Calculates exact interest, repayable amount and monthly installment"""
        # total interest = principal * (rate/100) * months
        self.total_interest = self.amount_requested * (self.monthly_interest_rate / Decimal('100.0')) * Decimal(self.term_months)
        self.total_repayable = self.amount_requested + self.total_interest
        self.monthly_installment = self.total_repayable / Decimal(self.term_months)


class DepositRequest(models.Model):
    METHOD_CHOICES = (
        ('BTC', 'Bitcoin (BTC)'),
        ('USDT_TRC20', 'USDT (TRC-20)'),
        ('USDT_ERC20', 'USDT (ERC-20)'),
        ('ETH', 'Ethereum (ETH)'),
        ('BANK_WIRE', 'International Bank Wire Transfer'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending Verification'),
        ('approved', 'Approved & Credited'),
        ('rejected', 'Declined'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposits')
    reference_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    method = models.CharField(max_length=25, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    proof_hash = models.CharField(max_length=255, blank=True, help_text='TxID or Bank Transfer Reference')
    receipt_image = models.ImageField(upload_to='receipts/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Deposit ${self.amount:,.2f} ({self.method}) by {self.user.username} [{self.status}]"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('approved', 'Approved & Dispatched'),
        ('rejected', 'Declined'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    reference_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    payout_method = models.CharField(max_length=50)
    destination_details = models.TextField(help_text='Crypto Wallet Address or Bank details')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal ${self.amount:,.2f} by {self.user.username} [{self.status}]"


class Transaction(models.Model):
    TYPE_CHOICES = (
        ('deposit', 'Wallet Deposit'),
        ('investment', 'Investment Allocation'),
        ('roi_payout', 'ROI Profit Accrual'),
        ('loan_disbursement', 'Loan Disbursement'),
        ('loan_repayment', 'Loan Repayment'),
        ('withdrawal', 'Withdrawal Request'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    txn_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    reference = models.CharField(max_length=64, unique=True, default=uuid.uuid4)
    description = models.CharField(max_length=255)
    is_credit = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        prefix = "+" if self.is_credit else "-"
        return f"{self.user.username}: {prefix}${self.amount:,.2f} ({self.get_txn_type_display()})"


class CompanySetting(models.Model):
    site_name = models.CharField(max_length=100, default='Elvarion Holdings')
    domain = models.CharField(max_length=100, default='elvarionholdings.com')
    support_email = models.CharField(max_length=100, default='support@elvarionholdings.com')
    corporate_address = models.CharField(max_length=255, default='One World Trade Center, Suite 8500, New York, NY 10007')
    
    # Hybrid Deposit Gateways
    btc_wallet_address = models.CharField(max_length=120, default='bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh')
    usdt_trc20_address = models.CharField(max_length=120, default='TYDzsYUEpvnYmQk4zGP9sWWcTEd3GLGVbC')
    usdt_erc20_address = models.CharField(max_length=120, default='0x71C8360f3E242cfE31FaD5598585483f982D19a5')
    eth_wallet_address = models.CharField(max_length=120, default='0x71C8360f3E242cfE31FaD5598585483f982D19a5')
    
    # Bank Wire Coordinates
    bank_name = models.CharField(max_length=120, default='JPMorgan Chase Private Bank')
    bank_account_name = models.CharField(max_length=150, default='Elvarion Holdings Private Wealth Ltd')
    bank_account_number = models.CharField(max_length=50, default='984028491823')
    bank_routing_swift = models.CharField(max_length=50, default='CHASUS33XXX / ABA 021000021')

    def __str__(self):
        return f"{self.site_name} Settings"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj
