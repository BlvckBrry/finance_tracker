from django.urls import path, include
from . import views

urlpatterns = [
    path('transaction/', views.TransactionListCreateView.as_view(), name='transaction'),
    path('transaction/<int:pk>/', views.TransactionDetailView.as_view(), name='transaction_pk'),
    
    path('category/', views.CategoryListCreateView.as_view(), name='category'),
    path('category/<int:pk>/', views.CategoryDetailView.as_view(), name='category_pk'),

    path('balance/', views.BalanceView.as_view(), name='balance'),
    path('balance_reset/', views.BalanceResetView.as_view(), name='balance_reset'),
    path('balance_manual/', views.BalanceManualAdjustView.as_view(), name='balance_manual'),

    path('currency/', views.CurrencyListCreateView.as_view(), name='currency'),
    path('currency_conversion/', views.CurrencyConversionView.as_view(), name='currency_conversion'),
    path('currency/<str:code>/', views.CurrencyRetrieveView.as_view(), name='currency_pk'),

    path('excel_reports/', views.FinancialReportsView.as_view(), name='excel_reports'),
    path('excel_export/', views.ExportExcelView.as_view(), name='excel_export'),
    path('excel_import/', views.ImportExcelView.as_view(), name='excel_import'),
]