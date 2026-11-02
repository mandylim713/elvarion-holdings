import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'elvarion_project.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from core.models import (
    UserProfile, InvestmentArea, InvestmentPlan, UserInvestment,
    LoanTierCriteria, LoanTermConfig, LoanApplication,
    Transaction, CompanySetting
)

def run():
    print("[+] Seeding Elvarion Holdings database...")

    # 1. Company Settings
    company, _ = CompanySetting.objects.get_or_create(id=1)
    company.site_name = "Elvarion Holdings"
    company.domain = "elvarionholdings.com"
    company.support_email = "concierge@elvarionholdings.com"
    company.corporate_address = "Tower 49, 12 East 49th Street, New York, NY 10017"
    company.btc_wallet_address = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    company.usdt_trc20_address = "TYDzsYUEpvnYmQk4zGP9sWWcTEd3GLGVbC"
    company.usdt_erc20_address = "0x71C8360f3E242cfE31FaD5598585483f982D19a5"
    company.eth_wallet_address = "0x71C8360f3E242cfE31FaD5598585483f982D19a5"
    company.bank_name = "JPMorgan Chase & Co. Private Wealth"
    company.bank_account_name = "Elvarion Holdings Institutional Reserve LLC"
    company.bank_account_number = "982038472910"
    company.bank_routing_swift = "CHASUS33 / Routing: 021000021"
    company.save()
    print("[*] Company settings configured")

    # 2. Investment Areas
    areas_data = [
        {
            'name': 'Real-Estate Investment',
            'slug': 'real-estate-investment',
            'tagline': 'Institutional grade commercial towers, logistics hubs & luxury residential portfolios',
            'description': 'Direct equity and structured debt participations in prime international real estate assets generating stable quarterly appreciation and premier leasehold yields.',
            'icon': 'building',
            'risk_level': 'Low - Moderate',
            'expected_roi_range': '12.5% - 32.0%',
            'order': 1,
        },
        {
            'name': 'Gold Investment',
            'slug': 'gold-investment',
            'tagline': 'LBMA-certified physical gold bullion securely vaulted in Zurich & Singapore',
            'description': 'Physical allocated bullion ownership combined with institutional precious metals arbitrage to hedge against fiat debasement and capture steady commodity yield.',
            'icon': 'coins',
            'risk_level': 'Conservative',
            'expected_roi_range': '4.8% - 24.0%',
            'order': 2,
        },
        {
            'name': 'Trust Fund Investment',
            'slug': 'trust-fund-investment',
            'tagline': 'Bespoke multi-generational trust structures, asset protection & endowment growth',
            'description': 'Tax-optimized diversified fiduciary trusts managed under strict statutory governance, delivering predictable high-yield compounding across sovereign debt and blue-chip equities.',
            'icon': 'shield-alt',
            'risk_level': 'Balanced Growth',
            'expected_roi_range': '8.5% - 45.0%',
            'order': 3,
        },
        {
            'name': 'Money Market Mutual Funds',
            'slug': 'money-market-mutual-funds',
            'tagline': 'Ultra-short duration sovereign bills, commercial paper & overnight repo yield',
            'description': 'Maximum capital liquidity with daily dividend accruals backed by top-tier government securities, central bank deposits, and investment-grade corporate instruments.',
            'icon': 'chart-pie',
            'risk_level': 'Ultra Low',
            'expected_roi_range': '0.65% Daily - 18.5% Yearly',
            'order': 4,
        },
    ]

    areas = {}
    for a in areas_data:
        obj, _ = InvestmentArea.objects.update_or_create(slug=a['slug'], defaults=a)
        areas[a['slug']] = obj
    print("[*] 4 Investment Areas created")

    # 3. Investment Plans with custom durations (daily, weekly, monthly, yearly) and ROIs
    plans_data = [
        # Real-Estate
        {
            'area': areas['real-estate-investment'],
            'title': 'Metropolitan Commercial REIT',
            'min_deposit': Decimal('5000.00'),
            'max_deposit': Decimal('250000.00'),
            'roi_percentage': Decimal('12.50'),
            'duration_unit': 'monthly',
            'duration_count': 6,
            'capital_returned': True,
            'badge': 'PREMIER YIELD',
            'is_featured': True,
            'description': 'Targeting Grade-A office parks and metropolitan medical complexes with 98% long-term tenancy.',
            'features_list': '12.5% Monthly Payout\nPrincipal Returned at Maturity\nSecured by Real Property Deeds\nVIP Investor Quarterly Briefings',
        },
        {
            'area': areas['real-estate-investment'],
            'title': 'Luxury Residential Developments',
            'min_deposit': Decimal('15000.00'),
            'max_deposit': Decimal('1000000.00'),
            'roi_percentage': Decimal('32.00'),
            'duration_unit': 'yearly',
            'duration_count': 1,
            'capital_returned': True,
            'badge': 'HIGH CAPITAL GROWTH',
            'is_featured': False,
            'description': 'Pre-development financing in high-demand coastal resort and luxury urban properties.',
            'features_list': '32% Annualized Return\nInsured Escrow Protection\nDirect Equity Valuation upside\nDedicated Account Officer',
        },
        {
            'area': areas['real-estate-investment'],
            'title': 'Logistics Infrastructure Syndicate',
            'min_deposit': Decimal('2500.00'),
            'max_deposit': Decimal('150000.00'),
            'roi_percentage': Decimal('3.20'),
            'duration_unit': 'weekly',
            'duration_count': 12,
            'capital_returned': True,
            'badge': 'WEEKLY YIELD',
            'is_featured': False,
            'description': 'Distribution centers leased to multinational ecommerce conglomerates.',
            'features_list': '3.2% Weekly Payout\n12 Weeks Fixed Term\nLiquid weekly withdrawals\nZero Maintenance Fee',
        },

        # Gold
        {
            'area': areas['gold-investment'],
            'title': 'Swiss Vault Sovereign Bullion',
            'min_deposit': Decimal('3000.00'),
            'max_deposit': Decimal('500000.00'),
            'roi_percentage': Decimal('4.80'),
            'duration_unit': 'monthly',
            'duration_count': 3,
            'capital_returned': True,
            'badge': 'SECURE HAVEN',
            'is_featured': True,
            'description': 'Allocated physical bars stored in high-security bonded vaults in Zurich and Geneva.',
            'features_list': '4.8% Monthly ROI\n100% Allocated Gold Serial Numbers\nLloyds of London Insurance\nPhysical Delivery Option upon Request',
        },
        {
            'area': areas['gold-investment'],
            'title': 'Precious Metals Arbitrage',
            'min_deposit': Decimal('10000.00'),
            'max_deposit': Decimal('750000.00'),
            'roi_percentage': Decimal('24.00'),
            'duration_unit': 'yearly',
            'duration_count': 1,
            'capital_returned': True,
            'badge': 'COMPOUNDING',
            'is_featured': False,
            'description': 'Capitalizes on spot-futures spreads across London, New York and Shanghai gold exchanges.',
            'features_list': '24% Annual Return\nZero Counterparty Fiat Risk\nAudited by Ernst & Young\nQuarterly Valuation Statements',
        },
        {
            'area': areas['gold-investment'],
            'title': 'Fast-Track Bullion Liquidity',
            'min_deposit': Decimal('1500.00'),
            'max_deposit': Decimal('50000.00'),
            'roi_percentage': Decimal('1.10'),
            'duration_unit': 'daily',
            'duration_count': 30,
            'capital_returned': True,
            'badge': 'DAILY PAYOUT',
            'is_featured': False,
            'description': 'Short-cycle physical settlement liquidity pool with daily returns.',
            'features_list': '1.1% Daily Payout\n30 Days Cycle\nReal-time Accrual Ticker\nPrincipal returned on day 30',
        },

        # Trust Fund
        {
            'area': areas['trust-fund-investment'],
            'title': 'Global Heritage Wealth Trust',
            'min_deposit': Decimal('20000.00'),
            'max_deposit': Decimal('2000000.00'),
            'roi_percentage': Decimal('8.50'),
            'duration_unit': 'monthly',
            'duration_count': 12,
            'capital_returned': True,
            'badge': 'INSTITUTIONAL',
            'is_featured': True,
            'description': 'Multi-asset fiduciary trust structured for high-net-worth families and institutional endowments.',
            'features_list': '8.5% Monthly Guaranteed Dividend\n12 Months Comprehensive Term\nComplete Estate Asset Ringfencing\nBespoke Tax-Efficient Architecture',
        },
        {
            'area': areas['trust-fund-investment'],
            'title': 'Sovereign Endowment Trust',
            'min_deposit': Decimal('50000.00'),
            'max_deposit': Decimal('5000000.00'),
            'roi_percentage': Decimal('45.00'),
            'duration_unit': 'yearly',
            'duration_count': 2,
            'capital_returned': True,
            'badge': 'HIGH WATERMARK',
            'is_featured': False,
            'description': 'Multi-year capital compounding backed by supranational bonds and infrastructure concessions.',
            'features_list': '45% Annual Compound ROI\nCapital Protection Guarantee\nExclusive Private Banker Assigned\nAccess to Private Placement Deals',
        },

        # Money Market Mutual Funds
        {
            'area': areas['money-market-mutual-funds'],
            'title': 'Institutional Daily Liquidity Fund',
            'min_deposit': Decimal('1000.00'),
            'max_deposit': Decimal('500000.00'),
            'roi_percentage': Decimal('0.65'),
            'duration_unit': 'daily',
            'duration_count': 14,
            'capital_returned': True,
            'badge': 'ULTRA-FLEXIBLE',
            'is_featured': True,
            'description': 'Invested exclusively in overnight US Treasury repurchase agreements and Tier-1 commercial notes.',
            'features_list': '0.65% Daily Compounding\n14 Days Rolling Cycle\nInstant Liquidity Access\nZero Risk of Principal Drawdown',
        },
        {
            'area': areas['money-market-mutual-funds'],
            'title': 'Treasury Yield Mutual Portfolio',
            'min_deposit': Decimal('5000.00'),
            'max_deposit': Decimal('750000.00'),
            'roi_percentage': Decimal('6.20'),
            'duration_unit': 'monthly',
            'duration_count': 6,
            'capital_returned': True,
            'badge': 'STEADY YIELD',
            'is_featured': False,
            'description': 'Short-duration sovereign and sub-sovereign obligations with monthly interest crediting.',
            'features_list': '6.2% Monthly Interest\n6 Months Maturity\nGuaranteed Fixed Return\nAAA Rated Collateral',
        },
    ]

    for p in plans_data:
        InvestmentPlan.objects.update_or_create(
            area=p['area'],
            title=p['title'],
            defaults=p
        )
    print("[*] Investment Plans configured")

    # 4. Loan Tier Criteria as requested:
    # 25k eligible for 300-799k
    # 50k eligible for 800k-1m
    # 100k eligible for 2m-4.99m 
    # 150k for 5m 
    tier_criteria = [
        {
            'tier_name': 'Silver Private Credit',
            'min_deposit_required': Decimal('25000.00'),
            'min_loan_amount': Decimal('300000.00'),
            'max_loan_amount': Decimal('799000.00'),
            'badge': 'SILVER QUALIFIED',
            'perks_description': 'Unlocks up to $799,000 credit line with 0.5% monthly interest on 6m repayment or 1.0% on 12m repayment.',
            'order': 1,
        },
        {
            'tier_name': 'Gold Executive Credit',
            'min_deposit_required': Decimal('50000.00'),
            'min_loan_amount': Decimal('800000.00'),
            'max_loan_amount': Decimal('1000000.00'),
            'badge': 'GOLD QUALIFIED',
            'perks_description': 'Unlocks up to $1,000,000 credit line with priority expedited approval and flexible liquidity.',
            'order': 2,
        },
        {
            'tier_name': 'Diamond Sovereign Credit',
            'min_deposit_required': Decimal('100000.00'),
            'min_loan_amount': Decimal('2000000.00'),
            'max_loan_amount': Decimal('4990000.00'),
            'badge': 'DIAMOND QUALIFIED',
            'perks_description': 'Unlocks up to $4,990,000 institutional credit facility with dedicated underwriting concierge.',
            'order': 3,
        },
        {
            'tier_name': 'Chairman Elite Syndicate Credit',
            'min_deposit_required': Decimal('150000.00'),
            'min_loan_amount': Decimal('5000000.00'),
            'max_loan_amount': Decimal('5000000.00'),
            'badge': 'CHAIRMAN TIER',
            'perks_description': 'Unlocks the maximum $5,000,000 private credit facility with tailored repayment structures.',
            'order': 4,
        },
    ]

    for t in tier_criteria:
        LoanTierCriteria.objects.update_or_create(
            tier_name=t['tier_name'],
            defaults=t
        )
    print("[*] Loan Tier Criteria (25k->300k-799k, 50k->800k-1m, 100k->2m-4.99m, 150k->5m) configured")

    # 5. Loan Term Configurations:
    # Interest of 0.5 percent per month for six months repayment. 1.0 percent interest for per month for yearly repayment
    terms_data = [
        {
            'term_months': 6,
            'monthly_interest_rate': Decimal('0.50'),
            'label': '6 Months Semi-Annual Facility',
            'description': '0.50% interest per month (Total 3.0% interest for 6 months)',
        },
        {
            'term_months': 12,
            'monthly_interest_rate': Decimal('1.00'),
            'label': '12 Months Annual Facility',
            'description': '1.00% interest per month (Total 12.0% interest for 1 year)',
        },
    ]
    for term in terms_data:
        LoanTermConfig.objects.update_or_create(
            term_months=term['term_months'],
            defaults=term
        )
    print("[*] Loan Term Configs (6 months @ 0.5%/mo & 12 months @ 1.0%/mo) configured")

    # 6. Admin User
    admin_user, created = User.objects.get_or_create(username='admin')
    if created:
        admin_user.set_password('Admin@12345')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.first_name = 'Admin'
        admin_user.last_name = 'Director'
        admin_user.email = 'admin@elvarionholdings.com'
        admin_user.save()
        UserProfile.objects.get_or_create(user=admin_user, defaults={'wallet_balance': Decimal('1000000.00')})
        print("[*] Created Superuser Admin: admin / Admin@12345")
    else:
        admin_user.set_password('Admin@12345')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

    # 7. Demo VIP Investor with $75,000 deposits (qualifying for Gold Tier $800k - $1M loan!)
    vip_user, created = User.objects.get_or_create(username='vip_investor')
    vip_user.set_password('Investor@12345')
    vip_user.first_name = 'Alexander'
    vip_user.last_name = 'Vanderbilt'
    vip_user.email = 'alexander.v@elvarionholdings.com'
    vip_user.save()

    profile, _ = UserProfile.objects.get_or_create(user=vip_user)
    profile.wallet_balance = Decimal('38500.00')
    profile.total_deposited = Decimal('75000.00') # Meets Tier 2 (50k -> 800k - 1M)
    profile.kyc_status = 'verified'
    profile.save()

    # Create active investments across multiple areas to demonstrate real-time reading ROI
    reit_plan = InvestmentPlan.objects.filter(area__slug='real-estate-investment').first()
    gold_plan = InvestmentPlan.objects.filter(area__slug='gold-investment', duration_unit='daily').first()
    trust_plan = InvestmentPlan.objects.filter(area__slug='trust-fund-investment').first()

    now = timezone.now()
    if not UserInvestment.objects.filter(user=vip_user).exists():
        if reit_plan:
            # Started 14 days ago
            start_1 = now - timedelta(days=14)
            end_1 = start_1 + timedelta(seconds=reit_plan.total_duration_seconds)
            inv1 = UserInvestment.objects.create(
                user=vip_user,
                plan=reit_plan,
                amount=Decimal('25000.00'),
                start_date=start_1,
                end_date=end_1,
                status='active'
            )
        if gold_plan:
            # Started 5 days ago
            start_2 = now - timedelta(days=5)
            end_2 = start_2 + timedelta(seconds=gold_plan.total_duration_seconds)
            inv2 = UserInvestment.objects.create(
                user=vip_user,
                plan=gold_plan,
                amount=Decimal('10000.00'),
                start_date=start_2,
                end_date=end_2,
                status='active'
            )
        if trust_plan:
            # Started 3 days ago
            start_3 = now - timedelta(days=3)
            end_3 = start_3 + timedelta(seconds=trust_plan.total_duration_seconds)
            inv3 = UserInvestment.objects.create(
                user=vip_user,
                plan=trust_plan,
                amount=Decimal('20000.00'),
                start_date=start_3,
                end_date=end_3,
                status='active'
            )
        print("[*] Created 3 live active investments across Real-Estate, Gold, and Trust Fund")

    # Create demo transactions
    if not Transaction.objects.filter(user=vip_user).exists():
        Transaction.objects.create(
            user=vip_user,
            txn_type='deposit',
            amount=Decimal('50000.00'),
            description='Bank Wire Institutional Deposit - Verified',
            is_credit=True
        )
        Transaction.objects.create(
            user=vip_user,
            txn_type='deposit',
            amount=Decimal('25000.00'),
            description='USDT (TRC-20) Liquidity Injection',
            is_credit=True
        )
        Transaction.objects.create(
            user=vip_user,
            txn_type='investment',
            amount=Decimal('25000.00'),
            description='Allocation to Metropolitan Commercial REIT',
            is_credit=False
        )

    print("[SUCCESS] Database seeding complete! Ready for launch.")

if __name__ == '__main__':
    run()
