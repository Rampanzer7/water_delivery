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
        response = self.client.get(reverse('catalog'), {'q': 'Тестовая'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.water_product, response.context['page'].object_list)
        self.assertNotIn(self.water_out_of_stock, response.context['page'].object_list)

        response = self.client.get(reverse('catalog'), {'available': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.water_product, response.context['page'].object_list)
        self.assertNotIn(self.water_out_of_stock, response.context['page'].object_list)

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
        self.assertIn(f'href="{detail_url}" class="wire-card-btn"', html)
        self.assertNotIn(f'href="{rent_url}" class="wire-card-btn"', html)

    def test_home_page_buttons(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        self.assertIn('wire-btn-cooler', html)

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

        self.assertIn('.wire-hero-label {', css)
        self.assertNotIn('.wire-hero-label {\n  font-size: 12px;\n  letter-spacing: 0.8px;\n  color: var(--color-primary);', css)

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
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('ДОСТАВКА ПИТЬЕВОЙ ВОДЫ И АРЕНДА КУЛЕРОВ', html)
        self.assertNotIn('ВЫБИРАЙТЕ', html)
        self.assertNotIn('class="wire-hero-label"', html)
        self.assertNotIn('class="wire-section-label"', html)

        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('class="wire-section-label"', html)
        self.assertNotIn('КАТАЛОГ ВОДЫ', html)

        response = self.client.get(reverse('coolers'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertNotIn('class="wire-section-label"', html)
        self.assertNotIn('АРЕНДА ОБОРУДОВАНИЯ', html)

        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.wire-hero-label {\n  display: none !important;', css)
        self.assertIn('.wire-section-label {\n  display: none !important;', css)

    def test_requirement_2_login_label_and_email_auth(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Логин или почта', html)
        self.assertNotIn('АВТОРИЗАЦИЯ', html)
        self.assertNotIn('class="wire-section-label"', html)

        login_res = self.client.post(reverse('login'), {
            'username': 'ivanov',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        login_res = self.client.post(reverse('login'), {
            'username': 'ivanov@example.com',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        login_res = self.client.post(reverse('login'), {
            'username': 'IVANOV@EXAMPLE.COM',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

        login_res = self.client.post(reverse('login'), {
            'username': '  ivanov@example.com  ',
            'password': 'secretpassword123',
        })
        self.assertEqual(login_res.status_code, 302)
        self.client.logout()

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

        login_res = self.client.post(reverse('login'), {
            'username': 'ivanov@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(login_res.status_code, 200)

    def test_requirement_3_water_card_buy_button_links_to_product_detail(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        detail_url = reverse('product_detail', kwargs={'pk': self.water.pk})
        self.assertIn(f'class="wire-card-btn" href="{detail_url}">Купить</a>', html)

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

        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn(f'href="{detail_url}"', html)

    def test_requirement_4_cart_redesign(self):
        session = self.client.session
        session['cart'] = {str(self.water.pk): 2}
        session.save()

        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        self.assertIn('wire-cart-layout', html)
        self.assertIn('wire-table-card', html)
        self.assertIn('wire-cart-table', html)
        self.assertIn('wire-checkout-box', html)
        self.assertIn('Вода Артезианская 19 л', html)
        self.assertIn('700', html)
        self.assertIn(reverse('checkout'), html)

        update_res = self.client.post(reverse('cart_update', kwargs={'pk': self.water.pk}), {'quantity': 3})
        self.assertRedirects(update_res, reverse('cart'))
        self.assertEqual(self.client.session['cart'][str(self.water.pk)], 3)

        del_res = self.client.post(reverse('cart_update', kwargs={'pk': self.water.pk}), {'quantity': 0})
        self.assertRedirects(del_res, reverse('cart'))
        self.assertNotIn(str(self.water.pk), self.client.session['cart'])

        response = self.client.get(reverse('cart'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('wire-empty-state-box', html)
        self.assertIn('В корзине пока пусто', html)

        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('@media (max-width: 640px) {', css)
        self.assertIn('.wire-cart-table th,', css)

    def test_requirement_5_delivery_info_no_hover(self):
        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('.wire-card-static,', css)
        self.assertIn('.wire-card-static:hover {', css)
        self.assertIn('transform: none !important;', css)
        self.assertIn('cursor: default !important;', css)
        self.assertIn('.wire-card-static *,', css)

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

        res_cooler = self.client.get(reverse('api_search'), {'q': 'эко'})
        self.assertEqual(res_cooler.status_code, 200)
        data_cooler = res_cooler.json()
        self.assertGreaterEqual(data_cooler['count'], 1)
        cooler_item = [x for x in data_cooler['results'] if x['type'] == 'cooler'][0]
        self.assertEqual(cooler_item['name'], 'Кулер Напольный Эко')
        self.assertEqual(cooler_item['url'], reverse('cooler_detail', kwargs={'pk': self.cooler.pk}))

    def test_json_api_quickview_success_and_404(self):
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

        res_missing = self.client.get(reverse('api_quickview', kwargs={'pk': 999999}))
        self.assertEqual(res_missing.status_code, 404)

    def test_ajax_cart_add_json_response(self):
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
        anon_client = Client(enforce_csrf_checks=True)
        res_cat = anon_client.get(reverse('catalog'))
        self.assertEqual(res_cat.status_code, 200)
        html_cat = res_cat.content.decode('utf-8')
        self.assertIn('name="csrfmiddlewaretoken"', html_cat)

        import re
        csrf_match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html_cat)
        self.assertIsNotNone(csrf_match)
        csrf_token = csrf_match.group(1)

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

        res_reload = anon_client.get(reverse('catalog'))
        self.assertEqual(res_reload.status_code, 200)
        html_reload = res_reload.content.decode('utf-8')
        self.assertIn('Заказать (3)', html_reload)

    def test_server_side_forms_validation(self):
        from app.forms import CoolerForm, DeliveryScheduleForm, ProductForm, RegisterForm
        from django.utils import timezone

        form_reg = RegisterForm(data={
            'username': 'newuser',
            'email': 'lesson9@example.com',
            'phone': '+7 999 111-22-33',
            'password': 'password123',
        })
        self.assertFalse(form_reg.is_valid())
        self.assertIn('email', form_reg.errors)

        form_prod = ProductForm(data={
            'name': 'Неправильная вода',
            'kind': Product.WATER,
            'volume': '19.0',
            'price': '-50',
            'stock': '10',
        })
        self.assertFalse(form_prod.is_valid())
        self.assertIn('price', form_prod.errors)

        form_cooler = CoolerForm(data={
            'name': 'Тестовый кулер',
            'monthly_price': '0',
            'deposit': '500',
            'quantity': '2',
        })
        self.assertFalse(form_cooler.is_valid())
        self.assertIn('monthly_price', form_cooler.errors)

        form_sched = DeliveryScheduleForm(data={
            'quantity': '0',
            'weekday': '1',
        })
        self.assertFalse(form_sched.is_valid())
        self.assertIn('quantity', form_sched.errors)

    def test_client_side_validation_script_and_markup(self):
        val_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'js', 'validation.js')
        self.assertTrue(os.path.exists(val_path))
        with open(val_path, 'r', encoding='utf-8') as f:
            js = f.read()
        self.assertIn('EMAIL_REGEX', js)
        self.assertIn('PHONE_REGEX', js)
        self.assertIn('is-invalid', js)
        self.assertIn('wire-client-error', js)
        self.assertIn('Нельзя выбрать прошедшую дату', js)

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

        chk_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'js', 'checkout.js')
        with open(chk_path, 'r', encoding='utf-8') as f:
            cjs = f.read()
        self.assertIn('wire-is-loading', cjs)
        self.assertIn('Загрузка доступных интервалов', cjs)
        self.assertIn('sum-total-mobile', cjs)

        base_path = os.path.join(settings.BASE_DIR, 'app', 'templates', 'base.html')
        with open(base_path, 'r', encoding='utf-8') as f:
            base_html = f.read()
        self.assertIn('<title>', base_html)
        self.assertIn('validation.js', base_html)
        self.assertIn('interactive.js', base_html)
        self.assertIn('wireCsrfHolder', base_html)
        self.assertIn('cart_count', base_html)

        css_path = os.path.join(settings.BASE_DIR, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('.wire-client-error', css)
        self.assertIn('.wire-spinner', css)
        self.assertIn('.wire-search-dropdown', css)
        self.assertIn('.wire-modal', css)
        self.assertIn('.wire-toast', css)

