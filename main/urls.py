from django.urls import path, include
from . import views

urlpatterns = [
    path('transaction/', views.TransactionListCreateView.as_view(), name='transaction_list_or_create'),
    path('transaction/<int:pk>/', views.TransactionDetailView.as_view(), name='transaction_detail_or_delete'),
    
    path('category/', views.CategoryListCreateView.as_view(), name='category_list_or_create'),
    path('category/<int:pk>/', views.CategoryDetailView.as_view(), name='category_detail_or_delete'),

    path('balance/', views.BalanceView.as_view(), name='balance'),
    path('balance_reset/', views.BalanceResetView.as_view(), name='balance_reset'),
    path('balance_manual/', views.BalanceManualAdjustView.as_view(), name='balance_manual'),

]