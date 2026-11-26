from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import Purchase


DISCOUNT_TIERS = ((0, 0), (3, 5), (5, 10), (10, 15))
KOPECK = Decimal('0.01')


@dataclass(frozen=True)
class PurchaseQuote:
    base_price: Decimal
    discount_percent: int
    total: Decimal


def discount_for(purchase_count):
    return next(percent for minimum, percent in reversed(DISCOUNT_TIERS)
                if purchase_count >= minimum)


def quote_purchase(price, purchase_count):
    percent = discount_for(purchase_count)
    base_price = Decimal(price).quantize(KOPECK)
    total = (base_price * (100 - percent) / 100).quantize(
        KOPECK, rounding=ROUND_HALF_UP,
    )
    return PurchaseQuote(base_price, percent, total)


@transaction.atomic
def record_purchase(customer, product, address, checkout_id):
    # A PostgreSQL row lock serializes purchase counts for this customer.
    customer = get_user_model().objects.select_for_update().get(pk=customer.pk)
    existing = customer.purchases.filter(checkout_id=checkout_id).first()
    if existing is not None:
        return existing

    quote = quote_purchase(product.price, customer.purchases.count())
    return customer.purchases.create(
        product=product,
        person=customer.get_username(),
        address=address,
        checkout_id=checkout_id,
        base_price=quote.base_price,
        discount_percent=quote.discount_percent,
        total=quote.total,
    )
