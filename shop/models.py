from django.conf import settings
from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=200)
    price = models.PositiveIntegerField()
    category = models.CharField(max_length=80, blank=True)
    description = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name


class Purchase(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        blank=True, related_name='purchases',
    )
    person = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percent = models.PositiveSmallIntegerField(default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    checkout_id = models.UUIDField(null=True, editable=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'checkout_id'],
                name='unique_customer_checkout',
            ),
        ]
