"""Presentation filters for financial values."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date, datetime

from django import template

from fin2.imports.xp_reconciliation import category_label

register = template.Library()
# The reviewer always sees the category wording, never the internal slug; the
# mapping lives with the categories themselves.
register.filter('category_label', category_label)


@register.filter
def short_date(value):
    """Format date objects and imported ISO dates as DD/MM/YY."""
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            return '—'
    if not isinstance(value, (date, datetime)):
        return '—'
    return value.strftime('%d/%m/%y')

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
