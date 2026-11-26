from uuid import uuid4

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.functional import cached_property
from django.views.generic.edit import FormView

from .forms import PurchaseForm
from .models import Product, Purchase
from .services import DISCOUNT_TIERS, discount_for, quote_purchase, record_purchase


def index(request):
    products = Product.objects.order_by('pk')
    purchase_count = request.user.purchases.count() if request.user.is_authenticated else 0
    return render(request, 'shop/index.html', {
        'products': products,
        'tiers': DISCOUNT_TIERS[1:],
        'discount': discount_for(purchase_count),
    })


def register(request):
    if request.user.is_authenticated:
        return redirect('account')
    form = UserCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('account')
    return render(request, 'registration/register.html', {'form': form})


class PurchaseCreate(LoginRequiredMixin, FormView):
    form_class = PurchaseForm
    template_name = 'shop/purchase_form.html'

    @cached_property
    def product(self):
        return get_object_or_404(Product, pk=self.kwargs['product_id'])

    def get_initial(self):
        return {'checkout_id': uuid4()}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        context['quote'] = quote_purchase(
            self.product.price, self.request.user.purchases.count(),
        )
        return context

    def form_valid(self, form):
        purchase = record_purchase(self.request.user, self.product,
                                   **form.cleaned_data)
        return redirect('receipt', purchase_id=purchase.pk)


@login_required
def account(request):
    purchases = request.user.purchases.select_related('product').order_by('-date', '-pk')
    purchase_count = len(purchases)
    return render(request, 'shop/account.html', {
        'purchases': purchases,
        'purchase_count': purchase_count,
        'discount': discount_for(purchase_count),
    })


@login_required
def receipt(request, purchase_id):
    purchase = get_object_or_404(
        Purchase.objects.select_related('product'), pk=purchase_id, customer=request.user,
    )
    return render(request, 'shop/receipt.html', {'purchase': purchase})
