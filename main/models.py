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
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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
    
    def delete(self, *args, **kwargs):
        self._revert_from_balance()
        super().delete(*args, **kwargs)
    
    def _apply_to_balance(self):
        balance, created = Balance.objects.get_or_create(user=self.user, defaults={'currency_id': 1})
        
        if self.type == 'income':
            balance.amount += Decimal(self.amount)
        elif self.type == 'expense':
            balance.amount -= Decimal(self.amount)
        
        balance.save()
    
    def _revert_from_balance(self):
        try:
            balance = Balance.objects.get(user=self.user)
            
            if self.type == 'income':
                balance.amount -= self.amount
            elif self.type == 'expense':
                balance.amount += self.amount
            
            balance.save()

        except Balance.DoesNotExist:
            pass

    class Meta:
        ordering = ['-created_at']