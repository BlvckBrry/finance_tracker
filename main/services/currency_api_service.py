import requests
import logging
from decimal import Decimal
from django.core.cache import cache
from typing import Dict, Optional
from ..models import Currency

logger = logging.getLogger(__name__)

class CurrencyAPIService:    
    def __init__(self):
        self.base_url = "https://api.exchangerate-api.com/v4/latest/USD"
        self.timeout = 10
        self.cache_timeout = 3600
    
    def fetch_currencies_from_api(self) -> Optional[Dict]:
        cache_key = "external_currency_rates"
        cached_data = cache.get(cache_key)

        if cached_data:
            print("Using cached data")
            return cached_data
        
        try:
            print("SENDING A REQUEST TO API...")
            response = requests.get(self.base_url, timeout=self.timeout, headers={'User-Agent': 'Django Currency App 1.0'})
            response.raise_for_status()
            data = response.json()
            print(f"API RESPONSE RECEIVED. Status: {response.status_code}")
            
            if 'rates' not in data:
                print("ERROR: 'rates' NOT FOUND IN API RESPONSE")
                return None
            
            print(f"FOUND {len(data['rates'])} CURRENCIES IN API")
            print(f"FIRST 10 CURRENCIES: {list(data['rates'].keys())[:10]}")
            cache.set(cache_key, data, self.cache_timeout)
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"Request API error: {e}")
            logger.error(f"Request API error: {e}")
            return None
    
    def update_database_currencies(self) -> bool:
        print("\n=== UPDATING CURRENCIES ===")
        api_data = self.fetch_currencies_from_api()
        
        if not api_data or 'rates' not in api_data:
            print("ERROR: NO DATA RECEIVED FROM API")
            return False
        
        currency_names = {
            'USD': 'USA Dollar',
            'EUR': 'Euro', 
            'UAH': 'Hryvnia',
            'GBP': 'Pound',
            'JPY': 'Yen',
            'CAD': 'Canadian Dollar',
            'CHF': 'Swiss Franc',
            'AUD': 'Australian Dollar',
            'PLN': 'Polish Zloty',
            'CZK': 'Czech Crown',
            'CNY': 'Chinese Yuan',
        }
        
        try:
            rates = api_data['rates']
            print(f"PROCESSING {len(rates)} CURRENCIES")
            
            if 'UAH' not in rates:
                print("CRITICAL ERROR: UAH NOT FOUND IN API!")
                return False
            
            usd_rate_to_uah = rates['UAH']
            print(f"USD TO UAH RATE: {usd_rate_to_uah}")
            print("UPDATING USD")
            usd_currency, created = Currency.objects.update_or_create(
                code='USD',
                defaults={
                    'name': currency_names.get('USD', 'USA Dollar'),
                    'rate_to_uah': Decimal(str(usd_rate_to_uah))
                }
            )
            print(f"USD {'CREATED' if created else 'UPDATED'}: {usd_currency}")
            print("UPDATE UAH...")
            uah_currency, created = Currency.objects.update_or_create(
                code='UAH',
                defaults={
                    'name': 'Hryvnia',
                    'rate_to_uah': Decimal('1.0000')
                }
            )
            print(f"UAH {'CREATED' if created else 'UPDATED'}: {uah_currency}")
            print("\nWE PROCESS OTHER CURRENCIES...")
            processed_count = 0
            error_count = 0
            
            for code, usd_rate in rates.items():
                if code in ['USD', 'UAH']:
                    continue
                
                try:
                    print(f"Processing {code}: {usd_rate}")                    
                    rate_to_uah = Decimal(str(usd_rate_to_uah)) / Decimal(str(usd_rate))
                    print(f"Rate {code} to UAH: {rate_to_uah}")
                    currency, created = Currency.objects.update_or_create(
                        code=code,
                        defaults={
                            'name': currency_names.get(code, code),
                            'rate_to_uah': rate_to_uah
                        }
                    )
                    action = 'CREATED' if created else 'UPDATED'
                    print(f"  {code} {action}: {currency}")
                    processed_count += 1
                    
                except Exception as e:
                    print(f"ERROR processing {code}: {e}")
                    error_count += 1
                    continue
            
            print(f"\n=== RESULT ===")
            print(f"SUCCESSFULLY PROCESSED: {processed_count}")
            print(f"ERRORS: {error_count}")            
            total_currencies = Currency.objects.count()
            print(f"TOTAL CURRENCIES IN THE BASE: {total_currencies}")
            print("CURRENCIES IN THE DATABASE:")
            for currency in Currency.objects.all()[:10]:  
                print(f"{currency.code}: {currency.name} = {currency.rate_to_uah}")
            
            logger.info(f"Currencies successfully updated: {processed_count} processed, {error_count} errors")
            return True
            
        except Exception as e:
            print(f"CRITICAL ERROR: {e}")
            logger.error(f"Currency update error: {e}")
            import traceback
            print(f"TRACEBACK: {traceback.format_exc()}")
            return False