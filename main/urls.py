from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()

router.register('transaction', views.TransactionListCreateViewSet, basename='transaction-list')
router.register('transaction_detail', views.TransactionDetailViewSet, basename='transaction-detail')

router.register('category', views.CategoryListCreateViewSet, basename='category-list')
router.register('category_detail', views.CategoryDetailViewSet, basename='category-detail')

router.register('currency', views.CurrencyListCreateViewSet, basename='currency-list')
router.register('currency_detail', views.CurrencyRetrieveViewSet, basename='currency-detail')
router.register('currency_conversion', views.CurrencyConversionViewSet, basename='currency-conversion')

router.register('balance', views.BalanceViewSet, basename='balance')
router.register('balance_reset', views.BalanceResetViewSet, basename='balance-reset')
router.register('balance_manual', views.BalanceManualAdjustViewSet, basename='balance-manual')

router.register('spending_limit', views.SpendingLimitViewSet, basename='spending-limit')
router.register('spending_summary', views.SpendingSummaryViewSet, basename='spending-summary')
router.register('financial_reports', views.FinancialReportsViewSet, basename='financial-reports')

urlpatterns = [
    path('', include(router.urls)),    
    path('excel_export/', views.ExportExcelView.as_view(), name='excel-export'),
    path('excel_import/', views.ImportExcelView.as_view(), name='excel-import'),
]