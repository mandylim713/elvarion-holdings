from django.urls import path
from . import views

urlpatterns = [
    # Public views
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('privacy/', views.privacy, name='privacy'),
    path('terms/', views.terms, name='terms'),
    path('robots.txt', views.robots_txt),
    path('login/', views.login_view, name='login'),
    path('login/verify/', views.login_verify, name='login_verify'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('auth/resend-otp/', views.resend_otp, name='resend_otp'),
    path('settings/profile/', views.settings_profile, name='settings_profile'),
    path('settings/password/', views.settings_password, name='settings_password'),
    path('settings/security/', views.settings_security, name='settings_security'),
    path('logout/', views.logout_view, name='logout'),

    # Client Portal
    path('dashboard/', views.dashboard, name='dashboard'),
    path('invest/', views.create_investment, name='create_investment'),
    path('loans/apply/', views.apply_loan, name='apply_loan'),
    path('deposit/', views.submit_deposit, name='submit_deposit'),
    path('withdraw/', views.submit_withdrawal, name='submit_withdrawal'),
    path('trade/', views.trade_order, name='trade_order'),
    path('trade/quick/', views.option_place, name='option_place'),
    path('api/options/', views.api_options, name='api_options'),
    path('cron/tick/', views.cron_tick, name='cron_tick'),
    path('api/market/', views.api_market, name='api_market'),
    path('kyc/submit/', views.submit_kyc, name='submit_kyc'),

    # Real-Time APIs
    path('api/realtime-roi/', views.api_realtime_roi, name='api_realtime_roi'),
    path('api/loan-calculator/', views.api_loan_calculator, name='api_loan_calculator'),

    # Admin Management Portal
    path('management/login/', views.admin_login, name='admin_login'),
    path('management/logout/', views.admin_logout, name='admin_logout'),
    path('management/', views.admin_management, name='admin_management'),
    path('management/loan/<int:loan_id>/<str:action>/', views.admin_loan_action, name='admin_loan_action'),
    path('management/deposit/<int:deposit_id>/<str:action>/', views.admin_deposit_action, name='admin_deposit_action'),
    path('management/kyc/<int:submission_id>/<str:action>/', views.admin_kyc_action, name='admin_kyc_action'),
    path('management/withdrawal/<int:withdrawal_id>/<str:action>/', views.admin_withdrawal_action, name='admin_withdrawal_action'),
    path('management/user/<int:user_id>/<str:action>/', views.admin_user_action, name='admin_user_action'),
    path('management/plan/<int:plan_id>/toggle/', views.admin_toggle_plan, name='admin_toggle_plan'),
    path('management/investment/<int:investment_id>/<str:action>/', views.admin_investment_action, name='admin_investment_action'),
    path('management/settings/save/', views.admin_save_settings, name='admin_save_settings'),
    path('management/asset/save/', views.admin_save_asset, name='admin_save_asset'),
    path('management/plan/save/', views.admin_save_plan, name='admin_save_plan'),
    path('management/tier/save/', views.admin_save_tier, name='admin_save_tier'),
]
