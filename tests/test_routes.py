"""
Tests for kiosk app routes.
Covers: auth flow, login_required decorator, cart operations, 
checkout, error handling, health check, and customer list.
"""
from unittest.mock import patch, MagicMock
from decimal import Decimal


class TestAppCreation:
    """Basic app creation and route registration."""

    def test_app_is_created(self, app):
        assert app is not None

    def test_app_is_testing(self, app):
        assert app.testing is True

    def test_routes_registered(self, app):
        rules = [str(r) for r in app.url_map.iter_rules()]
        assert '/' in rules
        assert '/index' in rules
        assert '/customerlist' in rules
        assert '/health' in rules
        assert '/register_mowing' in rules
        assert '/mowing_status' in rules
        assert '/logout' in rules


class TestAuth:
    """Login and logout routes."""

    def test_login_page_loads(self, client):
        with patch('kiosk.routes.auth.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get('/')
            assert response.status_code == 200
            assert b'Login' in response.data

    def test_login_empty_id_shows_error(self, client):
        with patch('kiosk.routes.auth.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.post('/', data={'customer_id': ''})
            assert response.status_code == 200
            assert 'Indtast medlemsnummer'.encode() in response.data

    def test_login_valid_user_redirects(self, client):
        with patch('kiosk.routes.auth.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            # First call: purchase history, second call: user lookup
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {
                'customerid': 42,
                'customername': 'Test User'
            }
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.post('/', data={'customer_id': '42'})
            assert response.status_code == 302
            assert '/index' in response.headers['Location']

    def test_login_unknown_user_shows_error(self, client):
        with patch('kiosk.routes.auth.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = None
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.post('/', data={'customer_id': '99999'})
            assert response.status_code == 200
            assert 'ikke fundet'.encode() in response.data

    def test_logout_clears_session(self, logged_in_client):
        response = logged_in_client.get('/logout')
        assert response.status_code == 302

        with logged_in_client.session_transaction() as sess:
            assert 'customerid' not in sess


class TestLoginRequired:
    """Tests for the @login_required decorator."""

    def test_index_redirects_when_not_logged_in(self, client):
        response = client.get('/index')
        assert response.status_code == 302
        assert '/' in response.headers['Location']

    def test_add_to_cart_redirects_when_not_logged_in(self, client):
        response = client.post('/add_to_cart/1')
        assert response.status_code == 302

    def test_checkout_redirects_when_not_logged_in(self, client):
        response = client.post('/checkout')
        assert response.status_code == 302

    def test_register_mowing_redirects_when_not_logged_in(self, client):
        response = client.get('/register_mowing')
        assert response.status_code == 302

    def test_mowing_status_redirects_when_not_logged_in(self, client):
        response = client.get('/mowing_status')
        assert response.status_code == 302


class TestIndex:
    """Tests for the main index page (product listing + cart)."""

    def test_index_loads_when_logged_in(self, logged_in_client):
        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.side_effect = [
                [{'productid': 1, 'productname': 'Kaffe', 'itemprice': Decimal('10.00'), 'imagefilename': 'kaffe.jpg'}],
                [],  # purchase history
            ]
            mock_cursor.fetchone.return_value = None  # not greenteam
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = logged_in_client.get('/index')
            assert response.status_code == 200
            assert b'Velkommen Test User' in response.data
            assert b'Kaffe' in response.data

    def test_index_handles_db_error(self, logged_in_client):
        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_db.side_effect = Exception('DB down')

            response = logged_in_client.get('/index')
            assert response.status_code == 200
            assert 'Systemfejl'.encode() in response.data


class TestCart:
    """Tests for add_to_cart functionality."""

    def test_add_to_cart_creates_new_item(self, logged_in_client):
        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                'itemprice': Decimal('10.00'),
                'productname': 'Kaffe'
            }
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = logged_in_client.post('/add_to_cart/1')
            assert response.status_code == 302

            with logged_in_client.session_transaction() as sess:
                assert '1' in sess['cart']
                assert sess['cart']['1']['quantity'] == 1

    def test_add_to_cart_increments_existing_item(self, logged_in_client):
        with logged_in_client.session_transaction() as sess:
            sess['cart'] = {
                '1': {'itemprice': Decimal('10.00'), 'productname': 'Kaffe', 'quantity': 1}
            }

        response = logged_in_client.post('/add_to_cart/1')
        assert response.status_code == 302

        with logged_in_client.session_transaction() as sess:
            assert sess['cart']['1']['quantity'] == 2

    def test_add_to_cart_handles_db_error(self, logged_in_client):
        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_db.side_effect = Exception('DB down')

            response = logged_in_client.post('/add_to_cart/1')
            # Should redirect back to index even on error
            assert response.status_code == 302



class TestCartRemoval:
    """Tests for remove_from_cart functionality."""

    def test_remove_decrements_quantity(self, logged_in_client):
        with logged_in_client.session_transaction() as sess:
            sess['cart'] = {
                '1': {'itemprice': Decimal('10.00'), 'productname': 'Kaffe', 'quantity': 2}
            }

        response = logged_in_client.post('/remove_from_cart/1')
        assert response.status_code == 302
        assert '/index' in response.headers['Location']

        with logged_in_client.session_transaction() as sess:
            assert sess['cart']['1']['quantity'] == 1

    def test_remove_deletes_item_at_zero(self, logged_in_client):
        with logged_in_client.session_transaction() as sess:
            sess['cart'] = {
                '1': {'itemprice': Decimal('10.00'), 'productname': 'Kaffe', 'quantity': 1}
            }

        response = logged_in_client.post('/remove_from_cart/1')
        assert response.status_code == 302

        with logged_in_client.session_transaction() as sess:
            assert '1' not in sess['cart']

    def test_remove_ignores_invalid_product(self, logged_in_client):
        response = logged_in_client.post('/remove_from_cart/999')
        assert response.status_code == 302

    def test_remove_redirects_when_not_logged_in(self, client):
        response = client.post('/remove_from_cart/1')
        assert response.status_code == 302


class TestCheckout:
    """Tests for the checkout flow."""

    def test_checkout_with_empty_cart(self, logged_in_client):
        response = logged_in_client.post('/checkout')
        assert response.status_code == 302
        assert '/' in response.headers['Location']

    def test_checkout_success_clears_session(self, logged_in_client):
        with logged_in_client.session_transaction() as sess:
            sess['cart'] = {
                '1': {'itemprice': Decimal('10.00'), 'productname': 'Kaffe', 'quantity': 2}
            }

        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (1,)  # salesid
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_conn.transaction.return_value.__enter__ = MagicMock()
            mock_conn.transaction.return_value.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = logged_in_client.post('/checkout')
            assert response.status_code == 200

            with logged_in_client.session_transaction() as sess:
                assert sess.get('purchase') == 1
                assert 'cart' not in sess

    def test_checkout_handles_db_error(self, logged_in_client):
        with logged_in_client.session_transaction() as sess:
            sess['cart'] = {
                '1': {'itemprice': Decimal('10.00'), 'productname': 'Kaffe', 'quantity': 1}
            }

        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_db.side_effect = Exception('DB down')

            response = logged_in_client.post('/checkout')
            assert response.status_code == 302
            assert '/' in response.headers['Location']

            with logged_in_client.session_transaction() as sess:
                assert sess.get('purchase') is None


class TestHealthCheck:
    """Tests for the /health endpoint."""

    def test_health_check_healthy(self, client):
        with patch('kiosk.routes.api.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get('/health')
            assert response.status_code == 200
            assert response.json['status'] == 'healthy'

    def test_health_check_unhealthy(self, client):
        with patch('kiosk.routes.api.get_db_connection') as mock_db:
            mock_db.side_effect = Exception('Connection refused')

            response = client.get('/health')
            assert response.status_code == 500
            assert response.json['status'] == 'unhealthy'


class TestConfig:
    """Tests for configuration values."""

    def test_customer_groups_are_defined(self, app):
        assert len(app.config.get('CUSTOMER_GROUPS', [])) > 0 or hasattr(app.config, 'from_object')
        from kiosk.config import Config as AppConfig
        assert AppConfig.CUSTOMER_GROUPS == [10, 15, 20, 30, 40]

    def test_customer_groups_all_includes_hidden(self):
        from kiosk.config import Config as AppConfig
        assert 1 in AppConfig.CUSTOMER_GROUPS_ALL
        assert all(g in AppConfig.CUSTOMER_GROUPS_ALL for g in AppConfig.CUSTOMER_GROUPS)

    def test_eco_product_id_is_int(self):
        from kiosk.config import Config as AppConfig
        assert isinstance(AppConfig.ECO_PRODUCT_ID, int)

class TestHistory:
    """Tests for the purchase history page."""

    def test_history_loads_when_logged_in(self, logged_in_client):
        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            
            # Mock purchase history query response
            mock_cursor.fetchall.return_value = [
                {'productname': 'Kaffe', 'solditemprice': Decimal('5.00'), 'timestamp': '2026-02-21 12:00:00', 'quantity': 1}
            ]
            
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = logged_in_client.get('/history')
            assert response.status_code == 200
            assert b'Kaffe' in response.data
            assert b'Test User' in response.data

    def test_history_handles_db_error(self, logged_in_client):
        with patch('kiosk.routes.main.get_db_connection') as mock_db:
            mock_db.side_effect = Exception('DB down')

            response = logged_in_client.get('/history')
            assert response.status_code == 200
            assert 'Systemfejl'.encode() in response.data

    def test_history_redirects_when_not_logged_in(self, client):
        response = client.get('/history')
        assert response.status_code == 302
        assert '/' in response.headers['Location']


class TestSecurityHeaders:
    """Tests for security headers like Cache-Control."""

    def test_html_responses_have_cache_control(self, client):
        with patch('kiosk.routes.auth.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get('/')
            assert response.status_code == 200
            assert response.headers['Cache-Control'] == 'no-store, no-cache, must-revalidate, max-age=0'
            assert response.headers['Pragma'] == 'no-cache'
            assert response.headers['Expires'] == '0'
            assert response.headers['Vary'] == 'Cookie'

    def test_json_responses_skip_cache_control(self, client):
        with patch('kiosk.routes.api.get_db_connection') as mock_db:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.__enter__ = lambda s: mock_conn
            mock_conn.__exit__ = MagicMock(return_value=False)
            mock_cursor.__enter__ = lambda s: mock_cursor
            mock_cursor.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor
            mock_db.return_value = mock_conn

            response = client.get('/health')
            assert response.status_code == 200
            # Test that we didn't add the HTML-specific cache prevention
            assert 'no-store' not in response.headers.get('Cache-Control', '')
