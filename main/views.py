from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import GenericAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView, RetrieveUpdateAPIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import ListModelMixin, CreateModelMixin, RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin
from rest_framework.views import APIView
from django.http import HttpResponse
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action
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


class CurrencyListCreateViewSet(ListModelMixin, CreateModelMixin, GenericViewSet):   
    permission_classes = [IsAuthenticated] 
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()


class CurrencyRetrieveViewSet(RetrieveModelMixin, GenericViewSet): 
    permission_classes = [IsAuthenticated]   
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all()
    lookup_field = 'code'
    lookup_value_regex = '[A-Z]{3}'


class CurrencyConversionViewSet(CreateModelMixin, GenericViewSet):   
    permission_classes = [IsAuthenticated]
    serializer_class = CurrencyConversionSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'error': f"Wrong params: {serializer.errors}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.to_representation(serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)


class TransactionListCreateViewSet(ListModelMixin, CreateModelMixin, GenericViewSet):
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


class TransactionDetailViewSet(RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TransactionSerializer
    
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)
    
    def get_serializer_context(self):
        return {'request': self.request}
    
    def destroy(self, request, *args, **kwargs):
        transaction = self.get_object()
        serializer = TransactionSerializer(transaction, context={'request': request})
        message = serializer.delete_transaction(transaction)
        return Response(message, status=status.HTTP_204_NO_CONTENT)


class CategoryListCreateViewSet(ListModelMixin, CreateModelMixin, GenericViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)


class CategoryDetailViewSet(RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer
    
    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)
    
    def get_serializer_context(self):
        return {'request': self.request}
    
    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = CategorySerializer(category, context={'request': request})
        
        try:
            serializer.validate_delete(category)
            category.delete()
            return Response("Category was successfully deleted", status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class BalanceViewSet(RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BalanceDetailSerializer
    
    def get_balance_object(self):
        serializer = BalanceSerializer(context={'request': self.request})
        balance, created = serializer.get_or_create_balance(self.request.user)
        if created:
            balance._created = True
        return balance
    
    def list(self, request, *args, **kwargs):
        instance = self.get_balance_object()
        serializer = self.get_serializer(instance)
        return Response(
            serializer.data, 
            status=status.HTTP_201_CREATED if hasattr(instance, '_created') else status.HTTP_200_OK
        )


class BalanceResetViewSet(CreateModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BalanceResetSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer()
        result = serializer.reset_balance(request.user)
        return Response(result)


class BalanceManualAdjustViewSet(CreateModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = BalanceManualAdjustSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        result = serializer.adjust_balance(request.user)
        return Response(result)


class SpendingLimitViewSet(RetrieveModelMixin, UpdateModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSpendingLimitSerializer
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_context(self):
        return {'request': self.request}

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def current_user_limit(self, request):
        if request.method == 'GET':
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)

        else:  
            partial = request.method == 'PATCH'
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)


class SpendingSummaryViewSet(RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = SpendingSummarySerializer
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer()
        data = serializer.get_spending_summary(request.user)
        return Response(data)


class FinancialReportsViewSet(RetrieveModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FinancialReportsSerializer
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        data = {
            'start_date': request.GET.get('start_date'),
            'end_date': request.GET.get('end_date'),
            'report_type': request.GET.get('report_type', 'balance'),
        }
        
        serializer = self.get_serializer(data=data)
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
        data = {}
        
        if request.GET.get('type'):
            data['type'] = request.GET.get('type')
        if request.GET.get('category'):
            data['category'] = request.GET.get('category')
        if request.GET.get('currency'):
            data['currency'] = request.GET.get('currency')
        if request.GET.get('start_date'):
            data['start_date'] = request.GET.get('start_date')
        if request.GET.get('end_date'):
            data['end_date'] = request.GET.get('end_date')
        
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
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        serializer = ImportExcelSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            result = serializer.import_from_excel(request.user)
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)