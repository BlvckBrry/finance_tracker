from django.db.models import Q
from rest_framework import status
from decimal import Decimal
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.mixins import (
    ListModelMixin, 
    CreateModelMixin, 
    UpdateModelMixin, 
    DestroyModelMixin
)
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Transaction, Balance, Category, Currency
from .serializers import (
    TransactionSerializer, 
    TransactionListSerializer, 
    CategorySerializer,
    BalanceSerializer,
    BalanceDetailSerializer
)


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