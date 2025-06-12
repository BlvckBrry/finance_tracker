from django.urls import path, include
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='registration'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('users/', views.UserListView.as_view(), name='userlist'),
    path('profile/', views.UserDetailView.as_view(), name='user_detail'),
]