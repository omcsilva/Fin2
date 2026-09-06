"""Presentation filters for financial values."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()

SYMBOLS = {
    'BRL': 'R$', 'REAL': 'R$',
    'USD': 'US$', 'DOL': 'US$', 'DOLAR': 'US$',
    'EUR': '€',
    'GBP': '£',
}


@register.filter
def money(value, currency=''):
    """Format money with its currency and Brazilian numeric separators."""
    if value is None or value == '':
        return '—'
    try:
        amount=Decimal(str(value)).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    except (InvalidOperation,ValueError):
        return '—'
    code=str(currency or '').strip().upper()
    prefix=SYMBOLS.get(code,code or '¤')
    rendered=f'{abs(amount):,.2f}'.translate(str.maketrans({',':'.','.':','}))
    sign='-' if amount<0 else ''
    return f'{sign}{prefix} {rendered}'


@register.filter
def number(value):
    """Format a decimal with Brazilian separators and at most four decimals."""
    if value is None or value == '':
        return '—'
    try:
        amount=Decimal(str(value)).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP)
    except (InvalidOperation,ValueError):
        return '—'
    rendered=f'{abs(amount):,.4f}'.translate(str.maketrans({',':'.','.':','})).rstrip('0').rstrip(',')
    sign='-' if amount<0 else ''
    return f'{sign}{rendered}'
