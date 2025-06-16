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
            
            if 'rates' not in rates_data:
                self.stdout.write(self.style.ERROR('No rates found in API response'))
                return
            
            currency_mapping = {
                'USD': 'US Dollar',
                'EUR': 'Euro', 
                'GBP': 'British Pound',
                'JPY': 'Japanese Yen',
                'PLN': 'Polish Zloty',
                'CZK': 'Czech Koruna'
            }
            
            updated_count = 0
            rates = rates_data['rates']
            
            if 'UAH' in rates:
                usd_to_uah_rate = rates['UAH']
                usd_currency, created = Currency.objects.update_or_create(
                    code='USD',
                    defaults={
                        'name': currency_mapping.get('USD', 'US Dollar'),
                        'rate_to_uah': Decimal(str(usd_to_uah_rate))
                    }
                )
                action = 'Created' if created else 'Updated'
                self.stdout.write(self.style.SUCCESS(f'{action} USD: {usd_to_uah_rate} UAH'))
                updated_count += 1
            
            for currency_code, usd_rate in rates.items():
                if currency_code in currency_mapping and currency_code != 'USD':
                    try:
                        uah_rate = rates['UAH']  
                        rate_to_uah = Decimal(str(uah_rate)) / Decimal(str(usd_rate))
                        
                        currency, created = Currency.objects.update_or_create(
                            code=currency_code,
                            defaults={
                                'name': currency_mapping[currency_code],
                                'rate_to_uah': rate_to_uah
                            }
                        )
                        action = 'Created' if created else 'Updated'
                        updated_count += 1
                        self.stdout.write(self.style.SUCCESS(f'{action} {currency_code}: {rate_to_uah:.4f} UAH'))
                        
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Error processing {currency_code}: {str(e)}'))
            
            uah, created = Currency.objects.update_or_create(
                code='UAH',
                defaults={'name': 'Ukrainian Hryvnia', 'rate_to_uah': Decimal('1.0')}
            )
            action = 'Created' if created else 'Updated'
            self.stdout.write(self.style.SUCCESS(f'{action} UAH: 1.0 UAH'))
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated {updated_count} currency rates')
            )
            
        except requests.RequestException as e:
            self.stdout.write(
                self.style.ERROR(f'API request error: {str(e)}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error updating currency rates: {str(e)}')
            )
