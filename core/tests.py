from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import (
    UserProfile, InvestmentArea, InvestmentPlan,
    LoanTierCriteria, LoanTermConfig, LoanApplication,
    DepositRequest, KYCSubmission, CompanySetting
)


class BaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.settings = CompanySetting.get_settings()
        
        # Configure Loan Tiers
        self.tier1 = LoanTierCriteria.objects.create(
            tier_name='Bronze Executive Line',
            min_deposit_required=Decimal('25000.00'),
            min_loan_amount=Decimal('300000.00'),
            max_loan_amount=Decimal('799000.00'),
            badge='BRONZE',
            order=1
        )
        self.tier2 = LoanTierCriteria.objects.create(
            tier_name='Gold Sovereign Syndicate',
            min_deposit_required=Decimal('50000.00'),
            min_loan_amount=Decimal('800000.00'),
            max_loan_amount=Decimal('1000000.00'),
            badge='GOLD',
            order=2
        )

        # Admin user
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@elvarion.test',
            password='AdminPassword123!'
        )
        UserProfile.objects.create(user=self.admin_user, kyc_status='verified')


class TestAuthenticationAndRegistration(BaseTestCase):
    def test_successful_registration(self):
        """Test institutional registration with classification and profile setup"""
        data = {
            'full_name': 'Lord Alexander Sterling',
            'account_type': 'corporate',
            'username': 'sterling_test',
            'email': 'alexander@sterling-holdings.test',
            'country': 'United Kingdom',
            'phone_code': '+44',
            'phone': '7911 123456',
            'password': 'VaultSecurePassword123!',
            'password_confirm': 'VaultSecurePassword123!',
        }
        response = self.client.post(reverse('register'), data, follow=True)
        self.assertEqual(response.status_code, 200)

        user = User.objects.get(username='sterling_test')
        self.assertEqual(user.first_name, 'Lord')
        self.assertEqual(user.last_name, 'Alexander Sterling')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.account_type, 'corporate')
        self.assertEqual(user.profile.country, 'United Kingdom')
        self.assertEqual(user.profile.kyc_status, 'unverified')

    def test_registration_password_mismatch(self):
        """Test registration rejection when passwords do not match"""
        data = {
            'full_name': 'Test Investor',
            'username': 'mismatch_user',
            'email': 'mismatch@test.com',
            'password': 'Password123!',
            'password_confirm': 'DifferentPassword123!',
        }
        response = self.client.post(reverse('register'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='mismatch_user').exists())

    def test_login_with_username_and_email(self):
        """Test client authentication using username as well as email"""
        user = User.objects.create_user(
            username='client_alpha',
            email='alpha@privatevault.test',
            password='ClientPassword123!'
        )
        UserProfile.objects.create(user=user)

        # Test login with username
        resp1 = self.client.post(reverse('login'), {
            'identifier': 'client_alpha',
            'password': 'ClientPassword123!'
        }, follow=True)
        self.assertTrue(resp1.context['user'].is_authenticated)
        self.client.logout()

        # Test login with email
        resp2 = self.client.post(reverse('login'), {
            'identifier': 'alpha@privatevault.test',
            'password': 'ClientPassword123!'
        }, follow=True)
        self.assertTrue(resp2.context['user'].is_authenticated)


class TestKYCComplianceWorkflow(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='investor_kyc_test',
            email='investor@kyc.test',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            kyc_status='unverified',
            country='Switzerland'
        )

    def test_submit_kyc_dossier(self):
        """Test investor submitting full KYC compliance credentials"""
        self.client.login(username='investor_kyc_test', password='TestPassword123!')
        
        data = {
            'full_legal_name': 'Alexander von Sterling',
            'date_of_birth': '1982-04-12',
            'residential_address': 'Bahnhofstrasse 45',
            'city': 'Zurich',
            'postal_code': '8001',
            'country': 'Switzerland',
            'id_type': 'passport',
            'id_number': 'CH98402819',
            'source_of_wealth': 'investments',
            'estimated_net_worth': '$5,000,000 - $20,000,000',
            'pep_status': '0',
        }
        response = self.client.post(reverse('submit_kyc'), data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify submission created
        kyc = KYCSubmission.objects.get(user=self.user)
        self.assertEqual(kyc.full_legal_name, 'Alexander von Sterling')
        self.assertEqual(kyc.id_number, 'CH98402819')
        self.assertEqual(kyc.status, 'pending')

        # Verify user profile status set to pending
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.kyc_status, 'pending')

    def test_admin_approve_and_reject_kyc(self):
        """Test compliance director approving KYC submission and upgrading profile"""
        kyc = KYCSubmission.objects.create(
            user=self.user,
            full_legal_name='Alexander von Sterling',
            residential_address='Bahnhofstrasse 45',
            city='Zurich',
            postal_code='8001',
            country='Switzerland',
            id_type='passport',
            id_number='CH98402819',
            status='pending'
        )
        self.profile.kyc_status = 'pending'
        self.profile.save()

        # Admin logs in and approves KYC
        self.client.login(username='admin_test', password='AdminPassword123!')
        url = reverse('admin_kyc_action', kwargs={'submission_id': kyc.id, 'action': 'approve'})
        resp = self.client.post(url, {'admin_notes': 'Verified against passport registry.'}, follow=True)
        self.assertEqual(resp.status_code, 200)

        kyc.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(kyc.status, 'approved')
        self.assertEqual(self.profile.kyc_status, 'verified')

        # Test reject action
        url_reject = reverse('admin_kyc_action', kwargs={'submission_id': kyc.id, 'action': 'reject'})
        resp_reject = self.client.post(url_reject, {'admin_notes': 'Document blurry.'}, follow=True)
        self.assertEqual(resp_reject.status_code, 200)

        kyc.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(kyc.status, 'rejected')
        self.assertEqual(self.profile.kyc_status, 'unverified')


class TestTreasuryDepositWorkflow(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='investor_deposit_test',
            email='deposit@investor.test',
            password='TestPassword123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            wallet_balance=Decimal('0.00'),
            total_deposited=Decimal('0.00')
        )

    def test_instant_demo_deposit_credits_wallet_and_unlocks_loan(self):
        """Test instant evaluation deposit immediately updates balance and unlocks Tier-1 loan"""
        self.client.login(username='investor_deposit_test', password='TestPassword123!')

        data = {
            'amount': '25000.00',
            'method': 'USDT_TRC20',
            'proof_hash': 'TRX89410294829104',
            'is_demo_instant': '1',
        }
        response = self.client.post(reverse('submit_deposit'), data, follow=True)
        self.assertEqual(response.status_code, 200)

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.wallet_balance, Decimal('25000.00'))
        self.assertEqual(self.profile.total_deposited, Decimal('25000.00'))

        # Check loan qualification unlocked Tier 1
        tier = self.profile.get_eligible_loan_tier()
        self.assertIsNotNone(tier)
        self.assertEqual(tier.tier_name, 'Bronze Executive Line')

    def test_pending_deposit_approved_by_admin(self):
        """Test standard deposit pending audit, approved by director desk"""
        self.client.login(username='investor_deposit_test', password='TestPassword123!')

        data = {
            'amount': '50000.00',
            'method': 'BANK_WIRE',
            'proof_hash': 'JPMC-WIRE-9820491',
            # No is_demo_instant
        }
        self.client.post(reverse('submit_deposit'), data, follow=True)

        dep = DepositRequest.objects.get(user=self.user)
        self.assertEqual(dep.status, 'pending')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.wallet_balance, Decimal('0.00'))

        # Admin logs in to approve deposit
        self.client.login(username='admin_test', password='AdminPassword123!')
        url = reverse('admin_deposit_action', kwargs={'deposit_id': dep.id, 'action': 'approve'})
        resp = self.client.post(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        dep.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(dep.status, 'approved')
        self.assertEqual(self.profile.wallet_balance, Decimal('50000.00'))
        self.assertEqual(self.profile.total_deposited, Decimal('50000.00'))

        # Check tier 2 unlocked
        tier = self.profile.get_eligible_loan_tier()
        self.assertEqual(tier.tier_name, 'Gold Sovereign Syndicate')
