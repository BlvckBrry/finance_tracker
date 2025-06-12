from rest_framework import serializers
from .models import Currency, Category, Balance, Transaction
from decimal import Decimal


class CurrencySerializer(serializers.ModelSerializer):    
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'rate_to_uah', 'updated_at']
        read_only_fields = ['id', 'updated_at']


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
    
    class Meta:
        model = Transaction
        fields = ['id', 'type', 'amount', 'title', 'category', 'category_name', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("The amount must be greater than 0.")
        return abs(value)  
    
    def validate_category_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Category name cannot be empty.")
        return value.strip()
    
    def validate(self, data):
        if data.get('type') == 'expense':
            balance = Balance.objects.get_or_create(user=self.context['request'].user, defaults={'currency_id': 1})[0]
            
            if balance.amount - Decimal(data['amount']) < 0:
                raise serializers.ValidationError({
                    'amount': 'There are not enough funds on the balance sheet. '
                             f'Available: {balance.amount}, trying to spend: {data["amount"]}'
                })
        
        return data
    
    def create(self, validated_data):
        category_name = validated_data.pop('category_name')
        user = self.context['request'].user
        category, created = Category.objects.get_or_create(name=category_name, user=user)
        validated_data['category'] = category
        validated_data['user'] = user
    
        if 'amount' in validated_data:
            validated_data['amount'] = abs(validated_data['amount'])
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        if 'category_name' in validated_data:
            category_name = validated_data.pop('category_name')
            user = self.context['request'].user
            category, created = Category.objects.get_or_create(name=category_name, user=user)
            validated_data['category'] = category
        
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