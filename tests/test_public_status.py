import pytest
import sys
import os
from unittest.mock import MagicMock

# Add public_status to import path to be able to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../public_status')))

# Now we can import the public app
from app import app as public_app

@pytest.fixture
def public_client():
    public_app.config['TESTING'] = True
    with public_app.test_client() as client:
        yield client

def test_public_status_index(public_client, monkeypatch):
    # Mock get_db_connection to return a mock connection and cursor
    mock_conn = MagicMock()
    mock_curs = MagicMock()
    
    # Setup mock to return some data to be rendered in the template
    mock_curs.fetchall.side_effect = [
        # 1. Mowing History
        [{'date': '01/01/2026', 'customername': 'Test User', 'section_name': 'Test Section History', 'status': '8/8'}],
        # 2. Last Mowed
        [{'days': 5, 'customername': 'Test User Last', 'section_name': 'Test Section Last'}],
        # 3. Overdue Maintenance (from get_maintenance_items)
        [{'id': 1, 'maintenance_type': 'Test Maintenance', 'interval_h': 10, 'last_maintained_timestamp': '2026-01-01', 'maintained_by': 'Admin', 'used_h': 12, 'remaining_h': -2}]
    ]
    
    mock_conn.cursor.return_value.__enter__.return_value = mock_curs
    # Handle the "with get_db_connection() as conn"
    mock_conn.__enter__.return_value = mock_conn
    
    monkeypatch.setattr('app.get_db_connection', lambda: mock_conn)
    
    response = public_client.get('/')
    assert response.status_code == 200
    
    # Check that the data is rendered in the HTML
    html_data = response.data.decode('utf-8')
    assert 'Test User' in html_data
    assert 'Test Section History' in html_data
    assert 'Test Section Last' in html_data
    assert 'Test Maintenance' in html_data
    assert 'AASvK Greenteam' in html_data

def test_public_status_health(public_client):
    response = public_client.get('/health')
    assert response.status_code == 200
    assert b'OK' == response.data
