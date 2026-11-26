from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def fill_legacy_prices(apps, schema_editor):
    Product = apps.get_model('shop', 'Product')
    Purchase = apps.get_model('shop', 'Purchase')
    database = schema_editor.connection.alias
    products = Product.objects.using(database).values_list('pk', 'price')
    purchases = Purchase.objects.using(database)
    for product_id, price in products.iterator():
        purchases.filter(product_id=product_id).update(base_price=price, total=price)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('shop', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product', name='category',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='product', name='description',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='purchase', name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                    to='shop.product'),
        ),
        migrations.AddField(
            model_name='purchase', name='customer',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='purchases', to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='purchase', name='checkout_id',
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name='purchase', name='discount_percent',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='purchase', name='base_price',
            field=models.DecimalField(decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='purchase', name='total',
            field=models.DecimalField(decimal_places=2, max_digits=12, null=True),
        ),
        migrations.RunPython(fill_legacy_prices, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='purchase', name='base_price',
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name='purchase', name='total',
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AddConstraint(
            model_name='purchase',
            constraint=models.UniqueConstraint(
                fields=('customer', 'checkout_id'), name='unique_customer_checkout',
            ),
        ),
    ]
