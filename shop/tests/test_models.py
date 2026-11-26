from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase, TransactionTestCase, skipUnlessDBFeature

from shop.models import Product, Purchase
from shop.services import discount_for, quote_purchase, record_purchase


class DiscountTests(SimpleTestCase):
    def test_thresholds(self):
        for count, expected in [(0, 0), (2, 0), (3, 5), (4, 5), (5, 10),
                                (9, 10), (10, 15), (30, 15)]:
            with self.subTest(count=count):
                self.assertEqual(discount_for(count), expected)

    def test_calculates_exact_kopecks(self):
        quote = quote_purchase(349, 3)
        self.assertEqual(quote.base_price, Decimal('349.00'))
        self.assertEqual(quote.discount_percent, 5)
        self.assertEqual(quote.total, Decimal('331.55'))


class PurchaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.customer = get_user_model().objects.create_user(username='buyer')
        cls.other = get_user_model().objects.create_user(username='other')
        cls.towel = Product.objects.create(name='Полотенце', price=390)
        cls.basket = Product.objects.create(name='Корзина', price=1250)

    def test_discount_increases_across_products_only_for_their_buyer(self):
        products = [self.towel, self.basket] * 5 + [self.towel]
        discounts = [record_purchase(self.customer, product, 'Адрес', uuid4()).discount_percent
                     for product in products]
        self.assertEqual(discounts, [0, 0, 0, 5, 5, 10, 10, 10, 10, 10, 15])
        purchase = record_purchase(self.other, self.towel, 'Адрес', uuid4())
        self.assertEqual(purchase.discount_percent, 0)
        self.assertEqual(self.customer.purchases.count(), 11)

    def test_retry_returns_the_same_purchase(self):
        checkout_id = uuid4()
        purchase = record_purchase(self.customer, self.towel, 'Адрес', checkout_id)
        retry = record_purchase(self.customer, self.basket, 'Другой адрес', checkout_id)
        self.assertEqual(purchase, retry)
        self.assertEqual(purchase, Purchase.objects.get())
        self.assertEqual(purchase.product, self.towel)
        self.assertEqual(purchase.address, 'Адрес')

    def test_checkout_id_is_scoped_to_the_customer(self):
        checkout_id = uuid4()
        first = record_purchase(self.customer, self.towel, 'Адрес', checkout_id)
        second = record_purchase(self.other, self.towel, 'Адрес', checkout_id)
        self.assertNotEqual(first, second)

    def test_receipt_price_is_saved_and_product_is_protected(self):
        purchase = record_purchase(self.customer, self.towel, 'Адрес', uuid4())
        self.towel.price = 999
        self.towel.save(update_fields=['price'])
        purchase.refresh_from_db()
        self.assertEqual(purchase.base_price, Decimal('390.00'))
        self.assertEqual(purchase.total, Decimal('390.00'))
        self.assertEqual(purchase.person, 'buyer')
        self.assertEqual(str(purchase.product), 'Полотенце')
        with self.assertRaises(ProtectedError):
            self.towel.delete()


class PurchaseConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_purchases_cross_the_threshold_once(self):
        customer = get_user_model().objects.create_user(username='buyer')
        product = Product.objects.create(name='Полотенце', price=390)
        for _ in range(2):
            record_purchase(customer, product, 'Адрес', uuid4())
        barrier = Barrier(2, timeout=5)

        def buy():
            try:
                barrier.wait()
                return record_purchase(customer, product, 'Адрес', uuid4()).discount_percent
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            purchases = [pool.submit(buy), pool.submit(buy)]
            self.assertEqual(sorted(future.result(timeout=10) for future in purchases), [0, 5])
        self.assertEqual(customer.purchases.count(), 4)


class LegacyMigrationTests(TransactionTestCase):
    def test_existing_purchase_is_preserved_without_guessing_its_customer(self):
        previous = [('shop', '0001_initial')]
        current = [('shop', '0002_customer_loyalty')]
        executor = MigrationExecutor(connection)
        try:
            executor.migrate(previous)
            old_models = executor.loader.project_state(previous).apps
            product = old_models.get_model('shop', 'Product').objects.create(
                name='Стол', price=2000,
            )
            old_purchase = old_models.get_model('shop', 'Purchase').objects.create(
                product_id=product.pk, person='buyer', address='Старый адрес',
            )
        finally:
            MigrationExecutor(connection).migrate(current)

        purchase = Purchase.objects.get(pk=old_purchase.pk)
        self.assertEqual(purchase.person, 'buyer')
        self.assertEqual(purchase.address, 'Старый адрес')
        self.assertIsNone(purchase.customer)
        self.assertEqual(purchase.base_price, Decimal('2000.00'))
        self.assertEqual(purchase.total, Decimal('2000.00'))
        self.assertEqual(purchase.discount_percent, 0)
