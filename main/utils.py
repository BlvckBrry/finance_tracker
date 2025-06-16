from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from .models import Transaction, Currency


def calculate_monthly_spending(user):
    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    expenses = Transaction.objects.filter(user=user,type='expense', created_at__gte=start_of_month)
    total_spending = Decimal('0.00')
    for expense in expenses:
        converted_amount = convert_to_uah(expense.amount, expense.currency)
        total_spending += converted_amount
    
    return total_spending


def convert_to_uah(amount, currency):
    if not currency or currency.code == 'UAH':
        return amount
    
    try:
        exchange_rate = currency.rate_to_uah
        return amount * Decimal(str(exchange_rate))
    except:
        return amount


def check_spending_limits(user, transaction_amount, transaction_currency):
    if not user.spending_limit:
        return
    
    current_spending = calculate_monthly_spending(user)
    new_transaction_amount = convert_to_uah(transaction_amount, transaction_currency)
    projected_spending = current_spending + new_transaction_amount
    spending_limit = user.spending_limit
    warning_threshold_amount = spending_limit * (user.warning_threshold / Decimal('100'))
    
    if projected_spending >= spending_limit:
        send_limit_exceeded_email(user, projected_spending, spending_limit)
    elif projected_spending >= warning_threshold_amount and should_send_warning(user):
        send_warning_email(user, projected_spending, spending_limit, user.warning_threshold)
        user.last_warning_sent = timezone.now()
        user.save()


def should_send_warning(user):
    if not user.last_warning_sent:
        return True
    
    time_since_last_warning = timezone.now() - user.last_warning_sent
    return time_since_last_warning > timedelta(hours=24)


def send_warning_email(user, current_spending, spending_limit, threshold_percentage):
    subject = 'Spending Limit Warning'
    message = f"""
Hello {user.username},

You have reached {threshold_percentage}% of your monthly spending limit.

Current spending: {current_spending} UAH
Monthly limit: {spending_limit} UAH
Remaining: {spending_limit - current_spending} UAH

Please monitor your expenses carefully.

Best regards,
Your Finance App
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_limit_exceeded_email(user, current_spending, spending_limit):
    subject = 'Spending Limit Exceeded!'
    message = f"""
Hello {user.username},

WARNING: You have exceeded your monthly spending limit!

Current spending: {current_spending} UAH
Monthly limit: {spending_limit} UAH
Overspent by: {current_spending - spending_limit} UAH

Please review your expenses and consider adjusting your budget.

Best regards,
Your Finance App
"""
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )