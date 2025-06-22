from django.urls import path, include
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='registration'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('users/', views.UserListView.as_view(), name='userlist'),
    path('profile/', views.UserDetailView.as_view(), name='user_detail'),
    path('delete/', views.UserDeleteView.as_view(), name='user_delete'),

    path('email_verification_send/', views.EmailVerificationSendView.as_view(), name='email_verification_send'),
    path('email_verification_confirm/', views.EmailVerificationConfirmView.as_view(), name='email_verification_confirm'),

    path('password_reset_request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password_reset_confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
]