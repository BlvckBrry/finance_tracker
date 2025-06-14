from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.conf import settings


class Currency(models.Model):
    code = models.CharField(max_length=3, unique=True)  
    name = models.CharField(max_length=50)  
    rate_to_uah = models.DecimalField(max_digits=10, decimal_places=4, default=1.0000)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Category(models.Model):
    name = models.CharField(max_length=100) 
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ['name', 'user']  
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class Balance(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, default='UAH')
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username}: {self.amount} {self.currency.code}"


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('income', 'Дохід'),
        ('expense', 'Витрата'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE, null=True, blank=True)
    type = models.CharField(max_length=7, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    title = models.CharField(max_length=200)  
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title}: {self.amount} ({self.type})"
    
    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_instance = None
        
        if not is_new:
            old_instance = Transaction.objects.get(pk=self.pk)
        
        self.amount = abs(self.amount)
        super().save(*args, **kwargs)
        
        if is_new:
            self._apply_to_balance()
        else:
            old_instance._revert_from_balance()
            self._apply_to_balance()

    def _apply_to_balance(self):
        uah_currency = Currency.objects.get(code='UAH')
        balance, created = Balance.objects.get_or_create(user=self.user, defaults={'currency': uah_currency})
        converted_amount = self._convert_to_uah(self.amount)

        if self.type == 'income':
            balance.amount += Decimal(converted_amount)
            
        elif self.type == 'expense':
            balance.amount -= Decimal(converted_amount)

        balance.save()


    def _revert_from_balance(self):
        try:
            balance = Balance.objects.get(user=self.user)
            converted_amount = self._convert_to_uah(self.amount)

            if self.type == 'income':
                balance.amount -= Decimal(converted_amount)

            elif self.type == 'expense':
                balance.amount += Decimal(converted_amount)

            balance.save()

        except Balance.DoesNotExist:
            pass

    def _convert_to_uah(self, amount):
        if not self.currency or self.currency.code == 'UAH':
            return amount
        
        try:
            exchange_rate = self.currency.rate_to_uah
            converted_amount = amount * Decimal(str(exchange_rate))
            return converted_amount
        except Exception as e:
            return amount

    class Meta:
        ordering = ['-created_at']