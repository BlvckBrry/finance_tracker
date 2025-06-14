import requests
from decimal import Decimal
from django.core.management.base import BaseCommand
from main.models import Currency  


class Command(BaseCommand):
    help = 'Update currency exchange rates from API'
    
    def handle(self, *args, **options):
        try:
            response = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
            response.raise_for_status()
            rates_data = response.json()
            currency_mapping = {
                'USD': 'USD',
                'EUR': 'EUR', 
                'GBP': 'GBP',
                'JPY': 'JPY',
                'PLN': 'PLN',
                'CZK': 'CZK'
            }
            updated_count = 0
            for rate_info in rates_data:
                currency_code = rate_info.get('cc')
                rate = rate_info.get('rate')
                
                if currency_code in currency_mapping and rate:
                    try:
                        currency = Currency.objects.get(code=currency_code)
                        currency.rate_to_uah = Decimal(str(rate))
                        currency.save()
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(f'Updated {currency_code}: {rate} UAH'))
                    except Currency.DoesNotExist:
                        Currency.objects.create(code=currency_code, name=rate_info.get('txt', currency_code), rate_to_uah=Decimal(str(rate)))
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(f'Created {currency_code}: {rate} UAH'))
            
            uah, created = Currency.objects.get_or_create(
                code='UAH',
                defaults={'name': 'Ukrainian Hryvnia', 'rate_to_uah': Decimal('1.0')}
            )
            if not created:
                uah.rate_to_uah = Decimal('1.0')
                uah.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated_count} currency rates')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating currency rates: {str(e)}')
            )