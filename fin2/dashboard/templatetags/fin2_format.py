"""Presentation filters for financial values."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import date, datetime

from django import template
from django.urls import reverse

from fin2.imports.xp_reconciliation import category_label

register = template.Library()
# The reviewer always sees the category wording, never the internal slug; the
# mapping lives with the categories themselves.
register.filter('category_label', category_label)


@register.simple_tag
def import_step_url(step, import_id, selected_attachment=''):
    """Destination URL for the given import-wizard step, or '' when there is
    no selected import yet (steps 2-6 have nothing to navigate to)."""
    if step == 1:
        return reverse('statement-imports')
    if not import_id:
        return ''
    if step in (2, 6):
        return f"{reverse('statement-imports')}?preview={import_id}"
    if step == 3:
        return reverse('xp-statement-notes', args=[import_id])
    if step == 4:
        notes_url = reverse('xp-statement-notes', args=[import_id])
        # Without a currently selected attachment there is nothing to show
        # on step 4; land back on step 3 with a hint instead of guessing.
        if selected_attachment:
            return f"{notes_url}?attachment={selected_attachment}"
        return f"{notes_url}?review=1"
    if step == 5:
        return reverse('xp-statement-review', args=[import_id])
    return ''


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


DOCUMENT_TYPE_SYMBOLS = {
    'account_statement': '📑',
    'brokerage_note': '🧾',
    'investment_receipt': '💰',
    'transaction_file': '📄',
}
DOCUMENT_TYPE_LABELS = {
    'account_statement': 'Extrato de conta',
    'brokerage_note': 'Nota de corretagem',
    'investment_receipt': 'Recibo de investimento',
    'transaction_file': 'Arquivo de lançamentos',
}


@register.filter
def document_type_symbol(value):
    """Icon standing in for a file_import.document_type value."""
    return DOCUMENT_TYPE_SYMBOLS.get(value, '❔')


@register.filter
def document_type_label(value):
    """Human-readable text for a file_import.document_type value, used as alt/title."""
    return DOCUMENT_TYPE_LABELS.get(value, value)


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
