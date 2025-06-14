from rest_framework import serializers
from .models import Currency, Category, Balance, Transaction
from decimal import Decimal


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


class CategorySerializer(serializers.ModelSerializer):    
    class Meta:
        model = Category
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class BalanceSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = Balance
        fields = ['id', 'amount', 'currency', 'currency_id', 'updated_at']
        read_only_fields = ['id', 'amount', 'updated_at']  


class TransactionSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_name = serializers.CharField(write_only=True, max_length=100)
    currency = serializers.CharField(write_only=True, required=False, allow_null=True, max_length=50)
    currency_code = serializers.CharField(write_only=True, required=False, allow_null=True, max_length=3)
    currency_info = serializers.StringRelatedField(source='currency', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'amount', 'title', 'category', 'category_name', 'currency', 'currency_info', 'currency_code', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate(self, data):
        currency_from_request = data.get('currency')
        if currency_from_request:
            currency_mapping = {
                'Yen': 'JPY',
                'Dollar': 'USD', 
                'Euro': 'EUR',
                'Pound': 'GBP',
                'Hryvnia': 'UAH',
                'Гривня': 'UAH',
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
        category_name = validated_data.pop('category_name')
        currency_code = validated_data.pop('currency_code', None) 
        user = self.context['request'].user
        category, created = Category.objects.get_or_create(name=category_name, user=user)
        validated_data['category'] = category
        validated_data['user'] = user

        if currency_code:
            try:
                currency = Currency.objects.get(code=currency_code)
                validated_data['currency'] = currency
            except Currency.DoesNotExist:
                uah_currency, created = Currency.objects.get_or_create(code='UAH', defaults={'name': 'Ukrainian Hryvnia'})
                validated_data['currency'] = uah_currency
        else:
            uah_currency, created = Currency.objects.get_or_create(code='UAH', defaults={'name': 'Ukrainian Hryvnia'})
            validated_data['currency'] = uah_currency

        if 'amount' in validated_data:
            validated_data['amount'] = abs(validated_data['amount'])
        
        transaction = super().create(validated_data)
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
        
        return super().update(instance, validated_data)

class TransactionListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'type_display', 'amount', 'title', 'category_name', 'created_at']
        read_only_fields = fields


class BalanceDetailSerializer(serializers.ModelSerializer):
    currency = CurrencySerializer(read_only=True)
    recent_transactions = TransactionListSerializer(source='user.transaction_set', many=True, read_only=True)
    
    class Meta:
        model = Balance
        fields = ['id', 'amount', 'currency', 'updated_at', 'recent_transactions']
        read_only_fields = fields
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['recent_transactions'] = data['recent_transactions'][:5]
        return data