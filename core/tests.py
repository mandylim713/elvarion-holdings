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

    def test_no_free_credit_shortcut(self):
        """A deposit can never credit itself, whatever the form says"""
        self.client.login(username='investor_deposit_test', password='TestPassword123!')
        self.client.post(reverse('submit_deposit'), {
            'amount': '25000.00', 'method': 'USDT_TRC20', 'proof_hash': 'TRX89410294829104', 'is_demo_instant': '1'}, follow=True)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.wallet_balance, Decimal('0.00'))
        self.assertEqual(DepositRequest.objects.get(user=self.user).status, 'pending')

    def test_pending_deposit_approved_by_admin(self):
        """Test standard deposit pending audit, approved by director desk"""
        self.client.login(username='investor_deposit_test', password='TestPassword123!')

        data = {
            'amount': '50000.00',
            'method': 'BANK_WIRE',
            'proof_hash': 'JPMC-WIRE-9820491',
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


# ---------------------------------------------------------------- new features
from datetime import timedelta
from unittest import mock
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from . import accrual, otp
from .models import UserInvestment, Transaction, TradingAsset, OptionTrade, EmailOTP


class TestRoiAccrual(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('roi_user', 'roi@example.com', 'Passw0rd!x')
        self.profile = UserProfile.objects.create(user=self.user, wallet_balance=Decimal('0.00'))
        area = InvestmentArea.objects.create(name='A', slug='a')
        self.plan = InvestmentPlan.objects.create(area=area, title='Daily 2%', roi_percentage=Decimal('2.00'),
                                                  duration_unit='daily', duration_count=10, capital_returned=True)

    def _inv(self, days_ago):
        start = timezone.now() - timedelta(days=days_ago)
        return UserInvestment.objects.create(user=self.user, plan=self.plan, amount=Decimal('1000.00'), start_date=start,
                                             end_date=start + timedelta(days=10), status='active')

    def test_roi_is_paid_into_wallet_and_not_twice(self):
        inv = self._inv(5)                      # half way: 10 days x 2% x 1000 = 200 total, 100 earned
        accrual.accrue_investment(inv.id)
        self.profile.refresh_from_db()
        self.assertAlmostEqual(float(self.profile.wallet_balance), 100.0, delta=0.5)
        first = self.profile.wallet_balance
        accrual.accrue_investment(inv.id)       # immediately again: nothing new beyond a few cents
        self.profile.refresh_from_db()
        self.assertAlmostEqual(float(self.profile.wallet_balance), float(first), delta=0.05)
        self.assertEqual(Transaction.objects.filter(user=self.user, txn_type='roi_payout').count(), 1)  # one row per day

    def test_maturity_pays_rest_and_returns_capital(self):
        inv = self._inv(11)
        accrual.accrue_investment(inv.id)
        inv.refresh_from_db(); self.profile.refresh_from_db()
        self.assertEqual(inv.status, 'completed')
        self.assertEqual(self.profile.wallet_balance, Decimal('1200.00'))   # 200 ROI + 1000 capital
        accrual.accrue_investment(inv.id)                                    # no double payout
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.wallet_balance, Decimal('1200.00'))


class TestQuickTrade(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('qt_user', 'qt@example.com', 'Passw0rd!x')
        self.profile = UserProfile.objects.create(user=self.user, wallet_balance=Decimal('500.00'), email_verified=True)
        self.asset, _ = TradingAsset.objects.get_or_create(symbol='BTC', defaults=dict(name='Bitcoin', category='crypto', base_price=Decimal('100000')))
        self.client.login(username='qt_user', password='Passw0rd!x')

    def _place(self, direction='up', stake='100', duration='30'):
        with mock.patch('core.views.quote', return_value=(Decimal('100000.00'), Decimal('0'))):
            self.client.post(reverse('option_place'), {'asset_id': self.asset.id, 'direction': direction, 'stake': stake, 'duration': duration})
        return OptionTrade.objects.order_by('-id').first()

    def _settle(self, opt, price):
        opt.expires_at = timezone.now() - timedelta(seconds=1); opt.save()
        with mock.patch('core.accrual.quote', return_value=(Decimal(price), Decimal('0'))):
            accrual.settle_options()
        opt.refresh_from_db(); self.profile.refresh_from_db()

    def test_win_pays_stake_plus_payout(self):
        o = self._place('up'); self.profile.refresh_from_db()
        self.assertEqual(self.profile.wallet_balance, Decimal('400.00'))
        self._settle(o, '100500.00')
        self.assertEqual(o.status, 'won'); self.assertEqual(self.profile.wallet_balance, Decimal('580.00'))   # 400 + 100 + 80%

    def test_loss_keeps_stake(self):
        o = self._place('up'); self._settle(o, '99000.00')
        self.assertEqual(o.status, 'lost'); self.assertEqual(self.profile.wallet_balance, Decimal('400.00'))

    def test_flat_refunds(self):
        o = self._place('down'); self._settle(o, '100000.00')
        self.assertEqual(o.status, 'draw'); self.assertEqual(self.profile.wallet_balance, Decimal('500.00'))

    def test_cannot_bet_more_than_balance_or_bad_timer(self):
        self._place(stake='900'); self.assertEqual(OptionTrade.objects.count(), 0)
        self._place(duration='7'); self.assertEqual(OptionTrade.objects.count(), 0)

    def test_settled_only_once(self):
        o = self._place('up'); self._settle(o, '100500.00')
        accrual.settle_options(); self.profile.refresh_from_db()
        self.assertEqual(self.profile.wallet_balance, Decimal('580.00'))


@override_settings(EMAIL_HOST='smtp.test.invalid')
class TestEmailCodes(TestCase):
    def _last_code(self):
        import re
        return re.search(r'Code: (\d{6})', mail.outbox[-1].body).group(1)

    def test_register_verify_resend_flow(self):
        r = self.client.post(reverse('register'), {
            'full_name': 'Jane Doe', 'username': 'jane', 'email': 'jane@example.com', 'password': 'Str0ng!Pass', 'password_confirm': 'Str0ng!Pass'})
        self.assertRedirects(r, reverse('verify_email'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)       # gated until verified
        r = self.client.post(reverse('resend_otp'), {'purpose': 'verify'})              # too soon
        self.assertFalse(r.json()['ok']); self.assertGreater(r.json()['wait'], 0)
        self.client.post(reverse('verify_email'), {'code': '000000'})
        self.assertFalse(User.objects.get(username='jane').profile.email_verified)
        self.client.post(reverse('verify_email'), {'code': self._last_code()})
        self.assertTrue(User.objects.get(username='jane').profile.email_verified)
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_resend_after_wait_sends_new_code(self):
        self.client.post(reverse('register'), {'full_name': 'J D', 'username': 'jd', 'email': 'jd@example.com', 'password': 'Str0ng!Pass', 'password_confirm': 'Str0ng!Pass'})
        EmailOTP.objects.update(created_at=timezone.now() - timedelta(minutes=5))
        r = self.client.post(reverse('resend_otp'), {'purpose': 'verify'})
        self.assertTrue(r.json()['ok']); self.assertEqual(len(mail.outbox), 2)

    def test_forgot_and_reset_password(self):
        u = User.objects.create_user('bob', 'bob@example.com', 'Old!Passw0rd'); UserProfile.objects.create(user=u, email_verified=True)
        self.client.post(reverse('forgot_password'), {'identifier': 'bob@example.com'})
        code = self._last_code()
        r = self.client.post(reverse('reset_password'), {'code': '111111', 'new_password': 'Brand!New9pass', 'confirm_password': 'Brand!New9pass'})
        self.assertEqual(r.status_code, 200)
        self.client.post(reverse('reset_password'), {'code': code, 'new_password': 'Brand!New9pass', 'confirm_password': 'Brand!New9pass'})
        self.assertTrue(self.client.login(username='bob', password='Brand!New9pass'))

    def test_unknown_account_gets_same_answer(self):
        r = self.client.post(reverse('forgot_password'), {'identifier': 'nobody@example.com'})
        self.assertRedirects(r, reverse('reset_password')); self.assertEqual(len(mail.outbox), 0)

    def test_sign_in_code_when_enabled(self):
        u = User.objects.create_user('amy', 'amy@example.com', 'Amy!Passw0rd'); UserProfile.objects.create(user=u, email_verified=True, two_factor=True)
        r = self.client.post(reverse('login'), {'identifier': 'amy', 'password': 'Amy!Passw0rd'})
        self.assertRedirects(r, reverse('login_verify'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 302)
        self.client.post(reverse('login_verify'), {'code': self._last_code()})
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)

    def test_code_locks_after_too_many_tries(self):
        u = User.objects.create_user('zed', 'zed@example.com', 'Zed!Passw0rd'); UserProfile.objects.create(user=u)
        otp.send_code(u, 'reset'); good = self._last_code()
        for _ in range(6):
            otp.check_code(u, 'reset', '999999')
        self.assertFalse(otp.check_code(u, 'reset', good))


@override_settings(EMAIL_HOST='smtp.test.invalid')
class TestSettings(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('set_user', 'set@example.com', 'Old!Passw0rd')
        UserProfile.objects.create(user=self.user, email_verified=True)
        self.client.login(username='set_user', password='Old!Passw0rd')

    def test_change_password_needs_current(self):
        self.client.post(reverse('settings_password'), {'current_password': 'wrong', 'new_password': 'Newer!Pass99', 'confirm_password': 'Newer!Pass99'})
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('Old!Passw0rd'))
        self.client.post(reverse('settings_password'), {'current_password': 'Old!Passw0rd', 'new_password': 'Newer!Pass99', 'confirm_password': 'Newer!Pass99'})
        self.user.refresh_from_db(); self.assertTrue(self.user.check_password('Newer!Pass99'))
        self.assertEqual(self.client.get(reverse('dashboard')).status_code, 200)   # still signed in

    def test_profile_save(self):
        self.client.post(reverse('settings_profile'), {'first_name': 'Sam', 'last_name': 'Lee', 'phone': '+1 555', 'country': 'Canada'})
        self.user.refresh_from_db(); self.assertEqual(self.user.first_name, 'Sam'); self.assertEqual(self.user.profile.country, 'Canada')
        self.assertFalse(self.user.profile.email_notifications)

    def test_admin_cannot_double_approve_deposit(self):
        admin = User.objects.create_user('adm', 'adm@example.com', 'Adm!Passw0rd', is_staff=True); UserProfile.objects.create(user=admin)
        dep = DepositRequest.objects.create(user=self.user, method='BANK_WIRE', amount=Decimal('100'))
        self.client.login(username='adm', password='Adm!Passw0rd')
        url = reverse('admin_deposit_action', kwargs={'deposit_id': dep.id, 'action': 'approve'})
        self.client.post(url); self.client.post(url)
        self.assertEqual(UserProfile.objects.get(user=self.user).wallet_balance, Decimal('100.00'))
