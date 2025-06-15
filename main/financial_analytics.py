import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
import io
from django.http import HttpResponse
from django.db.models import Sum, Q
from .models import Transaction, Category, Currency, Balance
from openpyxl.styles import NamedStyle


class FinancialAnalyticsService:
    def __init__(self, user, start_date=None, end_date=None):
        self.user = user
        self.start_date = start_date or (datetime.now() - timedelta(days=30))
        self.end_date = end_date or datetime.now()
    
    def get_transactions_dataframe(self):
        transactions = Transaction.objects.filter(user=self.user,
            created_at__range=[self.start_date, self.end_date]
        ).select_related('category', 'currency').values(
            'id', 'amount', 'title', 'created_at', 'type',
            'category__name', 'currency__code', 'currency__rate_to_uah'
        )
        df = pd.DataFrame(list(transactions))
        
        if df.empty:
            return pd.DataFrame()
        
        df['amount'] = pd.to_numeric(df['amount'])
        df['created_at'] = pd.to_datetime(df['created_at'])
        df['amount_uah'] = df['amount'].astype(float) * df['currency__rate_to_uah'].astype(float)
        df['income'] = df.apply(lambda x: x['amount_uah'] if x['type'] == 'income' else 0, axis=1)
        df['expense'] = df.apply(lambda x: x['amount_uah'] if x['type'] == 'expense' else 0, axis=1)
        
        return df
    
    def calculate_general_balance(self):
        df = self.get_transactions_dataframe()
        
        if df.empty:
            return {
                'total_income': 0,
                'total_expense': 0,
                'net_balance': 0,
                'current_balance': self._get_current_balance()
            }
        
        total_income = df['income'].sum()
        total_expense = df['expense'].sum()
        net_balance = total_income - total_expense
        daily_balance = df.groupby(df['created_at'].dt.date).agg({
            'income': 'sum',
            'expense': 'sum'
        }).reset_index()
        daily_balance['net'] = daily_balance['income'] - daily_balance['expense']
        daily_balance['cumulative'] = daily_balance['net'].cumsum()
        
        return {
            'total_income': float(total_income),
            'total_expense': float(total_expense),
            'net_balance': float(net_balance),
            'current_balance': self._get_current_balance(),
            'daily_trend': daily_balance.to_dict('records')
        }
    
    def analyze_by_categories(self):
        df = self.get_transactions_dataframe()
        
        if df.empty:
            return {'income_categories': [], 'expense_categories': []}
        
        income_analysis = df[df['type'] == 'income'].groupby('category__name').agg({
            'amount_uah': ['sum', 'count', 'mean'],
            'created_at': ['min', 'max']
        }).round(2)
        
        income_analysis.columns = ['total', 'count', 'average', 'first_date', 'last_date']
        income_analysis['percentage'] = (income_analysis['total'] / income_analysis['total'].sum() * 100).round(2)
        income_analysis = income_analysis.reset_index()
        expense_analysis = df[df['type'] == 'expense'].groupby('category__name').agg({
            'amount_uah': ['sum', 'count', 'mean'],
            'created_at': ['min', 'max']
        }).round(2)
        
        expense_analysis.columns = ['total', 'count', 'average', 'first_date', 'last_date']
        expense_analysis['percentage'] = (expense_analysis['total'] / expense_analysis['total'].sum() * 100).round(2)
        expense_analysis = expense_analysis.reset_index()
        top_income = income_analysis.nlargest(5, 'total')
        top_expense = expense_analysis.nlargest(5, 'total')
        
        return {
            'income_categories': income_analysis.to_dict('records'),
            'expense_categories': expense_analysis.to_dict('records'),
            'top_income_categories': top_income.to_dict('records'),
            'top_expense_categories': top_expense.to_dict('records')
        }

    def _analyze_filtered_categories(self, filtered_df):
        if filtered_df.empty:
            return {
                'income_categories': [],
                'expense_categories': [],
                'summary': {
                    'total_categories': 0,
                    'total_income': 0,
                    'total_expense': 0
                }
            }
        
        income_df = filtered_df[filtered_df['type'] == 'income']
        if not income_df.empty:
            income_analysis = income_df.groupby('category__name').agg({
                'amount_uah': ['sum', 'count', 'mean'],
                'created_at': ['min', 'max']
            }).round(2)
            
            income_analysis.columns = ['total', 'count', 'average', 'first_date', 'last_date']
            income_analysis['percentage'] = (income_analysis['total'] / income_analysis['total'].sum() * 100).round(2)
            income_analysis = income_analysis.reset_index()
            income_categories = income_analysis.to_dict('records')
            total_income = float(income_df['amount_uah'].sum())
        else:
            income_categories = []
            total_income = 0
        
        expense_df = filtered_df[filtered_df['type'] == 'expense']
        if not expense_df.empty:
            expense_analysis = expense_df.groupby('category__name').agg({
                'amount_uah': ['sum', 'count', 'mean'],
                'created_at': ['min', 'max']
            }).round(2)
            
            expense_analysis.columns = ['total', 'count', 'average', 'first_date', 'last_date']
            expense_analysis['percentage'] = (expense_analysis['total'] / expense_analysis['total'].sum() * 100).round(2)
            expense_analysis = expense_analysis.reset_index()
            expense_categories = expense_analysis.to_dict('records')
            total_expense = float(expense_df['amount_uah'].sum())
        else:
            expense_categories = []
            total_expense = 0
        
        total_categories = len(filtered_df['category__name'].unique())
        
        return {
            'income_categories': income_categories,
            'expense_categories': expense_categories,
            'summary': {
                'total_categories': total_categories,
                'total_income': total_income,
                'total_expense': total_expense,
                'net_balance': total_income - total_expense
            }
        }
    
    def export_to_excel(self, transaction_type=None, category_name=None, currency_code=None):
        df = self.get_transactions_dataframe()
        if df.empty:
            return None

        filtered_df = df.copy()
        if transaction_type:
            if transaction_type.lower() == 'income':
                filtered_df = filtered_df[filtered_df['type'] == 'income']

            elif transaction_type.lower() == 'expense':
                filtered_df = filtered_df[filtered_df['type'] == 'expense']
        
        if category_name:
            filtered_df = filtered_df[filtered_df['category__name'].str.contains(category_name, case=False, na=False)]
        
        if currency_code:
            filtered_df = filtered_df[filtered_df['currency__code'] == currency_code.upper()]
        
        if filtered_df.empty:
            return None

        export_df = filtered_df[[
            'created_at', 'type', 'category__name', 'title', 
            'amount', 'currency__code', 'amount_uah'
        ]].copy()

        for col in export_df.columns:
            if pd.api.types.is_datetime64_any_dtype(export_df[col]):
                if hasattr(export_df[col].dtype, 'tz') and export_df[col].dtype.tz is not None:
                    export_df[col] = export_df[col].dt.tz_localize(None)

        export_df.columns = [
            'Date', 'Type', 'Category', 'Title', 
            'Amount', 'Currency', 'Rate to UAH'
        ]

        filename_parts = ['Transactions']
        if transaction_type:
            filename_parts.append(f"Type_{transaction_type}")

        if category_name:
            filename_parts.append(f"Category{category_name}")

        if currency_code:
            filename_parts.append(f"Currency_{currency_code}")

        main_sheet_name = '_'.join(filename_parts)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, sheet_name='Transactions', index=False)
            worksheet = writer.sheets['Transactions']
            worksheet.column_dimensions['A'].width = 20  
            worksheet.column_dimensions['B'].width = 15  
            worksheet.column_dimensions['C'].width = 25  
            worksheet.column_dimensions['D'].width = 30  
            worksheet.column_dimensions['E'].width = 15  
            worksheet.column_dimensions['F'].width = 10  
            worksheet.column_dimensions['G'].width = 15  
            date_style = NamedStyle(name='datetime', number_format='DD.MM.YYYY HH:MM')

            for row in range(2, len(export_df) + 2):  
                worksheet[f'A{row}'].style = date_style
            
            category_analysis = self._analyze_filtered_categories(filtered_df)
            
            if category_analysis['income_categories']:
                income_df = pd.DataFrame(category_analysis['income_categories'])
                for col in income_df.columns:
                    if pd.api.types.is_datetime64_any_dtype(income_df[col]):
                        if hasattr(income_df[col].dtype, 'tz') and income_df[col].dtype.tz is not None:
                            income_df[col] = income_df[col].dt.tz_localize(None)
                income_df.to_excel(writer, sheet_name='Incomes by categories', index=False)
                
                if 'Incomes by categories' in writer.sheets:
                    ws_income = writer.sheets['Incomes by categories']
                    for col_num, col in enumerate(income_df.columns, 1):
                        ws_income.column_dimensions[chr(64 + col_num)].width = 20
            
            if category_analysis['expense_categories']:
                expense_df = pd.DataFrame(category_analysis['expense_categories'])
                for col in expense_df.columns:
                    if pd.api.types.is_datetime64_any_dtype(expense_df[col]):
                        if hasattr(expense_df[col].dtype, 'tz') and expense_df[col].dtype.tz is not None:
                            expense_df[col] = expense_df[col].dt.tz_localize(None)
                expense_df.to_excel(writer, sheet_name='Expenses by categories', index=False)
                
                if 'Expenses by categories' in writer.sheets:
                    ws_expense = writer.sheets['Expenses by categories']
                    for col_num, col in enumerate(expense_df.columns, 1):
                        ws_expense.column_dimensions[chr(64 + col_num)].width = 20
            
            df_copy = filtered_df.copy()
            if pd.api.types.is_datetime64_any_dtype(df_copy['created_at']):
                if hasattr(df_copy['created_at'].dtype, 'tz') and df_copy['created_at'].dtype.tz is not None:
                    df_copy['created_at'] = df_copy['created_at'].dt.tz_localize(None)
            
            daily_stats = df_copy.groupby(df_copy['created_at'].dt.date).agg({
                'income': 'sum',
                'expense': 'sum',
                'amount_uah': 'count'
            }).reset_index()
            daily_stats.columns = ['Date', 'Incomes', 'Expenses', 'Number of transactions']
            daily_stats['Clean result'] = daily_stats['Incomes'] - daily_stats['Expanses']
            daily_stats.to_excel(writer, sheet_name='Daily statistic', index=False)
            ws_daily = writer.sheets['Daily statistic']
            ws_daily.column_dimensions['A'].width = 15  
            ws_daily.column_dimensions['B'].width = 15  
            ws_daily.column_dimensions['C'].width = 15  
            ws_daily.column_dimensions['D'].width = 25  
            ws_daily.column_dimensions['E'].width = 20  
            date_style_short = NamedStyle(name='date_short', number_format='DD.MM.YYYY')
            for row in range(2, len(daily_stats) + 2):
                ws_daily[f'A{row}'].style = date_style_short
            
            filter_info = []
            filter_info.append(['Used filters:', ''])
            filter_info.append(['Type of transaction:', transaction_type or 'All'])
            filter_info.append(['Category:', category_name or 'All'])
            filter_info.append(['Currency:', currency_code or 'All'])
            filter_info.append(['Number of notes:', len(export_df)])
            filter_info.append(['Creating date:', pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')])
            filter_df = pd.DataFrame(filter_info, columns=['Param', 'Value'])
            filter_df.to_excel(writer, sheet_name='Information about filters', index=False)
            ws_info = writer.sheets['Information about filters']
            ws_info.column_dimensions['A'].width = 25
            ws_info.column_dimensions['B'].width = 20
        
        output.seek(0)
        return output

    def _analyze_filtered_categories(self, df):
        income_data = df[df['type'] == 'income']
        expense_data = df[df['type'] == 'expense']
        income_categories = []
        if not income_data.empty:
            income_by_category = income_data.groupby('category__name')['amount_uah'].sum().reset_index()
            income_categories = [
                {'category': row['category__name'], 'total_amount': row['amount_uah']}
                for _, row in income_by_category.iterrows()
            ]
        
        expense_categories = []
        if not expense_data.empty:
            expense_by_category = expense_data.groupby('category__name')['amount_uah'].sum().reset_index()
            expense_categories = [
                {'category': row['category__name'], 'total_amount': row['amount_uah']}
                for _, row in expense_by_category.iterrows()
            ]
        
        return {
            'income_categories': income_categories,
            'expense_categories': expense_categories
        }
    
    def import_from_excel(self, excel_file):
        try:
            df = pd.read_excel(excel_file, sheet_name=0)
            required_columns = ['created_at', 'type', 'category', 'amount', 'currency', 'title']
            missing_columns = set(required_columns) - set(df.columns.str.lower())
            if missing_columns:
                return {
                    'success': False,
                    'error': f'Missing columns: {missing_columns}',
                    'imported_count': 0
                }
            
            df.columns = df.columns.str.lower()
            df = self._clean_import_data(df)
            created_transactions = []
            errors = []
            
            for index, row in df.iterrows():
                try:
                    category, created = Category.objects.get_or_create(
                        name=row['category'],
                        user=self.user,
                        defaults={'type': row['type']}
                    )
                    currency = Currency.objects.get(code=row['currency'].upper())
                    transaction = Transaction.objects.create(
                        user=self.user,
                        amount=Decimal(str(row['amount'])),
                        title=row['title'],
                        created_at=row['created_at'],
                        type=row['type'],
                        category=category,
                        currency=currency
                    )
                    
                    created_transactions.append(transaction)

                except Exception as e:
                    errors.append(f'Row {index + 2}: {str(e)}')
            
            return {
                'success': True,
                'imported_count': len(created_transactions),
                'errors': errors,
                'total_rows': len(df)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'imported_count': 0
            }

    def _clean_import_data(self, df):
        df = df.dropna(subset=['amount', 'type', 'category'])
        df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
        df = df.dropna(subset=['created_at'])
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df = df[df['amount'] > 0]
        df['type'] = df['type'].str.lower().map({
            'доход': 'income',
            'income': 'income',
            'витрата': 'expense', 
            'expense': 'expense'
        })
        df = df.dropna(subset=['type'])
        df['title'] = df['title'].fillna('Import from Excel')
        df['currency'] = df['currency'].str.upper()
        df['currency'] = df['currency'].fillna('UAH')
        
        return df
    
    def _get_current_balance(self):
        try:
            balance = Balance.objects.get(user=self.user)
            return float(balance.amount)
        except Balance.DoesNotExist:
            return 0.0