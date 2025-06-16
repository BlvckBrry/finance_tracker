from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=False)
    spending_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    warning_threshold = models.DecimalField(max_digits=5, decimal_places=2, default=80.00)
    last_warning_sent = models.DateTimeField(null=True, blank=True)
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    
    def __str__(self):
        return self.username