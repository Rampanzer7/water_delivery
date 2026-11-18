import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from app.models import Product, Cooler


class CatalogAndCoolersTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.water_product = Product.objects.create(
            name='Вода Тестовая 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=300,
            stock=10,
            is_active=True,
        )
        self.water_out_of_stock = Product.objects.create(
            name='Вода Закончилась 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=400,
            stock=0,
            is_active=True,
        )
        self.cooler_product = Product.objects.create(
            name='Кулер Тестовый Product',
            kind=Product.COOLER,
            price=800,
            stock=5,
            is_active=True,
        )
        self.cooler = Cooler.objects.create(
            name='Кулер Модель Aqua Test',
            description='Тестовый кулер для испытаний',
            monthly_price=550,
            deposit=1000,
            quantity=3,
        )

    def test_catalog_shows_only_water(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        products_in_page = list(response.context['page'].object_list)
        self.assertIn(self.water_product, products_in_page)
        self.assertNotIn(self.cooler_product, products_in_page)
        for p in products_in_page:
            self.assertEqual(p.kind, Product.WATER)

    def test_catalog_filters_and_search(self):
        # Search by query
        response = self.client.get(reverse('catalog'), {'q': 'Тестовая'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.water_product, response.context['page'].object_list)
        self.assertNotIn(self.water_out_of_stock, response.context['page'].object_list)

        # Filter only available
        response = self.client.get(reverse('catalog'), {'available': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.water_product, response.context['page'].object_list)
        self.assertNotIn(self.water_out_of_stock, response.context['page'].object_list)

        # Filter price bounds
        response = self.client.get(reverse('catalog'), {'price_min': '350'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.water_product, response.context['page'].object_list)
        self.assertIn(self.water_out_of_stock, response.context['page'].object_list)

    def test_catalog_kind_cooler_redirects_to_coolers(self):
        response = self.client.get(reverse('catalog'), {'kind': 'cooler'})
        self.assertRedirects(response, reverse('coolers'))

    def test_catalog_kind_cooler_preserves_query(self):
        response = self.client.get(reverse('catalog'), {'kind': 'cooler', 'q': 'Aqua'})
        self.assertRedirects(response, f"{reverse('coolers')}?q=Aqua")

    def test_catalog_html_has_no_coolers_tab(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        # Ensure there is no tab/pill for coolers in catalog.html
        self.assertNotIn('kind=cooler', html)
        self.assertNotIn('>Кулеры</a>', html)
        self.assertIn('Вода 19 л', html)

    def test_coolers_catalog_shows_coolers(self):
        response = self.client.get(reverse('coolers'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.cooler, response.context['coolers'])

    def test_coolers_catalog_search_filter(self):
        Cooler.objects.create(
            name='Другой аппарат Office',
            description='Кулер офисный',
            monthly_price=700,
            deposit=1000,
            quantity=2,
        )
        response = self.client.get(reverse('coolers'), {'q': 'Aqua'})
        self.assertEqual(response.status_code, 200)
        coolers_list = list(response.context['coolers'])
        self.assertEqual(len(coolers_list), 1)
        self.assertEqual(coolers_list[0].pk, self.cooler.pk)

    def test_coolers_rent_button_links_to_cooler_detail(self):
        response = self.client.get(reverse('coolers'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        detail_url = reverse('cooler_detail', kwargs={'pk': self.cooler.pk})
        rent_url = reverse('rent_cooler', kwargs={'pk': self.cooler.pk})
        # The 'Арендовать' button must point to cooler_detail, not directly to rent_cooler
        self.assertIn(f'href="{detail_url}" class="wire-card-btn"', html)
        self.assertNotIn(f'href="{rent_url}" class="wire-card-btn"', html)

    def test_home_page_buttons(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        # The 'Арендовать кулер' button on home hero must use wire-btn-cooler
        self.assertIn('wire-btn-cooler', html)

        # Cooler card in 'Если нужна аренда кулера' section must link 'Арендовать' to cooler_detail
        detail_url = reverse('cooler_detail', kwargs={'pk': self.cooler.pk})
        rent_url = reverse('rent_cooler', kwargs={'pk': self.cooler.pk})
        self.assertIn(f'href="{detail_url}"', html)
        self.assertNotIn(f'href="{rent_url}"', html)

    def test_cooler_detail_page_has_rent_action(self):
        detail_url = reverse('cooler_detail', kwargs={'pk': self.cooler.pk})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        rent_url = reverse('rent_cooler', kwargs={'pk': self.cooler.pk})
        self.assertIn(f'href="{rent_url}"', html)
        self.assertIn('Оформить аренду', html)

    def test_product_detail_cooler_redirects_to_cooler_detail(self):
        # Product with kind=cooler should redirect to cooler_detail
        self.cooler_product.name = f"Кулер {self.cooler.name}"
        self.cooler_product.save()
        response = self.client.get(reverse('product_detail', kwargs={'pk': self.cooler_product.pk}))
        self.assertRedirects(response, reverse('cooler_detail', kwargs={'pk': self.cooler.pk}))

    def test_product_detail_water_has_no_cooler_breadcrumb(self):
        response = self.client.get(reverse('product_detail', kwargs={'pk': self.water_product.pk}))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Каталог воды', html)
        self.assertNotIn('kind=cooler', html)
        self.assertNotIn('КУЛЕРЫ', html)

    def test_css_tokens_and_blue_headings_removed(self):
        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Check .wire-hero-label has color var(--color-navy)
        self.assertIn('.wire-hero-label {', css)
        self.assertNotIn('.wire-hero-label {\n  font-size: 12px;\n  letter-spacing: 0.8px;\n  color: var(--color-primary);', css)

        # Check .wire-btn-cooler is defined with navy background
        self.assertIn('.wire-btn-cooler', css)
        self.assertIn('background: var(--color-navy);', css)


class Task81RequirementsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='ivanov',
            email='ivanov@example.com',
            password='secretpassword123'
        )
        self.water = Product.objects.create(
            name='Вода Артезианская 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=350,
            stock=15,
            is_active=True,
        )

    def test_requirement_1_micro_headings_removed_from_pages(self):
        # Home page
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('ДОСТАВКА ПИТЬЕВОЙ ВОДЫ И АРЕНДА КУЛЕРОВ', html)
        self.assertNotIn('ВЫБИРАЙТЕ', html)
        self.assertNotIn('class="wire-hero-label"', html)
        self.assertNotIn('class="wire-section-label"', html)

        # Catalog page
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('class="wire-section-label"', html)
        self.assertNotIn('КАТАЛОГ ВОДЫ', html)

        # Coolers page
        response = self.client.get(reverse('coolers'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('class="wire-section-label"', html)
        self.assertNotIn('АРЕНДА ОБОРУДОВАНИЯ', html)

        # CSS has display: none for micro headings
        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.wire-hero-label {\n  display: none !important;', css)
        self.assertIn('.wire-section-label {\n  display: none !important;', css)

    def test_requirement_2_login_label_and_email_auth(self):
        # Check login page UI
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Логин или почта', html)
        self.assertNotIn('АВТОРИЗАЦИЯ', html)
        self.assertNotIn('class="wire-section-label"', html)

        # Login with username
        login_res = self.client.post(reverse('login'), {
            'username': 'ivanov',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        # Login with email
        login_res = self.client.post(reverse('login'), {
            'username': 'ivanov@example.com',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        # Login with email uppercase
        login_res = self.client.post(reverse('login'), {
            'username': 'IVANOV@EXAMPLE.COM',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        # Login with whitespace-padded email
        login_res = self.client.post(reverse('login'), {
            'username': '  ivanov@example.com  ',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        # Multi-user candidate resolution: inactive user should not shadow active user with shared email
        UserModel = get_user_model()
        shadow_user = UserModel.objects.create_user(
            username='shadow_user',
            email='shared_alias@example.com',
            password='shadowpass',
            is_active=False
        )
        active_user = UserModel.objects.create_user(
            username='active_user',
            email='shared_alias@example.com',
            password='activepass123'
        )
        login_shared = self.client.post(reverse('login'), {
            'username': 'shared_alias@example.com',
            'password': 'activepass123',
        })
        self.assertEqual(login_shared.status_code, 302)
        self.client.logout()

        # Login with wrong password
        login_res = self.client.post(reverse('login'), {
            'username': 'ivanov@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(login_res.status_code, 200)

    def test_requirement_3_water_card_buy_button_links_to_product_detail(self):
        # Catalog page: Buy button links to product_detail when in stock
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        detail_url = reverse('product_detail', kwargs={'pk': self.water.pk})
        self.assertIn(f'class="wire-card-btn" href="{detail_url}">Купить</a>', html)

        # Catalog page: Buy button links to product_detail even when stock is 0
        oos_water = Product.objects.create(
            name='Вода Горная Тестовая 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=400,
            stock=0,
            is_active=True,
        )
        response_oos = self.client.get(reverse('catalog'))
        html_oos = response_oos.content.decode('utf-8')
        oos_detail_url = reverse('product_detail', kwargs={'pk': oos_water.pk})
        self.assertIn(f'class="wire-card-btn" href="{oos_detail_url}">Купить</a>', html_oos)

        # Home page: Buy button links to product_detail
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn(f'href="{detail_url}"', html)

    def test_requirement_4_cart_redesign(self):
        # Add item to cart session
        session = self.client.session
        session['cart'] = {str(self.water.pk): 2}
        session.save()

        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        # Check UI components
        self.assertIn('wire-cart-layout', html)
        self.assertIn('wire-table-card', html)
        self.assertIn('wire-cart-table', html)
        self.assertIn('wire-checkout-box', html)
        self.assertIn('Вода Артезианская 19 л', html)
        self.assertIn('700', html)  # 350 * 2
        self.assertIn(reverse('checkout'), html)

        # Update quantity via POST
        update_res = self.client.post(reverse('cart_update', kwargs={'pk': self.water.pk}), {'quantity': 3})
        self.assertRedirects(update_res, reverse('cart'))
        self.assertEqual(self.client.session['cart'][str(self.water.pk)], 3)

        # Remove item by setting quantity 0
        del_res = self.client.post(reverse('cart_update', kwargs={'pk': self.water.pk}), {'quantity': 0})
        self.assertRedirects(del_res, reverse('cart'))
        self.assertNotIn(str(self.water.pk), self.client.session['cart'])

        # Empty cart view
        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('wire-empty-state-box', html)
        self.assertIn('В корзине пока пусто', html)

        # Mobile responsiveness CSS checks
        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('@media (max-width: 640px) {', css)
        self.assertIn('.wire-cart-table th,', css)

    def test_requirement_5_delivery_info_no_hover(self):
        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Check wire-card-static is defined and prevents transform / hover effects
        self.assertIn('.wire-card-static,', css)
        self.assertIn('.wire-card-static:hover {', css)
        self.assertIn('transform: none !important;', css)
        self.assertIn('cursor: default !important;', css)
        self.assertIn('.wire-card-static *,', css)

        # Check template order_detail.html has wire-card-static
        template_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'app', 'order_detail.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            tmpl = f.read()
        self.assertIn('wire-card wire-card-static', tmpl)
        self.assertIn('Информация о доставке', tmpl)
