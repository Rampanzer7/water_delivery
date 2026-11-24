import os
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.urls import reverse
from app.models import Product, Cooler

User = get_user_model()


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


class Lesson9RequirementsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = get_user_model().objects.create_user(
            username='lesson9user',
            email='lesson9@example.com',
            password='testpassword123'
        )
        self.water = Product.objects.create(
            name='Вода Байкальская 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=420,
            deposit_price=350,
            stock=25,
            is_active=True,
            description='Глубинная природная вода из озера Байкал.',
            search_text='вода байкальская 19 л глубинная природная вода из озера байкал',
        )
        self.water_empty = Product.objects.create(
            name='Вода Дефицитная 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=500,
            deposit_price=350,
            stock=0,
            is_active=True,
            description='Вода временно отсутствует на складе.',
            search_text='вода дефицитная 19 л',
        )
        self.cooler = Cooler.objects.create(
            name='Кулер Напольный Эко',
            description='Современный компрессорный кулер',
            monthly_price=650,
            deposit=1500,
            quantity=5,
        )

    def test_json_api_search_empty_query(self):
        response = self.client.get(reverse('api_search'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['results'], [])

    def test_json_api_search_matches_products_and_coolers(self):
        # Search for water
        res_water = self.client.get(reverse('api_search'), {'q': 'байкал'})
        self.assertEqual(res_water.status_code, 200)
        data_water = res_water.json()
        self.assertGreaterEqual(data_water['count'], 1)
        found_names = [item['name'] for item in data_water['results']]
        self.assertIn('Вода Байкальская 19 л', found_names)
        item = data_water['results'][0]
        self.assertEqual(item['type'], 'water')
        self.assertTrue(item['in_stock'])
        self.assertIn('price', item)
        self.assertIn('url', item)

        # Search for cooler
        res_cooler = self.client.get(reverse('api_search'), {'q': 'эко'})
        self.assertEqual(res_cooler.status_code, 200)
        data_cooler = res_cooler.json()
        self.assertGreaterEqual(data_cooler['count'], 1)
        cooler_item = [x for x in data_cooler['results'] if x['type'] == 'cooler'][0]
        self.assertEqual(cooler_item['name'], 'Кулер Напольный Эко')
        self.assertEqual(cooler_item['url'], reverse('cooler_detail', kwargs={'pk': self.cooler.pk}))

    def test_json_api_quickview_success_and_404(self):
        # Successful quickview
        res = self.client.get(reverse('api_quickview', kwargs={'pk': self.water.pk}))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['id'], self.water.pk)
        self.assertEqual(data['name'], 'Вода Байкальская 19 л')
        self.assertEqual(data['stock'], 25)
        self.assertTrue(data['in_stock'])
        self.assertEqual(data['deposit_price'], '350.00')
        self.assertIn('Глубинная природная вода', data['description'])
        self.assertEqual(data['url'], reverse('product_detail', kwargs={'pk': self.water.pk}))
        self.assertEqual(data['add_cart_url'], reverse('cart_add', kwargs={'pk': self.water.pk}))

        # 404 on missing product
        res_missing = self.client.get(reverse('api_quickview', kwargs={'pk': 999999}))
        self.assertEqual(res_missing.status_code, 404)

    def test_ajax_cart_add_json_response(self):
        # Adding in-stock item via AJAX
        res = self.client.post(
            reverse('cart_add', kwargs={'pk': self.water.pk}),
            {'quantity': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cart_count'], 2)
        self.assertIn('добавлена в корзину', data['message'])

        # Adding out-of-stock item via AJAX returns 400
        res_empty = self.client.post(
            reverse('cart_add', kwargs={'pk': self.water_empty.pk}),
            {'quantity': 1},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(res_empty.status_code, 400)
        data_empty = res_empty.json()
        self.assertFalse(data_empty['success'])
        self.assertIn('нет на складе', data_empty['error'])

    def test_anonymous_user_csrf_and_cart_badge_persistence(self):
        # Verify anonymous visitor receives CSRF token in base template
        anon_client = Client(enforce_csrf_checks=True)
        res_cat = anon_client.get(reverse('catalog'))
        self.assertEqual(res_cat.status_code, 200)
        html_cat = res_cat.content.decode('utf-8')
        self.assertIn('name="csrfmiddlewaretoken"', html_cat)

        # Extract CSRF token from page
        import re
        csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html_cat)
        self.assertIsNotNone(csrf_match)
        csrf_token = csrf_match.group(1)

        # Perform AJAX cart add with the token
        res_add = anon_client.post(
            reverse('cart_add', kwargs={'pk': self.water.pk}),
            {'quantity': 3, 'csrfmiddlewaretoken': csrf_token},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(res_add.status_code, 200)
        data_add = res_add.json()
        self.assertEqual(data_add['cart_count'], 3)

        # Verify header button now displays "Заказать (3)" upon page reload
        res_reload = anon_client.get(reverse('catalog'))
        self.assertEqual(res_reload.status_code, 200)
        html_reload = res_reload.content.decode('utf-8')
        self.assertIn('Заказать (3)', html_reload)

    def test_server_side_forms_validation(self):
        from app.forms import CoolerForm, DeliveryScheduleForm, ProductForm, RegisterForm
        from django.utils import timezone

        # 1. RegisterForm duplicate email validation
        form_reg = RegisterForm(data={
            'username': 'newuser',
            'email': 'lesson9@example.com',
            'phone': '+7 999 111-22-33',
            'password': 'password123',
        })
        self.assertFalse(form_reg.is_valid())
        self.assertIn('email', form_reg.errors)

        # 2. ProductForm price <= 0 validation
        form_prod = ProductForm(data={
            'name': 'Неправильная вода',
            'kind': Product.WATER,
            'volume': '19.0',
            'price': '-50',
            'stock': '10',
        })
        self.assertFalse(form_prod.is_valid())
        self.assertIn('price', form_prod.errors)

        # 3. CoolerForm monthly_price <= 0 validation
        form_cooler = CoolerForm(data={
            'name': 'Тестовый кулер',
            'monthly_price': '0',
            'deposit': '500',
            'quantity': '2',
        })
        self.assertFalse(form_cooler.is_valid())
        self.assertIn('monthly_price', form_cooler.errors)

        # 4. DeliveryScheduleForm quantity range validation
        form_sched = DeliveryScheduleForm(data={
            'quantity': '0',
            'weekday': '1',
        })
        self.assertFalse(form_sched.is_valid())
        self.assertIn('quantity', form_sched.errors)

    def test_client_side_validation_script_and_markup(self):
        # Check validation.js static asset exists and contains necessary checks
        val_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'js', 'validation.js')
        self.assertTrue(os.path.exists(val_path))
        with open(val_path, 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('EMAIL_REGEX', js)
        self.assertIn('PHONE_REGEX', js)
        self.assertIn('is-invalid', js)
        self.assertIn('wire-client-error', js)
        self.assertIn('Нельзя выбрать прошедшую дату', js)

        # Check interactive.js static asset exists and contains live search, modal and toast
        inter_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'js', 'interactive.js')
        self.assertTrue(os.path.exists(inter_path))
        with open(inter_path, 'r', encoding='utf-8') as f:
            ijs = f.read()
        self.assertIn('/api/search/', ijs)
        self.assertIn('/api/quickview/', ijs)
        self.assertIn('wire-modal', ijs)
        self.assertIn('wire-toast', ijs)
        self.assertIn('wire-spinner', ijs)
        self.assertIn('X-CSRFToken', ijs)

        # Check checkout.js loading indicators and mobile summary update
        chk_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'js', 'checkout.js')
        with open(chk_path, 'r', encoding='utf-8') as f:
            cjs = f.read()
        self.assertIn('wire-is-loading', cjs)
        self.assertIn('Загрузка доступных интервалов', cjs)
        self.assertIn('sum-total-mobile', cjs)

        # Check base.html includes title, script tags and global CSRF token
        base_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'base.html')
        with open(base_path, 'r', encoding='utf-8') as f:
            base_html = f.read()
        self.assertIn('<title>', base_html)
        self.assertIn('validation.js', base_html)
        self.assertIn('interactive.js', base_html)
        self.assertIn('wireCsrfHolder', base_html)
        self.assertIn('cart_count', base_html)

        # Check style.css includes Lesson 9 classes
        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.wire-client-error', css)
        self.assertIn('.wire-spinner', css)
        self.assertIn('.wire-search-dropdown', css)
        self.assertIn('.wire-modal', css)
        self.assertIn('.wire-toast', css)


class Lesson13TestScenarios(TestCase):
    """
    Тест-кейсы практического занятия 13 (Разработка тестового сценария проекта).
    Покрытие функциональных требований FR-01 - FR-20, позитивные и негативные сценарии.
    """
    def setUp(self):
        from datetime import time
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group
        from app.models import (
            Address, ContainerBalance, Cooler, DeliverySlot, District,
            Order, Product, Profile
        )
        from app.permissions import DRIVER_GROUP, DISPATCHER_GROUP

        User = get_user_model()
        self.client = Client()
        self.driver_group, _ = Group.objects.get_or_create(name=DRIVER_GROUP)
        self.dispatcher_group, _ = Group.objects.get_or_create(name=DISPATCHER_GROUP)

        # 1. Тестовые учетные записи
        self.admin = User.objects.create_superuser('admin_t13', 'admin_t13@example.com', 'pass12345')
        self.dispatcher = User.objects.create_user('dispatcher_t13', 'disp_t13@example.com', 'pass12345')
        self.dispatcher.groups.add(self.dispatcher_group)

        self.driver = User.objects.create_user('driver_t13', 'driver_t13@example.com', 'pass12345')
        self.driver.groups.add(self.driver_group)

        self.client_user = User.objects.create_user('client_t13', 'client_t13@example.com', 'pass12345')
        self.profile = Profile.objects.create(user=self.client_user, phone='+79001112233')
        self.balance = ContainerBalance.objects.create(user=self.client_user, bottles=3)

        # 2. Район и интервал
        self.district = District.objects.create(name='Тестовый район')
        self.slot = DeliverySlot.objects.create(start=time(9, 0), end=time(12, 0))
        self.slot.districts.add(self.district)

        # 3. Адрес
        self.address = Address.objects.create(
            user=self.client_user,
            district=self.district,
            street='Ленина',
            house='10',
            flat='5'
        )

        # 4. Товар вода 19 л
        self.water = Product.objects.create(
            name='Вода Горная Тестовая 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=280.00,
            deposit_price=300.00,
            stock=50,
            is_active=True,
            description='Чистая горная природная вода 19 л'
        )

        # 5. Кулер
        self.cooler = Cooler.objects.create(
            name='Кулер Настольный T13',
            description='Кулер с нагревом и охлаждением',
            monthly_price=450.00,
            deposit=2000.00,
            quantity=5
        )

    def test_tc01_catalog_water_display(self):
        """TC-01 (FR-01, Позитивный, High): Отображение каталога питьевой воды 19 л."""
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.water, response.context['page'].object_list)
        self.assertEqual(self.water.kind, Product.WATER)
        self.assertContains(response, '280')
        self.assertContains(response, 'Купить')

    def test_tc02_product_detail_deposit(self):
        """TC-02 (FR-02, Позитивный, High): Карточка товара с залогом тары и описанием."""
        response = self.client.get(reverse('product_detail', kwargs={'pk': self.water.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['product'].deposit_price, 300.00)
        self.assertContains(response, '300')
        self.assertContains(response, 'В наличии')
        self.assertContains(response, 'Чистая горная природная вода')

    def test_tc03_catalog_filters(self):
        """TC-03 (FR-03, Позитивный, High): Фильтрация по цене и наличию."""
        expensive_water = Product.objects.create(
            name='Вода Премиум Экстра 19 л',
            kind=Product.WATER,
            volume=19.0,
            price=450.00,
            deposit_price=300.00,
            stock=10,
            is_active=True,
            description='Дорогая вода вне диапазона фильтра'
        )
        response = self.client.get(reverse('catalog'), {'price_min': 200, 'price_max': 300, 'available': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.water, response.context['page'].object_list)
        self.assertNotIn(expensive_water, response.context['page'].object_list)

    def test_tc04_negative_registration_validation(self):
        """TC-04 (FR-06, Негативный, High): Валидация некорректного email и пустого телефона."""
        from django.contrib.auth import get_user_model
        from app.forms import RegisterForm
        form = RegisterForm(data={
            'username': 'baduser13',
            'email': 'not-an-email',
            'phone': '',
            'password': 'p1'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('phone', form.errors)

        response = self.client.post(reverse('register'), {
            'username': 'baduser13',
            'email': 'not-an-email',
            'phone': '',
            'password': 'p1'
        })
        self.assertEqual(response.status_code, 200)
        User = get_user_model()
        self.assertFalse(User.objects.filter(username='baduser13').exists())

    def test_tc05_negative_authentication_wrong_password(self):
        """TC-05 (FR-06, Негативный, High): Отклонение входа с неверным паролем."""
        response = self.client.post(reverse('login'), {
            'username': 'client_t13',
            'password': 'WrongPassword999'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_tc06_positive_authentication_by_email(self):
        """TC-06 (FR-06, Позитивный, High): Аутентификация клиента по email."""
        response = self.client.post(reverse('login'), {
            'username': 'client_t13@example.com',
            'password': 'pass12345'
        })
        self.assertEqual(response.status_code, 302)
        self.client.logout()

    def test_tc07_cart_quantity_update(self):
        """TC-07 (FR-01, Позитивный, High): Обновление количества товара в корзине."""
        session = self.client.session
        session['cart'] = {str(self.water.pk): 2}
        session.save()
        response = self.client.post(reverse('cart_update', kwargs={'pk': self.water.pk}), {'quantity': 4})
        self.assertRedirects(response, reverse('cart'))
        self.assertEqual(self.client.session['cart'][str(self.water.pk)], 4)

    def test_tc08_negative_search_xss_escaped(self):
        """TC-08 (FR-03, Негативный, Medium): Поиск несуществующего товара и экранирование XSS."""
        xss_query = '<script>alert("xss")</script>AbraKadabra999'
        response = self.client.get(reverse('catalog'), {'q': xss_query})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<script>alert', response.content.decode('utf-8'))
        self.assertEqual(len(response.context['page'].object_list), 0)

    def test_tc09_api_quickview(self):
        """TC-09 (FR-02, Позитивный, High): JSON API быстрого просмотра."""
        response = self.client.get(reverse('api_quickview', kwargs={'pk': self.water.pk}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.water.pk)
        self.assertEqual(data['name'], self.water.name)
        self.assertEqual(data['deposit_price'], '300.00')

    def test_tc10_negative_order_checkout_past_date(self):
        """TC-10 (FR-09, Негативный, High): Запрет оформления на прошедшую дату."""
        from datetime import timedelta
        from django.utils import timezone
        from app.forms import OrderForm
        from app.models import Order
        yesterday = timezone.localdate() - timedelta(days=1)
        form = OrderForm(
            data={
                'address': self.address.pk,
                'delivery_date': yesterday,
                'slot': self.slot.pk,
                'returned_bottles': 0
            },
            user=self.client_user,
            bottles_total=2
        )
        self.assertFalse(form.is_valid())
        self.assertIn('delivery_date', form.errors)

        self.client.force_login(self.client_user)
        session = self.client.session
        session['cart'] = {str(self.water.pk): 2}
        session.save()
        response = self.client.post(reverse('checkout'), {
            'address': self.address.pk,
            'delivery_date': yesterday,
            'slot': self.slot.pk,
            'returned_bottles': 0
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.client_user, delivery_date=yesterday).exists())

    def test_tc11_negative_order_checkout_negative_bottles(self):
        """TC-11 (FR-10, FR-16, Негативный, High): Запрет ввода некорректного количества сдаваемой тары."""
        from datetime import timedelta
        from django.utils import timezone
        from app.forms import OrderForm
        from app.models import Order
        tomorrow = timezone.localdate() + timedelta(days=1)

        # 1. Отрицательное число бутылей
        form_neg = OrderForm(
            data={
                'address': self.address.pk,
                'delivery_date': tomorrow,
                'slot': self.slot.pk,
                'returned_bottles': -5
            },
            user=self.client_user,
            bottles_total=2
        )
        self.assertFalse(form_neg.is_valid())
        self.assertIn('returned_bottles', form_neg.errors)

        # 2. Превышение баланса тары клиента (у клиента 3 бут., заказано 2 бут., сдает 100)
        form_exceed = OrderForm(
            data={
                'address': self.address.pk,
                'delivery_date': tomorrow,
                'slot': self.slot.pk,
                'returned_bottles': 100
            },
            user=self.client_user,
            bottles_total=2
        )
        self.assertFalse(form_exceed.is_valid())
        self.assertIn('returned_bottles', form_exceed.errors)

        # 3. HTTP POST отклонение
        self.client.force_login(self.client_user)
        session = self.client.session
        session['cart'] = {str(self.water.pk): 2}
        session.save()
        response = self.client.post(reverse('checkout'), {
            'address': self.address.pk,
            'delivery_date': tomorrow,
            'slot': self.slot.pk,
            'returned_bottles': -5
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.filter(user=self.client_user, returned_bottles__lt=0).exists())

    def test_tc12_address_create(self):
        """TC-12 (FR-07, Позитивный, Medium): Создание адреса доставки в профиле клиента."""
        from app.models import Address
        self.client.force_login(self.client_user)
        response = self.client.post(reverse('address_create'), {
            'district': self.district.pk,
            'street': 'Победы',
            'house': '15',
            'flat': '42',
            'comment': 'Домофон 42'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Address.objects.filter(user=self.client_user, street='Победы').exists())

    def test_tc13_checkout_order_creation_with_deposit(self):
        """TC-13 (FR-08, FR-10, FR-12, FR-33, Позитивный, High): Оформление заказа со спецификацией OrderItem и расчетом залога."""
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone
        from app.models import Order
        self.client.force_login(self.client_user)
        session = self.client.session
        session['cart'] = {str(self.water.pk): 3}
        session.save()
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = self.client.post(reverse('checkout'), {
            'address': self.address.pk,
            'delivery_date': tomorrow,
            'slot': self.slot.pk,
            'returned_bottles': 1
        })
        self.assertEqual(response.status_code, 302)
        order = Order.objects.filter(user=self.client_user).order_by('-id').first()
        self.assertIsNotNone(order)
        # 3 заказано, 1 сдана -> 2 недостающие * 300 = 600 залог
        # Для первого заказа клиента применяется скидка 10% на товары: 840 * 0.9 = 756.00 ₽
        self.assertEqual(order.deposit_total, Decimal('600.00'))
        self.assertEqual(order.goods_total, Decimal('756.00'))
        self.assertEqual(order.total, Decimal('1356.00'))

        # Проверка спецификации товаров FR-10 (OrderItem)
        items = order.items.all()
        self.assertEqual(items.count(), 1)
        item = items.first()
        self.assertEqual(item.product, self.water)
        self.assertEqual(item.quantity, 3)
        self.assertEqual(item.price, Decimal(str(self.water.price)))

    def test_tc14_negative_sanitation_file_upload(self):
        """TC-14 (FR-21, FR-30, Негативный, Medium): Запрет загрузки невалидных файлов (EXE, скрипты, превышение 2 МБ)."""
        from datetime import timedelta
        from django.utils import timezone
        from django.core.files.uploadedfile import SimpleUploadedFile
        from app.forms import SanitationForm
        from app.validators import validate_image
        from django.core.exceptions import ValidationError

        # 1. Запрещенное расширение (.exe)
        bad_file = SimpleUploadedFile('script.exe', b'MZ12345', content_type='application/x-msdownload')
        form = SanitationForm(
            data={'desired_date': timezone.localdate() + timedelta(days=2), 'comment': 'Обработка'},
            files={'photo': bad_file}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('photo', form.errors)

        # 2. Поддельный файл с расширением .jpg, но вредоносным содержимым (HTML/XSS)
        spoofed_file = SimpleUploadedFile('fake.jpg', b'<script>alert("hack")</script>', content_type='image/jpeg')
        with self.assertRaises(ValidationError) as ctx:
            validate_image(spoofed_file)
        self.assertIn('Содержимое файла не похоже на изображение', str(ctx.exception))

        # 3. Превышение максимального размера (3.17 МБ > 2 МБ)
        big_payload = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00' + b'0' * (3 * 1024 * 1024)
        big_file = SimpleUploadedFile('oversized.jpg', big_payload, content_type='image/jpeg')
        with self.assertRaises(ValidationError) as ctx2:
            validate_image(big_file)
        self.assertIn('не должен превышать 2 МБ', str(ctx2.exception))

    def test_tc15_courier_close_delivery_balance_update(self):
        """TC-15 (FR-14, FR-15, Позитивный, High): Закрытие доставки курьером и пересчет тары."""
        from django.utils import timezone
        from app.models import Order, RouteSheet
        from app.services import close_delivery
        order = Order.objects.create(
            user=self.client_user,
            address=self.address,
            slot=self.slot,
            delivery_date=timezone.localdate(),
            bottles_total=2,
            returned_bottles=2,
            total=560,
            status=Order.ASSIGNED
        )
        sheet = RouteSheet.objects.create(driver=self.driver, date=timezone.localdate())
        order.route_sheet = sheet
        order.save()
        initial_balance = self.balance.bottles
        closed = close_delivery(order.pk, returned_bottles=2)
        self.assertEqual(closed.status, Order.DELIVERED)
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.bottles, initial_balance + order.bottles_total - 2)

    def test_tc16_negative_anonymous_access_courier(self):
        """TC-16 (FR-22, Негативный, High): Запрет неавторизованного и неролевого доступа к закрытию доставки."""
        from django.utils import timezone
        from app.models import Order
        order = Order.objects.create(
            user=self.client_user,
            address=self.address,
            slot=self.slot,
            delivery_date=timezone.localdate(),
            bottles_total=2,
            total=560,
            status=Order.ASSIGNED
        )
        # 1. Анонимный доступ -> редирект на вход
        self.client.logout()
        response_anon = self.client.get(reverse('courier_close_delivery', kwargs={'pk': order.pk}))
        self.assertEqual(response_anon.status_code, 302)
        self.assertIn('/accounts/login/', response_anon.url)

        # 2. Доступ от обычного клиента (не водителя) -> 403 Forbidden
        self.client.force_login(self.client_user)
        response_client = self.client.get(reverse('courier_close_delivery', kwargs={'pk': order.pk}))
        self.assertEqual(response_client.status_code, 403)

    def test_tc17_coolers_catalog_display(self):
        """TC-17 (FR-05, Позитивный, Medium): Каталог кулеров с ценой аренды и залогом."""
        response = self.client.get(reverse('coolers'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.cooler, response.context['coolers'])
        self.assertContains(response, '450')

    def test_tc18_cooler_rent_creation(self):
        """TC-18 (FR-17, FR-18, Позитивный, Medium): Оформление аренды кулера."""
        from datetime import timedelta
        from django.utils import timezone
        from app.models import Rental
        self.client.force_login(self.client_user)
        tomorrow = timezone.localdate() + timedelta(days=1)
        response = self.client.post(reverse('rent_cooler', kwargs={'pk': self.cooler.pk}), {
            'address': self.address.pk,
            'start_date': tomorrow
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Rental.objects.filter(user=self.client_user, cooler=self.cooler).exists())

    def test_tc19_negative_rental_out_of_stock(self):
        """TC-19 (FR-05, FR-17, Негативный, Medium): Кулер с остатком 0 недоступен для аренды."""
        from app.models import Cooler
        empty_cooler = Cooler.objects.create(name='Кулер Дефицитный', monthly_price=500, deposit=1000, quantity=0)
        response = self.client.get(reverse('cooler_detail', kwargs={'pk': empty_cooler.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Нет в наличии')

    def test_tc20_route_sheet_csv_export(self):
        """TC-20 (FR-13, FR-25, Позитивный, Medium): Экспорт маршрутного листа в CSV."""
        from django.utils import timezone
        from app.models import RouteSheet
        self.client.force_login(self.dispatcher)
        sheet = RouteSheet.objects.create(driver=self.driver, date=timezone.localdate())
        response = self.client.get(reverse('route_csv', kwargs={'pk': sheet.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])


class Lesson14RetestDefectScenarios(TestCase):
    """
    Автоматизированная верификация исправлений дефектов Занятия 14 (Ручное тестирование).
    Проверка устранения BUG-01, BUG-02, BUG-03, BUG-04, BUG-05, BUG-06, BUG-08.
    """
    def setUp(self):
        User = get_user_model()
        from app.models import ContainerBalance, District, Address, DeliverySlot
        from decimal import Decimal
        self.client = Client()
        self.client_user = User.objects.create_user(username='retest_client', password='demo12345', email='retest@example.com')
        self.balance = ContainerBalance.objects.create(user=self.client_user, bottles=5)
        self.district = District.objects.create(name='Тестовый район')
        self.address = Address.objects.create(user=self.client_user, district=self.district, street='Ленина', house='10', flat='5')
        self.slot = DeliverySlot.objects.create(start='10:00', end='14:00')
        self.slot.districts.add(self.district)
        self.water = Product.objects.create(
            name='Вода «Артезианская» 19 л',
            kind=Product.WATER,
            price=Decimal('350.00'),
            deposit_price=Decimal('300.00'),
            stock=100
        )

    def test_bug01_retest_deposit_rate_300(self):
        """BUG-01 (Retest, Critical): Ставка залога тары в ЛК и на /cabinet/balance/ равна 300 ₽ (1500 ₽ за 5 бутылей)."""
        self.client.force_login(self.client_user)
        response = self.client.get(reverse('cabinet_balance'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['deposit_sum'], Decimal('1500.00'))
        self.assertContains(response, '1500')
        self.assertNotContains(response, '1750')
        self.assertContains(response, '300')

    def test_bug02_retest_api_calc_first_order_discount(self):
        """BUG-02 (Retest, Critical): Динамический расчет /api/calc/ сохраняет 10% скидку для нового клиента."""
        User = get_user_model()
        from app.models import ContainerBalance
        new_client = User.objects.create_user(username='new_client_lab14', password='demo12345', email='new14@example.com')
        ContainerBalance.objects.create(user=new_client, bottles=0)
        self.client.force_login(new_client)
        session = self.client.session
        session['cart'] = {str(self.water.pk): 2}
        session.save()
        # 2 бутыли по 350 = 700 ₽. Скидка 10% = 70 ₽ -> товары 630 ₽. Залог 2*300 = 600 ₽. Итого 1230 ₽.
        response = self.client.get(reverse('api_calc') + '?returned=0')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(Decimal(data['goods']), Decimal('630.00'))
        self.assertEqual(Decimal(data['discount_amount']), Decimal('70.00'))
        self.assertEqual(data['discount_percent'], 10)
        self.assertEqual(Decimal(data['total']), Decimal('1230.00'))

    def test_bug03_retest_cart_add_negative_rejected(self):
        """BUG-03 (Retest, Blocker): Запрет добавления отрицательного количества товара в корзину."""
        response = self.client.post(
            reverse('cart_add', kwargs={'pk': self.water.pk}),
            {'quantity': '-5'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('не менее 1 шт', response.json().get('error', ''))

    def test_bug04_retest_order_form_max_14_days(self):
        """BUG-04 (Retest, Major): Валидация горизонта даты доставки не более 14 дней в OrderForm."""
        from datetime import timedelta
        from django.utils import timezone
        from app.forms import OrderForm

        # Дата через 15 дней должна быть отклонена
        too_late = timezone.localdate() + timedelta(days=15)
        form = OrderForm(data={
            'address': self.address.pk,
            'slot': self.slot.pk,
            'delivery_date': too_late,
            'returned_bottles': 0,
        }, user=self.client_user, bottles_total=2)
        self.assertFalse(form.is_valid())
        self.assertIn('delivery_date', form.errors)
        self.assertIn('не может быть позже 14 дней', str(form.errors['delivery_date']))

        # Дата через 5 дней должна пройти успешно
        valid_date = timezone.localdate() + timedelta(days=5)
        form_ok = OrderForm(data={
            'address': self.address.pk,
            'slot': self.slot.pk,
            'delivery_date': valid_date,
            'returned_bottles': 0,
        }, user=self.client_user, bottles_total=2)
        self.assertTrue(form_ok.is_valid())

    def test_bug05_retest_mobile_comment_field_present(self):
        """BUG-05 (Retest, Major): Поле комментария доступно в разметке без класса desktop-only."""
        from django.conf import settings
        template_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'app', 'checkout.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        self.assertNotIn('<div class="wire-form-row desktop-only">\n            <label for="id_comment"', html)
        self.assertIn('id="id_comment"', html)

    def test_bug06_retest_checkout_summary_discount_row(self):
        """BUG-06 (Retest, Minor): В сводке заказа checkout.html присутствует строка скидки #row-discount."""
        from django.conf import settings
        template_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'app', 'checkout.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        self.assertIn('id="row-discount"', html)
        self.assertIn('Скидка на 1-й заказ', html)

    def test_bug08_retest_footer_brand_copyright(self):
        """BUG-08 (Retest, Trivial/High): Подвал сайта содержит юридически корректное наименование ООО «Святой Источник»."""
        from django.conf import settings
        base_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'base.html')
        with open(base_path, 'r', encoding='utf-8') as f:
            html = f.read()
        self.assertIn('ООО «Святой Источник»', html)
        self.assertIn('Все права защищены', html)

    def test_bug07_retest_route_sheet_csv_export_empty_and_staff_url(self):
        """BUG-07 (Retest, Critical/Low): Корректный экспорт пустого маршрутного листа в CSV по путям /routes/ и /staff/routes/."""
        from django.utils import timezone
        from django.contrib.auth.models import Group
        from app.models import RouteSheet
        dispatcher = get_user_model().objects.create_user(username='disp_retest14', password='demo12345', is_staff=True)
        disp_group, _ = Group.objects.get_or_create(name='Оператор')
        dispatcher.groups.add(disp_group)
        self.client.force_login(dispatcher)

        sheet = RouteSheet.objects.create(driver=dispatcher, date=timezone.localdate())
        # Проверка стандартного URL
        res1 = self.client.get(reverse('route_csv', kwargs={'pk': sheet.pk}))
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1['Content-Type'], 'text/csv; charset=utf-8')
        content1 = res1.content.decode('utf-8-sig')
        self.assertIn('Заказ;Интервал;Адрес;Клиент;Телефон;Бутылей', content1)

        # Проверка URL в пространстве staff/routes/
        res2 = self.client.get(reverse('staff_route_csv', kwargs={'pk': sheet.pk}))
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2['Content-Type'], 'text/csv; charset=utf-8')
        content2 = res2.content.decode('utf-8-sig')
        self.assertIn('Заказ;Интервал;Адрес;Клиент;Телефон;Бутылей', content2)


class Lesson15FunctionalAndSecurityTests(TestCase):
    """
    Комплексный набор автотестов для Занятия 15:
    - 8 проверок безопасности (CSRF, XSS, SQLi, IDOR, пароли, конфигурация, загрузка файлов, брутфорс);
    - Функциональное тестирование на объёме данных (1000 записей, пагинация, перцентили NFR-01);
    - Матрица ролевого доступа RBAC (Гость, Клиент, Диспетчер, Курьер, Администратор).
    """

    def setUp(self):
        from decimal import Decimal
        from datetime import timedelta
        from django.utils import timezone
        from django.contrib.auth.models import Group, User
        from django.core.cache import cache
        from django.test import Client
        from app.permissions import DISPATCHER_GROUP, DRIVER_GROUP
        from app.models import District, DeliverySlot, Product, Address, Order, Cooler, Rental, ContainerBalance
        cache.clear()
        self.client_csrf = Client(enforce_csrf_checks=True)

        # Создание ролевых групп
        self.disp_group, _ = Group.objects.get_or_create(name=DISPATCHER_GROUP)
        self.driver_group, _ = Group.objects.get_or_create(name=DRIVER_GROUP)

        # Пользователи разных ролей
        self.user_a = User.objects.create_user(username='client_a', email='a@example.com', password='StrongPassword123!')
        self.user_b = User.objects.create_user(username='client_b', email='b@example.com', password='StrongPassword123!')
        self.operator = User.objects.create_user(username='dispatcher_15', email='disp@example.com', password='StrongPassword123!')
        self.operator.groups.add(self.disp_group)
        self.driver = User.objects.create_user(username='driver_15', email='driver@example.com', password='StrongPassword123!')
        self.driver.groups.add(self.driver_group)
        self.admin_user = User.objects.create_superuser(username='admin_15', email='admin@example.com', password='StrongPassword123!')

        # Базовые данные
        self.district = District.objects.create(name='Центральный район 15')
        self.slot = DeliverySlot.objects.create(start='10:00', end='12:00')
        self.slot.districts.add(self.district)
        self.water = Product.objects.create(
            name='Вода Архыз 19 л',
            kind=Product.WATER,
            price=Decimal('350.00'),
            volume=19.0,
            stock=100,
            is_active=True
        )
        self.address_a = Address.objects.create(user=self.user_a, district=self.district, street='Ленина', house='15', comment='Код 1234')
        self.address_b = Address.objects.create(user=self.user_b, district=self.district, street='Мира', house='20', comment='Офис 5')

        self.order_b = Order.objects.create(
            user=self.user_b,
            address=self.address_b,
            slot=self.slot,
            delivery_date=timezone.localdate() + timedelta(days=2),
            goods_total=Decimal('350.00'),
            deposit_total=Decimal('0.00'),
            bottles_total=1,
            returned_bottles=1,
            status=Order.NEW,
            comment='Секретный комментарий пользователя B'
        )

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()
        super().tearDown()

    def test_sec01_csrf_protection_rejects_missing_token(self):
        """Проверка 1 безопасности: CSRF — POST-запрос без токена отклоняется с кодом 403."""
        response = self.client_csrf.post(reverse('cart_add', kwargs={'pk': self.water.pk}), {'quantity': 2})
        self.assertEqual(response.status_code, 403)

    def test_sec02_xss_auto_escaping_in_comments_and_profile(self):
        """Проверка 2 безопасности: XSS — HTML-теги экранируются и выводятся как текст."""
        from app.models import Address
        self.client.force_login(self.user_a)
        xss_payload = '<script>alert("XSS-15")</script>'
        addr = Address.objects.create(user=self.user_a, district=self.district, street='Тестовая', house='1', comment=xss_payload)
        response = self.client.get(reverse('address_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '&lt;script&gt;alert(&quot;XSS-15&quot;)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert("XSS-15")</script>')

    def test_sec03_sqli_resistance_in_catalog_queries(self):
        """Проверка 3 безопасности: SQL-инъекция — параметр поиска экранируется ORM."""
        sqli_payload = "' OR 1=1 --"
        response = self.client.get(f"{reverse('catalog')}?q={sqli_payload}")
        self.assertEqual(response.status_code, 200)
        # Инъекция не должна возвращать все товары: совпадений с литералом нет
        self.assertEqual(len(response.context['page'].object_list), 0)
        self.assertContains(response, 'товаров не найдено')

    def test_sec04_idor_isolation_between_tenants_and_staff(self):
        """Проверка 4 безопасности: IDOR — клиент A не имеет доступа к заказу и адресу клиента B."""
        self.client.force_login(self.user_a)
        # Доступ к чужому заказу
        res_order = self.client.get(reverse('order_detail', kwargs={'pk': self.order_b.pk}))
        self.assertEqual(res_order.status_code, 403)

        # Попытка редактирования чужого адреса
        res_addr = self.client.get(reverse('address_edit', kwargs={'pk': self.address_b.pk}))
        self.assertEqual(res_addr.status_code, 403)

        # Попытка доступа обычного клиента в панель управления
        res_admin = self.client.get(reverse('manage_dashboard'))
        self.assertEqual(res_admin.status_code, 403)

    def test_sec05_password_storage_hashes_and_validators(self):
        """Проверка 5 безопасности: Хранение паролей — алгоритм PBKDF2 и валидация длины."""
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        # Проверка хеша в БД
        self.user_a.refresh_from_db()
        self.assertTrue(self.user_a.password.startswith('pbkdf2_sha256$'))

        # Проверка отклонения пароля короче 8 символов
        with self.assertRaises(ValidationError):
            validate_password('Short1!', user=self.user_a)

    def test_sec06_security_config_and_custom_error_pages(self):
        """Проверка 6 безопасности: Конфигурация — наличие кастомных страниц 403, 404, 500."""
        res_403 = self.client.get(reverse('custom_403'))
        self.assertEqual(res_403.status_code, 403)
        self.assertContains(res_403, 'Доступ ограничен', status_code=403)

        res_404 = self.client.get(reverse('custom_404'))
        self.assertEqual(res_404.status_code, 404)
        self.assertContains(res_404, 'Страница не найдена', status_code=404)

        res_500 = self.client.get(reverse('custom_500'))
        self.assertEqual(res_500.status_code, 500)
        self.assertContains(res_500, 'Внутренняя ошибка сервера', status_code=500)

    def test_sec07_file_upload_double_extension_and_structure_validation(self):
        """Проверка 7 безопасности: Загрузка файлов — блокировка двойных расширений, повреждённых файлов и подмены форматов."""
        import io
        from PIL import Image
        from app.validators import validate_image
        from django.core.exceptions import ValidationError
        from django.core.files.uploadedfile import SimpleUploadedFile

        # 1. Двойное расширение cooler.php.jpg
        double_ext_file = SimpleUploadedFile('cooler.php.jpg', b'\xff\xd8\xff\xe0\x00\x10JFIF\x00' + b'A' * 100, content_type='image/jpeg')
        with self.assertRaises(ValidationError) as ctx1:
            validate_image(double_ext_file)
        self.assertIn('двойными расширениями', str(ctx1.exception))

        # 2. Двойное расширение cooler.jsp.png
        jsp_file = SimpleUploadedFile('cooler.jsp.png', b'\x89PNG\r\n\x1a\n' + b'B' * 100, content_type='image/png')
        with self.assertRaises(ValidationError) as ctx_jsp:
            validate_image(jsp_file)
        self.assertIn('двойными расширениями', str(ctx_jsp.exception))

        # 3. Исполняемый файл .exe
        exe_file = SimpleUploadedFile('script.exe', b'MZ12345', content_type='application/x-msdownload')
        with self.assertRaises(ValidationError) as ctx2:
            validate_image(exe_file)
        self.assertIn('Допустимы только файлы JPG', str(ctx2.exception))

        # 4. Файл с поддельным заголовком, но разрушенной структурой
        fake_img = SimpleUploadedFile('fake.png', b'\x89PNG\r\n\x1a\n<?php eval($_GET["cmd"]); ?>', content_type='image/png')
        with self.assertRaises(ValidationError) as ctx3:
            validate_image(fake_img)
        self.assertIn('Содержимое файла не похоже на изображение', str(ctx3.exception))

        # 5. Подмена формата: валидный PNG-файл, сохранённый с расширением .jpg
        buf_png = io.BytesIO()
        im = Image.new('RGB', (10, 10), color='green')
        im.save(buf_png, format='PNG')
        mismatched_img = SimpleUploadedFile('spoofed_format.jpg', buf_png.getvalue(), content_type='image/jpeg')
        with self.assertRaises(ValidationError) as ctx4:
            validate_image(mismatched_img)
        self.assertIn('не соответствует расширению', str(ctx4.exception))

    def test_sec08_login_brute_force_rate_limiting(self):
        """Проверка 8 безопасности: Защита от перебора — блокировка после 5 неудачных попыток входа и запрет authenticate при блокировке."""
        login_url = reverse('login')
        # 5 неудачных попыток
        for i in range(5):
            res = self.client.post(login_url, {'username': 'client_a', 'password': f'WrongPass{i}'})
            self.assertEqual(res.status_code, 200)

        # 6-я попытка (даже с правильным паролем) должна быть заблокирована rate limiter'ом
        res_blocked = self.client.post(login_url, {'username': 'client_a', 'password': 'StrongPassword123!'})
        self.assertContains(res_blocked, 'Слишком много неудачных попыток входа')
        # Пользователь не должен быть авторизован в сессии
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_sec09_login_rate_limiting_ip_spoofing_defense(self):
        """Проверка безопасности: Защита от обхода rate limiting через подделку HTTP_X_FORWARDED_FOR."""
        login_url = reverse('login')
        # 1. Блокируем учетную запись client_a 5 неудачными попытками
        for i in range(5):
            self.client.post(login_url, {'username': 'client_a', 'password': f'WrongPass{i}'})

        # 2. Пытаемся обойти блокировку client_a, передавая поддельные заголовки X-Forwarded-For
        for i in range(3):
            res = self.client.post(
                login_url,
                {'username': 'client_a', 'password': 'StrongPassword123!'},
                HTTP_X_FORWARDED_FOR=f'10.20.{i}.1'
            )
            # Должен по-прежнему возвращаться отказ rate limiter'а (спуфинг не срабатывает)
            self.assertContains(res, 'Слишком много неудачных попыток входа')
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_sec10_login_rate_limiting_ip_spray_defense(self):
        """Проверка безопасности: Защита от распределенного перебора (IP Spray) — блокировка IP после 15 попыток."""
        from django.core.cache import cache
        cache.clear()
        login_url = reverse('login')
        # 15 неудачных попыток для разных логинов с одного IP
        for i in range(15):
            self.client.post(login_url, {'username': f'dummy_user_{i}', 'password': 'bad'})

        # 16-я попытка с новым логином с этого же IP должна быть заблокирована по IP
        res_ip_blocked = self.client.post(login_url, {'username': 'fresh_target_user', 'password': 'bad'})
        self.assertContains(res_ip_blocked, 'Слишком много неудачных попыток входа')
        cache.clear()

    def test_fn01_form_validation_and_required_fields(self):
        """Функциональное тестирование: Валидация форм и сохранение введённых данных."""
        self.client.force_login(self.user_a)
        # Отправка формы адреса без обязательного района
        response = self.client.post(reverse('address_create'), {
            'street': 'Новая',
            'house': '10',
            'comment': 'Домофон 55',
            'district': ''
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('district', response.context['form'].errors)
        # Сохранение введенных данных в полях
        self.assertContains(response, 'Новая')
        self.assertContains(response, 'Домофон 55')

    def test_fn02_catalog_volume_performance_1000_items_and_nfr01(self):
        """Функциональное тестирование на объёме: 1000 товаров, пагинация и соответствие NFR-01 (< 2.0 с)."""
        import time
        # Создаем 1000 записей товаров в каталоге
        bulk_waters = [
            Product(
                name=f'Вода Объемная №{i:04d}',
                kind=Product.WATER,
                price=Decimal('150.00') + Decimal(i % 50),
                volume=19.0 if i % 2 == 0 else 5.0,
                stock=50,
                is_active=True
            )
            for i in range(1, 1001)
        ]
        Product.objects.bulk_create(bulk_waters)
        self.assertGreaterEqual(Product.objects.count(), 1000)

        # 1. Замер времени ответа каталога (50 последовательных запросов)
        durations = []
        for _ in range(50):
            t0 = time.perf_counter()
            resp = self.client.get(reverse('catalog'))
            t1 = time.perf_counter()
            self.assertEqual(resp.status_code, 200)
            durations.append(t1 - t0)

        durations.sort()
        p95_index = int(0.95 * len(durations)) - 1
        p95_time = durations[p95_index]
        # Проверка нефункционального требования NFR-01 (<= 2.0 с)
        self.assertLess(p95_time, 2.0, f"95-й процентиль {p95_time:.4f} с превысил лимит 2.0 с")

        # 2. Последняя страница пагинации (50 товаров на страницу = 20)
        last_page = (Product.objects.filter(is_active=True, kind=Product.WATER).count() + 19) // 20
        res_last = self.client.get(f"{reverse('catalog')}?page={last_page}")
        self.assertEqual(res_last.status_code, 200)
        self.assertEqual(res_last.context['page'].number, last_page)

        # 3. Фильтр, под который ничего не попадает
        res_empty_filter = self.client.get(f"{reverse('catalog')}?price_min=999999")
        self.assertEqual(res_empty_filter.status_code, 200)
        self.assertEqual(len(res_empty_filter.context['page'].object_list), 0)

    def test_fn03_role_based_access_control_matrix(self):
        """Функциональное тестирование RBAC: Проверка матрицы прав доступа по ролям."""
        urls_roles_expected = [
            # Гость
            (None, reverse('home'), 200),
            (None, reverse('catalog'), 200),
            (None, reverse('cabinet'), 302),
            (None, reverse('manage_settings'), 302),
            # Клиент
            (self.user_a, reverse('cabinet'), 200),
            (self.user_a, reverse('operator_orders'), 403),
            (self.user_a, reverse('courier_deliveries'), 403),
            (self.user_a, reverse('manage_settings'), 403),
            # Диспетчер / Оператор
            (self.operator, reverse('operator_orders'), 200),
            (self.operator, reverse('manage_settings'), 403),
            # Курьер / Водитель
            (self.driver, reverse('courier_deliveries'), 200),
            (self.driver, reverse('operator_orders'), 403),
            # Администратор
            (self.admin_user, reverse('manage_settings'), 200),
            (self.admin_user, reverse('manage_products'), 200),
        ]

        for user, url, expected_status in urls_roles_expected:
            if user:
                self.client.force_login(user)
            else:
                self.client.logout()
            res = self.client.get(url)
            self.assertEqual(
                res.status_code, expected_status,
                f"Ошибка доступа: URL={url}, User={user.username if user else 'Guest'}, "
                f"Expected={expected_status}, Got={res.status_code}"
            )


class Lesson16ExceptionHandlingTests(TestCase):
    """
    Набор из 5 негативных тестов для Занятия 16 (Анализ и обеспечение обработки исключительных ситуаций):
    1. Обращение к несуществующей записи возвращает 404 (get_object_or_404 / Http404);
    2. Доступ без прав возвращает 403 (PermissionDenied / role_required);
    3. Форма с неверными данными не создаёт запись и показывает сообщения об ошибках на русском языке с сохранением полей;
    4. При ошибке в середине составной операции срабатывает откат транзакции (rollback) и данные не меняются;
    5. Расчёт показателей и агрегатов на пустой выборке не вызывает ZeroDivisionError и не падает.
    """

    def setUp(self):
        from decimal import Decimal
        from django.contrib.auth.models import Group, User
        from django.core.cache import cache
        from app.permissions import DISPATCHER_GROUP, DRIVER_GROUP
        from app.models import District, DeliverySlot, Product, Address, Order, ContainerBalance
        cache.clear()

        # Ролевые группы
        self.disp_group, _ = Group.objects.get_or_create(name=DISPATCHER_GROUP)
        self.driver_group, _ = Group.objects.get_or_create(name=DRIVER_GROUP)

        # Тестовые пользователи
        self.user_a = User.objects.create_user(username='client_neg_a', email='nega@example.com', password='NegPassword123!')
        self.user_b = User.objects.create_user(username='client_neg_b', email='negb@example.com', password='NegPassword123!')
        self.operator = User.objects.create_user(username='disp_neg', email='dispneg@example.com', password='NegPassword123!')
        self.operator.groups.add(self.disp_group)
        self.admin_user = User.objects.create_superuser(username='admin_neg', email='adminneg@example.com', password='NegPassword123!')

        # Балансы тары
        ContainerBalance.objects.create(user=self.user_a, bottles=5)
        ContainerBalance.objects.create(user=self.user_b, bottles=0)

        # Справочные данные
        self.district = District.objects.create(name='Заволжский район')
        self.slot = DeliverySlot.objects.create(start='09:00', end='13:00')
        self.slot.districts.add(self.district)

        # Каталог товаров
        self.water = Product.objects.create(
            name='Вода Святой Источник 19 л негатив',
            kind=Product.WATER,
            price=Decimal('280.00'),
            deposit_price=Decimal('350.00'),
            volume=19.0,
            stock=50,
            is_active=True
        )

        # Адрес клиента А
        self.address_a = Address.objects.create(
            user=self.user_a,
            district=self.district,
            street='Советская',
            house='14',
            flat='5',
            comment='Домофон 5В'
        )

    def test_neg01_nonexistent_record_returns_404(self):
        """Негативный тест 1: Обращение к несуществующей записи возвращает HTTP 404."""
        # 1. Запрос несуществующего товара по невалидному ID
        resp_product = self.client.get('/water/999999/')
        self.assertEqual(resp_product.status_code, 404)

        # 2. Запрос несуществующего заказа авторизованным клиентом
        self.client.force_login(self.user_a)
        resp_order = self.client.get(reverse('order_detail', kwargs={'pk': 999999}))
        self.assertEqual(resp_order.status_code, 404)

        # 3. Проверка фирменного шаблона 404.html со ссылками на главную и каталог/поиск
        resp_custom = self.client.get(reverse('custom_404'))
        self.assertEqual(resp_custom.status_code, 404)
        self.assertContains(resp_custom, '404', status_code=404)
        self.assertContains(resp_custom, 'Страница не найдена', status_code=404)
        self.assertContains(resp_custom, 'На главную', status_code=404)
        self.assertContains(resp_custom, 'В каталог и поиск', status_code=404)

    def test_neg02_unauthorized_access_returns_403(self):
        """Негативный тест 2: Доступ без прав возвращает HTTP 403 (Forbidden)."""
        # 1. Обычный клиент пытается открыть панель диспетчера
        self.client.force_login(self.user_a)
        resp_disp = self.client.get(reverse('operator_orders'))
        self.assertEqual(resp_disp.status_code, 403)

        # 2. Клиент пытается открыть страницу настроек администратора
        resp_admin = self.client.get(reverse('manage_settings'))
        self.assertEqual(resp_admin.status_code, 403)

        # 3. Проверка фирменного шаблона 403.html со ссылками на главную и каталог/поиск
        resp_custom_403 = self.client.get(reverse('custom_403'))
        self.assertEqual(resp_custom_403.status_code, 403)
        self.assertContains(resp_custom_403, '403', status_code=403)
        self.assertContains(resp_custom_403, 'Доступ ограничен', status_code=403)
        self.assertContains(resp_custom_403, 'На главную', status_code=403)
        self.assertContains(resp_custom_403, 'В каталог и поиск', status_code=403)

    def test_neg03_invalid_form_does_not_create_record_and_shows_error(self):
        """Негативный тест 3: Форма с неверными данными не создаёт запись и показывает ошибки на русском с сохранением значений."""
        from app.models import Address
        self.client.force_login(self.user_a)
        addr_count_before = Address.objects.count()

        # Отправляем форму адреса с заведомо некорректными данными (улица из 1 буквы, пустой дом, пустой район)
        resp = self.client.post(reverse('address_create'), {
            'street': 'У',
            'house': '',
            'flat': '12',
            'comment': 'Тестовый комментарий',
            'district': ''
        })

        # Запись в БД НЕ должна быть создана
        self.assertEqual(Address.objects.count(), addr_count_before)
        # Статус 200 — страница формы перерисована с ошибками
        self.assertEqual(resp.status_code, 200)
        form = resp.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('street', form.errors)
        self.assertIn('house', form.errors)
        self.assertIn('district', form.errors)

        # Проверка русскоязычных сообщений об ошибках
        self.assertContains(resp, 'Укажите корректное название улицы (не менее 2 символов).')
        self.assertContains(resp, 'Укажите номер дома или строения.')
        self.assertContains(resp, 'Пожалуйста, выберите район города из списка.')

        # Проверка сохранения введённых пользователем данных (field value preservation)
        self.assertContains(resp, 'value="У"')
        self.assertContains(resp, 'value="12"')
        self.assertContains(resp, 'Тестовый комментарий')

        # 2. Проверка метода clean_house на отсутствие цифры в номере дома
        resp_house = self.client.post(reverse('address_create'), {
            'street': 'Ленина',
            'house': 'без_номера',
            'flat': '12',
            'district': self.district.pk
        })
        self.assertEqual(Address.objects.count(), addr_count_before)
        self.assertContains(resp_house, 'Номер дома должен содержать хотя бы одну цифру (например: 10, 14к2 или 5А).')

        # 3. Проверка метода clean_returned_bottles в OrderForm на отрицательное значение
        from app.forms import OrderForm, DeliverySlotForm
        order_form = OrderForm({'returned_bottles': -5}, user=self.user_a, bottles_total=2)
        self.assertFalse(order_form.is_valid())
        self.assertIn('Количество возвращаемых бутылей не может быть отрицательным числом.', order_form.errors['returned_bottles'])

        # 4. Проверка метода DeliverySlotForm.clean на интервал start >= end
        slot_form = DeliverySlotForm({'start': '18:00', 'end': '10:00', 'districts': [self.district.pk]})
        self.assertFalse(slot_form.is_valid())
        self.assertIn('Время окончания интервала доставки должно быть строго позже времени начала.', slot_form.errors['end'])

    def test_neg04_transaction_rollback_on_mid_operation_failure(self):
        """Негативный тест 4: При ошибке в середине составной операции данные не меняются (откат транзакции rollback)."""
        from unittest.mock import patch
        from django.utils import timezone
        from app.models import Order, OrderItem
        from app.services import create_order

        stock_before = self.water.stock
        order_count_before = Order.objects.count()
        item_count_before = OrderItem.objects.count()
        balance_before = self.user_a.container_balance.bottles

        order_data = {
            'address': self.address_a,
            'slot': self.slot,
            'delivery_date': timezone.localdate(),
            'returned_bottles': 0,
            'comment': 'Тест транзакции'
        }

        # Имитируем сбой БД / шлюза на этапе создания позиций заказа внутри create_order
        with patch.object(OrderItem.objects, 'create', side_effect=RuntimeError('Имитация сбоя при записи позиции заказа')):
            with self.assertRaises(RuntimeError):
                create_order(self.user_a, [(self.water, 2)], order_data)

        # Проверяем целостность и атомарность транзакции:
        # Ни заголовок Order, ни позиция OrderItem НЕ должны сохраниться в БД
        self.assertEqual(Order.objects.count(), order_count_before)
        self.assertEqual(OrderItem.objects.count(), item_count_before)

        # Остаток товара на складе НЕ должен уменьшиться
        self.water.refresh_from_db()
        self.assertEqual(self.water.stock, stock_before)

        # Баланс тары пользователя НЕ должен измениться
        self.user_a.container_balance.refresh_from_db()
        self.assertEqual(self.user_a.container_balance.bottles, balance_before)

    def test_neg05_calculation_on_empty_queryset_does_not_crash(self):
        """Негативный тест 5: Расчёт показателей на пустой выборке не падает с ZeroDivisionError или исключениями."""
        from decimal import Decimal
        from app.models import Order
        from app.services import calculate_order

        # Очищаем все заказы для создания полностью пустой выборки
        Order.objects.all().delete()
        self.assertEqual(Order.objects.count(), 0)

        # 1. Расчёт итогов заказа на пустом списке позиций
        totals = calculate_order(lines=[], returned_bottles=0, discount_percent=10)
        self.assertEqual(totals['bottles'], 0)
        self.assertEqual(totals['goods'], Decimal('0'))
        self.assertEqual(totals['deposit'], Decimal('0'))
        self.assertEqual(totals['total'], Decimal('0'))
        self.assertEqual(totals['discount_amount'], Decimal('0'))

        # 2. Страница аналитики и статистики для диспетчера на пустой БД
        self.client.force_login(self.operator)
        resp_stats = self.client.get(reverse('stats'))
        self.assertEqual(resp_stats.status_code, 200)
        self.assertEqual(resp_stats.context['count'], 0)
        self.assertEqual(resp_stats.context['revenue'], 0)
        self.assertEqual(resp_stats.context['average'], 0)
        self.assertEqual(resp_stats.context['share'], 0)

        # 3. Каталог при фильтрации с пустой выборкой
        resp_empty_cat = self.client.get(f"{reverse('catalog')}?price_min=999999")
        self.assertEqual(resp_empty_cat.status_code, 200)
        self.assertEqual(len(resp_empty_cat.context['page'].object_list), 0)

    def test_neg06_custom_500_template_and_logging(self):
        """Проверка шаблона внутренней ошибки сервера 500 и ссылок на главную и поиск."""
        resp_500 = self.client.get(reverse('custom_500'))
        self.assertEqual(resp_500.status_code, 500)
        self.assertContains(resp_500, '500', status_code=500)
        self.assertContains(resp_500, 'Внутренняя ошибка сервера', status_code=500)
        self.assertContains(resp_500, 'На главную', status_code=500)
        self.assertContains(resp_500, 'В каталог и поиск', status_code=500)





