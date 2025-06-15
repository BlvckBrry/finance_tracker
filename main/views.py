from django.db.models import Q
from rest_framework import status
from decimal import Decimal
import pandas as pd
from rest_framework.response import Response
from datetime import datetime, timedelta
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.mixins import (
    ListModelMixin, 
    CreateModelMixin, 
    UpdateModelMixin, 
    DestroyModelMixin,
    RetrieveModelMixin
)
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from .services.currency_api_service import CurrencyAPIService
from .models import Transaction, Balance, Category, Currency
from .serializers import (
    TransactionSerializer, 
    TransactionListSerializer, 
    CategorySerializer,
    BalanceSerializer,
    BalanceDetailSerializer,
    CurrencySerializer, 
    CurrencyConversionSerializer
)
from .financial_analytics import FinancialAnalyticsService

class CurrencyListCreateView(ListModelMixin, CreateModelMixin, GenericAPIView):    
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class CurrencyRetrieveView(RetrieveModelMixin, GenericAPIView):    
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()
    lookup_field = 'code'
    
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class CurrencyConversionView(APIView):    
    def get(self, request):
        serializer = CurrencyConversionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': f"Wrong params: {serializer.errors}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        validated_data = serializer.validated_data
        amount = validated_data['amount']
        from_code = validated_data['from_currency'].upper()
        to_code = validated_data['to_currency'].upper()
        
        try:
            from_currency = Currency.objects.get(code=from_code)
            to_currency = Currency.objects.get(code=to_code)
        except Currency.DoesNotExist:
            return Response({
                'error': "Currency was not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        amount_in_uah = amount * from_currency.rate_to_uah
        converted_amount = amount_in_uah / to_currency.rate_to_uah
        
        return Response({
            'success': True,
            'conversion': {
                'original_amount': str(amount),
                'converted_amount': str(round(converted_amount, 4)),
                'from_currency': from_code,
                'to_currency': to_code,
                'rate': str(round(from_currency.rate_to_uah / to_currency.rate_to_uah, 6))
            }
        })


class TransactionListCreateView(ListModelMixin, CreateModelMixin, GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return TransactionListSerializer
        return TransactionSerializer
    
    def get_queryset(self):
        queryset = Transaction.objects.filter(user=self.request.user)
        category_ids = self.request.query_params.getlist('category') 
        transaction_type = self.request.query_params.get('type')
        min_amount = self.request.query_params.get('min_amount')
        max_amount = self.request.query_params.get('max_amount')
        filters = Q()
        if category_ids:
            try:
                category_ids = [int(cat_id) for cat_id in category_ids if cat_id.isdigit()]
                if category_ids:
                    filters &= Q(category_id__in=category_ids)
            except (ValueError, TypeError):
                pass

        if transaction_type and transaction_type in ['income', 'expense']:
            filters &= Q(type=transaction_type)
        
        if min_amount:
            try:
                min_amount = Decimal(min_amount)
                filters &= Q(amount__gte=min_amount)
            except (ValueError, TypeError, decimal.InvalidOperation):
                pass
        
        if max_amount:
            try:
                max_amount = Decimal(max_amount)
                filters &= Q(amount__lte=max_amount)
            except (ValueError, TypeError, decimal.InvalidOperation):
                pass
        
        if filters:
            queryset = queryset.filter(filters)
        
        return queryset.order_by('-created_at')
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class TransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        return get_object_or_404(Transaction, pk=pk, user=self.request.user)
    
    def get(self, request, pk):
        transaction = self.get_object(pk)
        serializer = TransactionSerializer(transaction, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request, pk):
        transaction = self.get_object(pk)
        old_amount = transaction.amount
        old_type = transaction.type
        serializer = TransactionSerializer(transaction, data=request.data, context={'request': request})
        
        if serializer.is_valid():
            self._revert_balance_change(transaction.user, old_amount, old_type)
            updated_transaction = serializer.save()
            self._apply_balance_change(updated_transaction.user, updated_transaction.amount, updated_transaction.type)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        transaction = self.get_object(pk)
        old_amount = transaction.amount
        old_type = transaction.type
        serializer = TransactionSerializer(transaction, data=request.data, partial=True,context={'request': request})
        
        if serializer.is_valid():
            self._revert_balance_change(transaction.user, old_amount, old_type)
            updated_transaction = serializer.save()
            self._apply_balance_change(updated_transaction.user, updated_transaction.amount, updated_transaction.type)
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        transaction = self.get_object(pk)
        self._revert_balance_change(transaction.user, transaction.amount, transaction.type)
        transaction.delete()
        return Response("Transaction was successfully deleted", status=status.HTTP_204_NO_CONTENT)
    
    def _apply_balance_change(self, user, amount, transaction_type):
        balance, created = Balance.objects.get_or_create(user=user, defaults={'currency_id': 1})

        if transaction_type == 'income':
            balance.amount += amount

        elif transaction_type == 'expense':
            balance.amount -= amount
        
        balance.save()
    
    def _revert_balance_change(self, user, amount, transaction_type):
        try:
            balance = Balance.objects.get(user=user)

            if transaction_type == 'income':
                balance.amount -= amount

            elif transaction_type == 'expense':
                balance.amount += amount
            
            balance.save()
        except Balance.DoesNotExist:
            pass


class CategoryListCreateView(ListModelMixin, CreateModelMixin, GenericAPIView):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk):
        return get_object_or_404(Category, pk=pk, user=self.request.user)
    
    def get(self, request, pk):
        category = self.get_object(pk)
        serializer = CategorySerializer(category, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request, pk):
        category = self.get_object(pk)
        serializer = CategorySerializer(category, data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        category = self.get_object(pk)
        serializer = CategorySerializer(category, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        category = self.get_object(pk)
        
        if Transaction.objects.filter(category=category).exists():
            return Response({'error': 'Unable to delete a category used in transactions'}, status=status.HTTP_400_BAD_REQUEST)
        
        category.delete()
        return Response("Category was successfully deleted", status=status.HTTP_204_NO_CONTENT)


class BalanceView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            balance = Balance.objects.get(user=request.user)
            serializer = BalanceDetailSerializer(balance, context={'request': request})
            return Response(serializer.data)
        except Balance.DoesNotExist:
            default_currency = Currency.objects.first()
            if not default_currency:
                return Response({'error': 'No currency found in the system'}, status=status.HTTP_400_BAD_REQUEST)

            balance = Balance.objects.create(user=request.user, currency=default_currency, amount=0.00)
            serializer = BalanceDetailSerializer(balance, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class BalanceResetView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        Transaction.objects.filter(user=request.user).delete()
        Category.objects.filter(user=request.user).delete()
        balance, created = Balance.objects.get_or_create(user=request.user,
            defaults={
                'currency': Currency.objects.first(),
                'amount': 0.00
            }
        )
        balance.amount = 0.00
        balance.save()
        serializer = BalanceDetailSerializer(balance, context={'request': request})
        
        return Response({
            'message': 'Balance reset to zero, all transactions and categories were deleted',
            'balance': serializer.data
        })

    
class BalanceManualAdjustView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        amount = request.data.get('amount')
        reason = request.data.get('reason', 'Manual adjustment')
        
        if not amount:
            return Response({'error': 'You must specify the amount.'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return Response({'error': 'Incorrect amount'}, status=status.HTTP_400_BAD_REQUEST)

        balance, created = Balance.objects.get_or_create(user=request.user,
            defaults={
                'currency': Currency.objects.first(),
                'amount': 0.00
            }
        )
        
        adjustment_category, created = Category.objects.get_or_create(name='Balance adjustment', user=request.user)        
        transaction_type = 'income' if amount > 0 else 'expense'
        Transaction.objects.create(user=request.user, type=transaction_type, amount=abs(amount), title=reason, category=adjustment_category)
        balance.refresh_from_db()
        serializer = BalanceDetailSerializer(balance, context={'request': request})
        return Response({
            'message': f'Balance adjusted to {amount}',
            'balance': serializer.data
        })

class FinancialReportsView(APIView):
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        report_type = request.GET.get('report_type', 'balance')
        
        if start_date:
            start_date = pd.to_datetime(start_date).date()

        if end_date:
            end_date = pd.to_datetime(end_date).date()
        
        analytics = FinancialAnalyticsService(request.user, start_date, end_date)
        
        if report_type == 'balance':
            data = analytics.calculate_general_balance()

        elif report_type == 'categories':
            data = analytics.analyze_by_categories()

        else:
            return Response({'error': 'Invalid report type'}, status=400)
        
        return Response(data)

class ExportExcelView(APIView):
    def get(self, request):
        transaction_type = request.GET.get('type')  
        category_name = request.GET.get('category')  
        currency_code = request.GET.get('currency')  
        analytics = FinancialAnalyticsService(start_date=request.GET.get('start_date'), end_date=request.GET.get('end_date'), user=request.user)
        excel_file = analytics.export_to_excel(transaction_type=transaction_type, category_name=category_name, currency_code=currency_code)
        if excel_file is None:
            return HttpResponse("No data for export", status=404)

        filename_parts = ['transactions']
        if transaction_type:
            filename_parts.append(transaction_type)

        if category_name:
            filename_parts.append(category_name.replace(' ', '_'))

        if currency_code:
            filename_parts.append(currency_code)
        
        filename = '_'.join(filename_parts) + '.xlsx'
        response = HttpResponse(excel_file.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class ImportExcelView(APIView):
    def post(self, request):
        if 'file' not in request.FILES:
            return Response({'error': 'No file provided'}, status=400)
        
        excel_file = request.FILES['file']
        
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            return Response({'error': 'Invalid file format'}, status=400)
        
        analytics = FinancialAnalyticsService(request.user)
        result = analytics.import_from_excel(excel_file)
        
        if result['success']:
            return Response(result)
        else:
            return Response(result, status=400)