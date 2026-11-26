from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from shop.models import Product, Purchase
from shop.services import record_purchase


class ShopViewsTests(TestCase):
    fixtures = ['products.yaml']

    @classmethod
    def setUpTestData(cls):
        cls.customer = get_user_model().objects.create_user(username='buyer')
        cls.other = get_user_model().objects.create_user(username='other')
        cls.product = Product.objects.get(name='Контейнер для продуктов')

    def setUp(self):
        self.buy_url = reverse('buy', args=[self.product.pk])

    def test_catalog_uses_household_fixture(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'Накопительная скидка')
        self.assertContains(response, self.buy_url)
        self.assertEqual(len(response.context['products']), 9)

    def test_empty_catalog_has_a_message(self):
        Product.objects.all().delete()
        self.assertContains(self.client.get(reverse('index')), 'В каталоге пока нет товаров')

    def test_checkout_and_history_require_login(self):
        for path in [self.buy_url, reverse('account'), reverse('receipt', args=[1])]:
            with self.subTest(path=path):
                self.assertRedirects(self.client.get(path), reverse('login') + f'?next={path}')
        self.assertRedirects(self.client.post(self.buy_url), reverse('login') + f'?next={self.buy_url}')
        self.assertFalse(Purchase.objects.exists())

    def test_checkout_uses_url_product_and_server_calculates_price(self):
        self.client.force_login(self.customer)
        for product in Product.objects.order_by('pk')[:3]:
            record_purchase(self.customer, product, 'Адрес', uuid4())

        form = self.client.get(self.buy_url).context['form']
        data = {'address': 'Учебная улица, 1', 'checkout_id': form['checkout_id'].value(),
                'product': 1, 'total': '1.00', 'discount_percent': 100}
        response = self.client.post(self.buy_url, data)
        purchase = Purchase.objects.latest('pk')
        self.assertEqual(purchase.product, self.product)
        self.assertEqual(purchase.discount_percent, 5)
        self.assertEqual(purchase.total, Decimal('331.55'))
        self.assertRedirects(response, reverse('receipt', args=[purchase.pk]))
        self.assertContains(self.client.get(response.url), '331,55')
        self.assertRedirects(self.client.post(self.buy_url, data), response.url)
        self.assertEqual(self.customer.purchases.count(), 4)

    def test_invalid_checkout_has_errors_and_does_not_create_purchase(self):
        self.client.force_login(self.customer)
        response = self.client.post(self.buy_url, {'address': ' ', 'checkout_id': 'bad'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.context['form'].errors), {'address', 'checkout_id'})
        self.assertFalse(Purchase.objects.exists())

    def test_missing_product_returns_404(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse('buy', args=[1000]))
        self.assertEqual(response.status_code, 404)

    def test_customer_sees_own_history_and_cannot_open_another_receipt(self):
        for _ in range(3):
            record_purchase(self.customer, self.product, 'Адрес', uuid4())
        other_product = Product.objects.get(name='Стол')
        other_purchase = record_purchase(self.other, other_product, 'Другой адрес', uuid4())
        self.client.force_login(self.customer)

        response = self.client.get(reverse('account'))
        self.assertEqual(response.context['purchase_count'], 3)
        self.assertEqual(response.context['discount'], 5)
        self.assertEqual(self.client.get(reverse('index')).context['discount'], 5)
        self.assertNotContains(response, other_product.name)
        self.assertEqual(self.client.get(reverse('receipt', args=[other_purchase.pk])).status_code, 404)

    def test_post_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)
        response = client.post(self.buy_url, {'address': 'Адрес', 'checkout_id': uuid4()})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Purchase.objects.exists())


class AccountViewsTests(TestCase):
    def test_register_login_and_logout(self):
        credentials = {'username': 'new-buyer', 'password': 'Bridge189!violet'}
        password = credentials['password']
        url = reverse('register')
        self.assertContains(self.client.get(url), 'Регистрация')
        response = self.client.post(url, {'username': credentials['username'],
                                          'password1': password, 'password2': password})
        self.assertRedirects(response, reverse('account'))
        response = self.client.get(reverse('account'))
        self.assertContains(response, 'Ваши покупки появятся здесь')
        self.assertRedirects(self.client.get(url), reverse('account'))
        self.assertRedirects(self.client.post(reverse('logout')), reverse('index'))
        self.assertContains(self.client.get(reverse('login')), 'Войти')
        self.assertRedirects(self.client.post(reverse('login'), credentials), reverse('account'))

    def test_mismatched_passwords_do_not_create_an_account(self):
        response = self.client.post(reverse('register'), {'username': 'new-buyer',
                                                         'password1': 'Bridge189!violet',
                                                         'password2': 'different-password'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(get_user_model().objects.filter(username='new-buyer').exists())
