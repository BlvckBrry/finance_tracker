from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from decimal import Decimal
import decimal
import pandas as pd
from .models import Currency, Category, Balance, Transaction
from .utils import calculate_monthly_spending
from .financial_analytics import FinancialAnalyticsService
from .constants import UAH_CURRENCY_NAME

User = get_user_model()

class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'rate_to_uah', 'updated_at']
        read_only_fields = ['updated_at']


class CurrencyConversionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=4)
    from_currency = serializers.CharField(max_length=3)
    to_currency = serializers.CharField(max_length=3)
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("The amount must be greater than 0.")
        return value

    def validate(self, attrs):
        from_code = attrs['from_currency'].upper()
        to_code = attrs["to_currency"].upper()

        try:
            Currency.objects.get(code=from_code)
            Currency.objects.get(code=to_code)
        except Currency.DoesNotExist:
            raise serializers.ValidationError("Currency was not found")
        
        return attrs

    def to_representation(self, instance):
        amount = instance["amount"]
        from_code = instance["from_currency"].upper()
        to_code = instance["to_currency"].upper()

        from_currency = Currency.objects.get(code=from_code)
        to_currency = Currency.objects.get(code=to_code)
        
        amount_in_uah = amount * from_currency.rate_to_uah
        converted_amount = amount_in_uah / to_currency.rate_to_uah
        
        return {
            'original_amount': amount,
            'from_currency': from_code,
            'to_currency': to_code,
            'converted_amount': converted_amount
        }


class CategorySerializer(serializers.ModelSerializer):    
    class Meta:
        model = Category
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)
    
    def validate_delete(self, category):
        if Transaction.objects.filter(category=category).exists():
            raise serializers.ValidationError('Unable to delete a category used in transactions')
        return True


class BalanceSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Balance
        fields = ['id', 'amount', 'currency', 'currency_id', 'updated_at']
        read_only_fields = ['id', 'amount', 'updated_at']

    def get_or_create_balance(self, user):
        try:
            balance = Balance.objects.get(user=user)
            return balance, False
        except Balance.DoesNotExist:
            default_currency = Currency.objects.get(code="UAH")
            if not default_currency:
                raise serializers.ValidationError({'error': 'No currency found in the system'})
            
            balance = Balance.objects.create(user=user, currency=default_currency, amount=0.00)
            return balance, True


class BalanceResetSerializer(serializers.Serializer):
    def reset_balance(self, user):
        Transaction.objects.filter(user=user).delete()
        Category.objects.filter(user=user).delete()
        balance, created = Balance.objects.get_or_create(
            user=user,
            defaults={
                'currency': Currency.objects.get(code='UAH'),
                'amount': 0.00
            }
        )
        balance.amount = 0.00
        balance.save()
        
        return {
            'message': 'Balance reset to zero, all transactions and categories were deleted',
            'balance': BalanceDetailSerializer(balance).data
        }


class BalanceManualAdjustSerializer(serializers.Serializer):
    amount = serializers.FloatField()
    reason = serializers.CharField(max_length=255, default='Manual adjustment')
    
    def validate_amount(self, value):
        if value == 0:
            raise serializers.ValidationError('Amount cannot be zero.')
        return value
    
    def adjust_balance(self, user):
        amount = self.validated_data['amount']
        reason = self.validated_data['reason']
        
        balance, created = Balance.objects.get_or_create(
            user=user,
            defaults={
                'currency': Currency.objects.first(),
                'amount': 0.00
            }
        )
        
        adjustment_category, created = Category.objects.get_or_create(
            name='Balance adjustment', 
            user=user
        )
        
        transaction_type = 'income' if amount > 0 else 'expense'
        Transaction.objects.create(
            user=user, 
            type=transaction_type, 
            amount=abs(amount), 
            title=reason, 
            category=adjustment_category
        )
        
        balance.refresh_from_db()
        
        return {
            'message': f'Balance adjusted to {amount}',
            'balance': BalanceDetailSerializer(balance).data
        }


class TransactionFilterSerializer(serializers.Serializer):
    category = serializers.ListField(child=serializers.CharField(), required=False)
    type = serializers.ChoiceField(choices=['income', 'expense'], required=False)
    min_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    max_amount = serializers.DecimalField(max_digits=15, decimal_places=2, required=False)
    
    def filter_queryset(self, queryset):
        filters = Q()
        
        category_ids = self.validated_data.get('category', [])
        if category_ids:
            try:
                category_ids = [int(cat_id) for cat_id in category_ids if cat_id.isdigit()]
                if category_ids:
                    filters &= Q(category_id__in=category_ids)
            except (ValueError, TypeError):
                pass

        transaction_type = self.validated_data.get('type')
        if transaction_type:
            filters &= Q(type=transaction_type)
        
        min_amount = self.validated_data.get('min_amount')
        if min_amount:
            filters &= Q(amount__gte=min_amount)
        
        max_amount = self.validated_data.get('max_amount')
        if max_amount:
            filters &= Q(amount__lte=max_amount)
        
        if filters:
            queryset = queryset.filter(filters)
        
        return queryset.order_by('-created_at')


class TransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_name = serializers.CharField(write_only=True, max_length=100)
    currency = serializers.CharField(write_only=True, required=False, allow_null=True, max_length=50)
    currency_code = serializers.CharField(write_only=True, required=False, allow_null=True, max_length=3)
    currency_info = serializers.StringRelatedField(source='currency', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'amount', 'title', 'category', 'category_name', 'currency', 'currency_info', 'currency_code', 'created_at']
        read_only_fields = ['id', 'created_at', 'currency_info']  
    
    def validate(self, data):
        currency_from_request = data.get('currency')
        if currency_from_request:
            currency_mapping = {
                'Yen': 'JPY',
                'Dollar': 'USD', 
                'Euro': 'EUR',
                'Pound': 'GBP',
                'Hryvnia': 'UAH',
                'UAH': 'UAH',
                'USD': 'USD',
                'EUR': 'EUR',
                'GBP': 'GBP',
                'JPY': 'JPY'
            }
            currency_code = currency_mapping.get(currency_from_request, currency_from_request.upper())
            data['currency_code'] = currency_code

        data.pop('currency', None)        
        currency_code = data.get('currency_code')
        if currency_code:
            try:
                Currency.objects.get(code=currency_code.upper())
                data['currency_code'] = currency_code.upper()
            except Currency.DoesNotExist:
                raise serializers.ValidationError(f"Currency with code '{currency_code}' does not exist.")
        
        if data.get('type') == 'expense':
            balance = Balance.objects.get_or_create(user=self.context['request'].user, defaults={'currency_id': 1})[0]            
            currency = None
            if currency_code:
                currency = Currency.objects.get(code=currency_code)
            
            amount = Decimal(data['amount'])
            converted_amount = self._convert_amount_to_uah(amount, currency)
            
            if balance.amount - converted_amount < 0:
                raise serializers.ValidationError({
                    'amount': 'There are not enough funds on the balance sheet. '
                             f'Available: {balance.amount} UAH, trying to spend: {converted_amount} UAH'
                })
        
        return data
    
    def _convert_amount_to_uah(self, amount, currency):
        if not currency or currency.code == 'UAH':
            return amount
        
        try:
            exchange_rate = currency.rate_to_uah
            return amount * Decimal(str(exchange_rate))
        except:
            return amount
    
    def create(self, validated_data):
        category_name = validated_data.pop('category_name', None)
        currency_code = validated_data.pop('currency_code', None)        
        validated_data.pop('currency', None)  
        user = self.context['request'].user
        
        if category_name:
            category, created = Category.objects.get_or_create(name=category_name, user=user)
            validated_data['category'] = category
        
        validated_data['user'] = user

        if currency_code:
            try:
                currency = Currency.objects.get(code=currency_code)
                validated_data['currency'] = currency
            except Currency.DoesNotExist:
                uah_currency, created = Currency.objects.get_or_create(
                    code='UAH', 
                    defaults={'name': UAH_CURRENCY_NAME}
                )
                validated_data['currency'] = uah_currency
        else:
            uah_currency, created = Currency.objects.get_or_create(
                code='UAH', 
                defaults={'name': UAH_CURRENCY_NAME}
            )
            validated_data['currency'] = uah_currency

        if 'amount' in validated_data:
            validated_data['amount'] = abs(validated_data['amount'])
        
        model_fields = [f.name for f in Transaction._meta.fields]
        cleaned_data = {k: v for k, v in validated_data.items() if k in model_fields}
        
        transaction = Transaction.objects.create(**cleaned_data)
        return transaction
    
    def update(self, instance, validated_data):
        if 'category_name' in validated_data:
            category_name = validated_data.pop('category_name')
            user = self.context['request'].user
            category, created = Category.objects.get_or_create(name=category_name, user=user)
            validated_data['category'] = category
        
        if 'currency_code' in validated_data:
            currency_code = validated_data.pop('currency_code')
            if currency_code:
                currency = Currency.objects.get(code=currency_code)
                validated_data['currency'] = currency
        
        if 'amount' in validated_data:
            validated_data['amount'] = abs(validated_data['amount'])
        
        updated_instance = super().update(instance, validated_data)
        return updated_instance
    
    def delete_transaction(self, transaction):
        transaction._revert_from_balance()
        transaction.delete()
        return "Transaction was successfully deleted"


class TransactionListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'type_display', 'amount', 'title', 'category_name', 'created_at']
        read_only_fields = fields


class BalanceDetailSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    
    class Meta:
        model = Balance
        fields = ['id', 'amount', 'currency', 'updated_at']
        read_only_fields = fields


class UserSpendingLimitSerializer(serializers.ModelSerializer):
    current_monthly_spending = serializers.SerializerMethodField()
    remaining_budget = serializers.SerializerMethodField()
    warning_threshold_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['spending_limit', 'warning_threshold', 'last_warning_sent', 
                 'current_monthly_spending', 'remaining_budget', 'warning_threshold_amount']
        read_only_fields = ['last_warning_sent', 'current_monthly_spending', 
                           'remaining_budget', 'warning_threshold_amount']
    
    def get_current_monthly_spending(self, obj):
        return calculate_monthly_spending(obj)
    
    def get_remaining_budget(self, obj):
        if not obj.spending_limit:
            return None
            
        current_spending = calculate_monthly_spending(obj)
        return max(Decimal('0.00'), obj.spending_limit - current_spending)
    
    def get_warning_threshold_amount(self, obj):
        if not obj.spending_limit:
            return None

        return obj.spending_limit * (obj.warning_threshold / Decimal('100'))
    
    def validate_warning_threshold(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Warning threshold must be between 0 and 100 percent.")

        return value
    
    def validate_spending_limit(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Spending limit must be greater than 0.")

        return value


class SpendingSummarySerializer(serializers.Serializer):
    def get_spending_summary(self, user):
        current_spending = calculate_monthly_spending(user)
        
        data = {
            'current_monthly_spending': current_spending,
            'spending_limit': user.spending_limit,
            'warning_threshold': user.warning_threshold,
            'last_warning_sent': user.last_warning_sent,
        }
        
        if user.spending_limit:
            data['remaining_budget'] = max(0, user.spending_limit - current_spending)
            data['warning_threshold_amount'] = user.spending_limit * (user.warning_threshold / 100)
            data['percentage_used'] = (current_spending / user.spending_limit * 100) if user.spending_limit > 0 else 0
            data['is_over_limit'] = current_spending > user.spending_limit
            data['is_near_limit'] = current_spending >= data['warning_threshold_amount']
        
        return data


class FinancialReportsSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    report_type = serializers.ChoiceField(choices=['balance', 'categories'], default='balance')
    
    def generate_report(self, user):
        start_date = self.validated_data.get('start_date')
        end_date = self.validated_data.get('end_date')
        report_type = self.validated_data.get('report_type', 'balance')
        
        if start_date:
            start_date = pd.to_datetime(start_date).date()

        if end_date:
            end_date = pd.to_datetime(end_date).date()
        
        analytics = FinancialAnalyticsService(user, start_date, end_date)
        
        if report_type == 'balance':
            data = analytics.calculate_general_balance()
        elif report_type == 'categories':
            data = analytics.analyze_by_categories()
        else:
            raise serializers.ValidationError({'error': 'Invalid report type'})
        
        return data


class ExportExcelSerializer(serializers.Serializer):
    type = serializers.CharField(required=False)
    category = serializers.CharField(required=False)
    currency = serializers.CharField(required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    
    def export_to_excel(self, user):
        transaction_type = self.validated_data.get('type')
        category_name = self.validated_data.get('category')
        currency_code = self.validated_data.get('currency')
        start_date = self.validated_data.get('start_date')
        end_date = self.validated_data.get('end_date')
        
        analytics = FinancialAnalyticsService(
            start_date=start_date, 
            end_date=end_date, 
            user=user
        )
        
        excel_file = analytics.export_to_excel(
            transaction_type=transaction_type, 
            category_name=category_name, 
            currency_code=currency_code
        )
        
        if excel_file is None:
            raise serializers.ValidationError("No data for export")

        filename_parts = ['transactions']
        if transaction_type:
            filename_parts.append(transaction_type)
        if category_name:
            filename_parts.append(category_name.replace(' ', '_'))
        if currency_code:
            filename_parts.append(currency_code)
        
        filename = '_'.join(filename_parts) + '.xlsx'
        
        return {
            'file': excel_file,
            'filename': filename
        }


class ImportExcelSerializer(serializers.Serializer):
    file = serializers.FileField(required=False)
    
    def validate(self, data):
        file_obj = None
        
        if 'file' in data and data['file']:
            file_obj = data['file']
        else:
            request = self.context.get('request')
            if request and hasattr(request, 'FILES') and request.FILES:
                file_obj = list(request.FILES.values())[0]
        
        if not file_obj:
            raise serializers.ValidationError({'file': 'No file provided'})
            
        if not file_obj.name.endswith(('.xlsx', '.xls')):
            raise serializers.ValidationError({'file': 'Invalid file format'})
            
        data['file'] = file_obj
        return data
    
    def import_from_excel(self, user):
        excel_file = self.validated_data['file']
        
        analytics = FinancialAnalyticsService(user)
        result = analytics.import_from_excel(excel_file)
        
        if not result['success']:
            raise serializers.ValidationError(result)
        
        return result