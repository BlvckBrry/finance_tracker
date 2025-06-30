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
            logger.info("Using cached currency data")
            return cached_data
        
        try:
            logger.info("Sending request to currency API", extra={
                'url': self.base_url,
                'timeout': self.timeout
            })
            response = requests.get(self.base_url, timeout=self.timeout, headers={'User-Agent': 'Django Currency App 1.0'})
            response.raise_for_status()
            data = response.json()
            logger.info("API response received successfully", extra={
                'status_code': response.status_code,
                'response_size': len(str(data))
            })
            
            if 'rates' not in data:
                logger.error("Rates not found in API response", extra={'response_data': data})
                return None
            
            logger.info("Currency rates fetched from API", extra={
                'currencies_count': len(data['rates']),
                'sample_currencies': list(data['rates'].keys())[:10]
            })
            cache.set(cache_key, data, self.cache_timeout)
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error("Request API error occurred", extra={
                'error': str(e),
                'url': self.base_url,
                'timeout': self.timeout
            })
            return None
    
    def update_database_currencies(self) -> bool:
        logger.info("Starting currency update process")
        api_data = self.fetch_currencies_from_api()
        
        if not api_data or 'rates' not in api_data:
            logger.error("No data received from API for currency update")
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
            logger.info("Processing currency rates", extra={'total_rates': len(rates)})
            
            if 'UAH' not in rates:
                logger.critical("UAH currency not found in API response", extra={'available_currencies': list(rates.keys())})
                return False
            
            usd_rate_to_uah = rates['UAH']
            logger.info("Processing USD currency", extra={'usd_to_uah_rate': usd_rate_to_uah})
            usd_currency, created = Currency.objects.update_or_create(
                code='USD',
                defaults={
                    'name': currency_names.get('USD', 'USA Dollar'),
                    'rate_to_uah': Decimal(str(usd_rate_to_uah))
                }
            )
            logger.info("USD currency processed", extra={
                'action': 'created' if created else 'updated',
                'currency_code': usd_currency.code,
                'rate': str(usd_currency.rate_to_uah)
            })
            
            logger.info("Processing UAH currency")
            uah_currency, created = Currency.objects.update_or_create(
                code='UAH',
                defaults={
                    'name': 'Hryvnia',
                    'rate_to_uah': Decimal('1.0000')
                }
            )
            logger.info("UAH currency processed", extra={
                'action': 'created' if created else 'updated',
                'currency_code': uah_currency.code,
                'rate': str(uah_currency.rate_to_uah)
            })
            
            logger.info("Processing other currencies")
            processed_count = 0
            error_count = 0
            
            for code, usd_rate in rates.items():
                if code in ['USD', 'UAH']:
                    continue
                
                try:
                    logger.debug("Processing currency", extra={
                        'currency_code': code,
                        'usd_rate': usd_rate
                    })
                    rate_to_uah = Decimal(str(usd_rate_to_uah)) / Decimal(str(usd_rate))
                    logger.debug("Calculated rate to UAH", extra={
                        'currency_code': code,
                        'rate_to_uah': str(rate_to_uah)
                    })
                    currency, created = Currency.objects.update_or_create(
                        code=code,
                        defaults={
                            'name': currency_names.get(code, code),
                            'rate_to_uah': rate_to_uah
                        }
                    )
                    logger.debug("Currency processed successfully", extra={
                        'currency_code': code,
                        'action': 'created' if created else 'updated',
                        'rate': str(currency.rate_to_uah)
                    })
                    processed_count += 1
                    
                except Exception as e:
                    logger.warning("Error processing currency", extra={
                        'currency_code': code,
                        'error': str(e)
                    })
                    error_count += 1
                    continue
            
            total_currencies = Currency.objects.count()
            sample_currencies = list(Currency.objects.all()[:10])
            
            logger.info("Currency update completed", extra={
                'processed_count': processed_count,
                'error_count': error_count,
                'total_currencies_in_db': total_currencies,
                'sample_currencies': [
                    {'code': c.code, 'name': c.name, 'rate': str(c.rate_to_uah)} 
                    for c in sample_currencies
                ]
            })
            
            return True
            
        except Exception as e:
            logger.error("Critical error during currency update", extra={
                'error': str(e),
                'error_type': type(e).__name__
            }, exc_info=True)
            return False