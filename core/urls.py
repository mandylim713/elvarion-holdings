from django.urls import path
from . import views

urlpatterns = [
    # Public views
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Client Portal
    path('dashboard/', views.dashboard, name='dashboard'),
    path('invest/', views.create_investment, name='create_investment'),
    path('loans/apply/', views.apply_loan, name='apply_loan'),
    path('deposit/', views.submit_deposit, name='submit_deposit'),
    path('withdraw/', views.submit_withdrawal, name='submit_withdrawal'),
    path('kyc/submit/', views.submit_kyc, name='submit_kyc'),

    # Real-Time APIs
    path('api/realtime-roi/', views.api_realtime_roi, name='api_realtime_roi'),
    path('api/loan-calculator/', views.api_loan_calculator, name='api_loan_calculator'),

    # Admin Management Portal
    path('management/', views.admin_management, name='admin_management'),
    path('management/loan/<int:loan_id>/<str:action>/', views.admin_loan_action, name='admin_loan_action'),
    path('management/deposit/<int:deposit_id>/<str:action>/', views.admin_deposit_action, name='admin_deposit_action'),
    path('management/kyc/<int:submission_id>/<str:action>/', views.admin_kyc_action, name='admin_kyc_action'),
    path('management/plan/save/', views.admin_save_plan, name='admin_save_plan'),
    path('management/tier/save/', views.admin_save_tier, name='admin_save_tier'),
]
