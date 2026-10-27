from django.contrib import admin
from django.utils import timezone
from .models import (
    UserProfile, InvestmentArea, InvestmentPlan, UserInvestment,
    LoanTierCriteria, LoanTermConfig, LoanApplication,
    DepositRequest, WithdrawalRequest, Transaction, CompanySetting,
    KYCSubmission
)

@admin.register(KYCSubmission)
class KYCSubmissionAdmin(admin.ModelAdmin):
    list_display = ('full_legal_name', 'user', 'id_type', 'id_number', 'source_of_wealth', 'status', 'submitted_at')
    list_filter = ('status', 'id_type', 'submitted_at')
    search_fields = ('full_legal_name', 'user__username', 'user__email', 'id_number')
    readonly_fields = ('submission_id', 'submitted_at')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'wallet_balance', 'loan_balance', 'total_deposited', 'total_roi_earned', 'kyc_status', 'created_at')
    list_editable = ('wallet_balance', 'loan_balance', 'total_deposited', 'kyc_status')
    search_fields = ('user__username', 'user__email', 'phone', 'country')
    list_filter = ('kyc_status', 'created_at')


class InvestmentPlanInline(admin.TabularInline):
    model = InvestmentPlan
    extra = 1
    fields = ('title', 'min_deposit', 'max_deposit', 'roi_percentage', 'duration_unit', 'duration_count', 'capital_returned', 'is_active')


@admin.register(InvestmentArea)
class InvestmentAreaAdmin(admin.ModelAdmin):
    list_display = ('name', 'tagline', 'risk_level', 'expected_roi_range', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [InvestmentPlanInline]
    search_fields = ('name', 'description')


@admin.register(InvestmentPlan)
class InvestmentPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'area', 'roi_percentage', 'duration_unit', 'duration_count', 'min_deposit', 'max_deposit', 'is_featured', 'is_active')
    list_editable = ('roi_percentage', 'duration_unit', 'duration_count', 'min_deposit', 'max_deposit', 'is_active')
    list_filter = ('area', 'duration_unit', 'is_active', 'is_featured')
    search_fields = ('title', 'area__name')
    fieldsets = (
        ('Plan Details', {
            'fields': ('area', 'title', 'badge', 'is_featured', 'is_active')
        }),
        ('Financial Terms & ROI', {
            'description': 'Configure the exact return on investment and duration cycle (daily, weekly, monthly, yearly)',
            'fields': (
                ('roi_percentage', 'duration_unit', 'duration_count'),
                ('min_deposit', 'max_deposit'),
                'capital_returned'
            )
        }),
        ('Information & Bullets', {
            'fields': ('description', 'features_list')
        })
    )


@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'start_date', 'end_date', 'status', 'total_projected_roi', 'accumulated_roi')
    list_filter = ('status', 'plan__area', 'start_date')
    search_fields = ('user__username', 'plan__title', 'reference_id')
    readonly_fields = ('reference_id', 'created_at', 'last_roi_update')
    actions = ['mark_as_completed', 'pause_investments']

    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
    mark_as_completed.short_description = "Mark selected investments as completed"

    def pause_investments(self, request, queryset):
        queryset.update(status='paused')
    pause_investments.short_description = "Pause selected investments"


@admin.register(LoanTierCriteria)
class LoanTierCriteriaAdmin(admin.ModelAdmin):
    list_display = ('tier_name', 'badge', 'min_deposit_required', 'min_loan_amount', 'max_loan_amount', 'order', 'is_active')
    list_editable = ('min_deposit_required', 'min_loan_amount', 'max_loan_amount', 'order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('tier_name', 'badge')
    ordering = ('min_deposit_required',)


@admin.register(LoanTermConfig)
class LoanTermConfigAdmin(admin.ModelAdmin):
    list_display = ('term_months', 'monthly_interest_rate', 'label', 'is_active')
    list_editable = ('monthly_interest_rate', 'label', 'is_active')


@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = ('loan_reference', 'user', 'amount_requested', 'term_months', 'monthly_interest_rate', 'total_repayable', 'status', 'applied_at')
    list_filter = ('status', 'term_months', 'applied_at')
    search_fields = ('loan_reference', 'user__username', 'user__email')
    readonly_fields = ('loan_reference', 'applied_at')
    actions = ['approve_and_disburse_loans', 'decline_loans']

    def approve_and_disburse_loans(self, request, queryset):
        for loan in queryset.filter(status='pending'):
            loan.status = 'approved'
            loan.reviewed_at = timezone.now()
            loan.disbursed_at = timezone.now()
            loan.disbursed_to_wallet = True
            loan.save()
            
            # Credit user's loan balance and create transaction
            profile = loan.user.profile
            profile.loan_balance += loan.amount_requested
            profile.save()

            Transaction.objects.create(
                user=loan.user,
                txn_type='loan_disbursement',
                amount=loan.amount_requested,
                description=f"Approved Loan Disbursement ({loan.term_months} Months @ {loan.monthly_interest_rate}%/mo)",
                is_credit=True
            )
        self.message_user(request, f"{queryset.count()} loan application(s) approved and disbursed successfully.")
    approve_and_disburse_loans.short_description = "Approve & Disburse Selected Loans to User Wallet"

    def decline_loans(self, request, queryset):
        queryset.update(status='rejected', reviewed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} loan application(s) marked as declined.")
    decline_loans.short_description = "Decline Selected Loans"


@admin.register(DepositRequest)
class DepositRequestAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'user', 'amount', 'method', 'proof_hash', 'status', 'created_at')
    list_filter = ('status', 'method', 'created_at')
    search_fields = ('reference_id', 'user__username', 'proof_hash')
    actions = ['approve_deposits', 'reject_deposits']

    def approve_deposits(self, request, queryset):
        for deposit in queryset.filter(status='pending'):
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
                description=f"Verified Deposit ({deposit.get_method_display()})",
                is_credit=True
            )
        self.message_user(request, f"{queryset.count()} deposit(s) approved and credited.")
    approve_deposits.short_description = "Approve & Credit Selected Deposits"

    def reject_deposits(self, request, queryset):
        queryset.filter(status='pending').update(status='rejected', processed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} deposit(s) rejected.")
    reject_deposits.short_description = "Reject Selected Deposits"


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ('reference_id', 'user', 'amount', 'payout_method', 'status', 'created_at')
    list_filter = ('status', 'payout_method', 'created_at')
    search_fields = ('reference_id', 'user__username', 'destination_details')
    actions = ['approve_withdrawals', 'reject_withdrawals']

    def approve_withdrawals(self, request, queryset):
        queryset.filter(status='pending').update(status='approved', processed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} withdrawal(s) marked as approved and dispatched.")
    approve_withdrawals.short_description = "Approve Selected Withdrawals"

    def reject_withdrawals(self, request, queryset):
        for w in queryset.filter(status='pending'):
            w.status = 'rejected'
            w.processed_at = timezone.now()
            w.save()
            # Refund balance
            profile = w.user.profile
            profile.wallet_balance += w.amount
            profile.save()
        self.message_user(request, f"{queryset.count()} withdrawal(s) rejected and funds refunded.")
    reject_withdrawals.short_description = "Reject & Refund Selected Withdrawals"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'user', 'txn_type', 'amount', 'is_credit', 'created_at')
    list_filter = ('txn_type', 'is_credit', 'created_at')
    search_fields = ('reference', 'user__username', 'description')


@admin.register(CompanySetting)
class CompanySettingAdmin(admin.ModelAdmin):
    list_display = ('site_name', 'domain', 'support_email', 'bank_name')
