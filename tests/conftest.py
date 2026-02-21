"""
Shared pytest fixtures for kiosk app tests.
Mocks psycopg so tests can run without a real database.
"""
import sys
from unittest.mock import MagicMock

# Mock psycopg modules before any app imports
mock_psycopg = MagicMock()
mock_psycopg.rows = MagicMock()
mock_psycopg.rows.dict_row = "dict_row"
mock_psycopg.errors = MagicMock()
mock_psycopg.errors.UniqueViolation = type('UniqueViolation', (Exception,), {})

sys.modules['psycopg'] = mock_psycopg
sys.modules['psycopg_pool'] = MagicMock()
sys.modules['psycopg.conninfo'] = MagicMock()
sys.modules['psycopg.rows'] = mock_psycopg.rows
sys.modules['psycopg.errors'] = mock_psycopg.errors

import pytest
from kiosk.config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    DB_HOST = 'localhost'
    DB_NAME = 'test'
    DB_USER = 'test'
    DB_PASSWORD = 'test'
    ADMIN_USER_IDS = [42]
    ADMIN_PIN = "1234"


@pytest.fixture
def app():
    """Create an application instance for testing."""
    from kiosk import create_app
    app = create_app(TestConfig)
    yield app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def logged_in_client(client):
    """Create a test client with an active session (logged in user)."""
    with client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Test User'
    return client
