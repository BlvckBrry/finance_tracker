from django.contrib import admin
from .models import Transaction, Category, Currency, Balance


admin.site.register(Transaction)
admin.site.register(Category)
admin.site.register(Currency)
admin.site.register(Balance)