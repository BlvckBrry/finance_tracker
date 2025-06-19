from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, RetrieveModelMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Currency, Transaction, Category, Balance
from .serializers import (
    CurrencySerializer, CurrencyConversionSerializer, CategorySerializer,
    TransactionSerializer, TransactionListSerializer, BalanceSerializer,
    BalanceDetailSerializer, BalanceResetSerializer, BalanceManualAdjustSerializer,
    UserSpendingLimitSerializer, SpendingSummarySerializer,
    FinancialReportsSerializer, ExportExcelSerializer, ImportExcelSerializer,
    TransactionFilterSerializer
)


class CurrencyListCreateView(ListModelMixin, CreateModelMixin, GenericAPIView):   
    permission_classes = [IsAuthenticated] 
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()
    
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)


class CurrencyRetrieveView(RetrieveModelMixin, GenericAPIView): 
    permission_classes = [IsAuthenticated]   
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()
    lookup_field = 'code'
    
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class CurrencyConversionView(APIView):   
    permission_classes = [IsAuthenticated]    
    
    def get(self, request):
        serializer = CurrencyConversionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': f"Wrong params: {serializer.errors}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.to_representation(serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class TransactionListCreateView(ListModelMixin, CreateModelMixin, GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return TransactionListSerializer
        return TransactionSerializer
    
    def get_queryset(self):
        queryset = Transaction.objects.filter(user=self.request.user)
        
        filter_data = {
            'category': self.request.query_params.getlist('category'),
            'type': self.request.query_params.get('type'),
            'min_amount': self.request.query_params.get('min_amount'),
            'max_amount': self.request.query_params.get('max_amount'),
        }
        
        filter_serializer = TransactionFilterSerializer(data=filter_data)
        if filter_serializer.is_valid():
            queryset = filter_serializer.filter_queryset(queryset)
        
        return queryset
    
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
        serializer = TransactionSerializer(transaction, data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        transaction = self.get_object(pk)
        serializer = TransactionSerializer(transaction, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        transaction = self.get_object(pk)
        serializer = TransactionSerializer(transaction, context={'request': request})
        message = serializer.delete_transaction(transaction)
        return Response(message, status=status.HTTP_204_NO_CONTENT)


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
        serializer = CategorySerializer(category, context={'request': request})
        
        try:
            serializer.validate_delete(category)
            category.delete()
            return Response("Category was successfully deleted", status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BalanceView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = BalanceSerializer(context={'request': request})
        balance, created = serializer.get_or_create_balance(request.user)
        
        balance_serializer = BalanceDetailSerializer(balance, context={'request': request})
        
        if created:
            return Response(balance_serializer.data, status=status.HTTP_201_CREATED)
        return Response(balance_serializer.data)


class BalanceResetView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = BalanceResetSerializer()
        result = serializer.reset_balance(request.user)
        return Response(result)


class BalanceManualAdjustView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = BalanceManualAdjustSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.adjust_balance(request.user)
        return Response(result)


class SpendingLimitView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def get(self, request):
        user = self.get_object()
        serializer = UserSpendingLimitSerializer(user, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request):
        user = self.get_object()
        serializer = UserSpendingLimitSerializer(user, data=request.data, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        user = self.get_object()
        serializer = UserSpendingLimitSerializer(user, data=request.data, partial=True, context={'request': request})
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SpendingSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = SpendingSummarySerializer()
        data = serializer.get_spending_summary(request.user)
        return Response(data)


class FinancialReportsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        data = {
            'start_date': request.GET.get('start_date'),
            'end_date': request.GET.get('end_date'),
            'report_type': request.GET.get('report_type', 'balance'),
        }
        
        serializer = FinancialReportsSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            report_data = serializer.generate_report(request.user)
            return Response(report_data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ExportExcelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        data = {
            'type': request.GET.get('type'),
            'category': request.GET.get('category'),
            'currency': request.GET.get('currency'),
            'start_date': request.GET.get('start_date'),
            'end_date': request.GET.get('end_date'),
        }
        
        serializer = ExportExcelSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = serializer.export_to_excel(request.user)
            excel_file = result['file']
            filename = result['filename']
            
            response = HttpResponse(
                excel_file.getvalue(), 
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ImportExcelView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ImportExcelSerializer(data=request.FILES)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = serializer.import_from_excel(request.user)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)