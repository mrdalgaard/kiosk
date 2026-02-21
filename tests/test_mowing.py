import pytest
from unittest.mock import patch, MagicMock

def test_register_mowing_get_renders_form(logged_in_client):
    """Test getting mowing form fetches sections."""
    with patch('kiosk.routes.mowing.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_curs.fetchall.return_value = [
            {'id': 1, 'section_name': 'Hul 1'}
        ]
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn

        response = logged_in_client.get('/register_mowing')
        assert response.status_code == 200
        assert b'Hul 1' in response.data

def test_register_mowing_post_inserts_activity(logged_in_client):
    """Test posting mowing status inserts db rows and redirects."""
    with patch('kiosk.routes.mowing.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn

        data = {
            'date': '2025-01-01',
            'status_1': '8/8',
            'status_2': 'NotMowed', # Should be ignored
            'status_3': '4/8'
        }
        
        response = logged_in_client.post('/register_mowing', data=data)
        
        # Verify redirects
        assert response.status_code == 302
        assert '/mowing_status' in response.headers['Location']
        
        # Verify executes
        assert mock_curs.execute.call_count == 2
        calls = mock_curs.execute.call_args_list
        # First call for section 1
        assert calls[0][0][1] == (42, '2025-01-01', 1, '8/8')
        # Second call for section 3
        assert calls[1][0][1] == (42, '2025-01-01', 3, '4/8')

def test_register_mowing_post_future_date_clamped(logged_in_client):
    """Test posting mowing status with future date clamps to today."""
    with patch('kiosk.routes.mowing.get_db_connection') as mock_db, \
         patch('kiosk.routes.mowing.datetime') as mock_datetime:
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn

        # Mock datetime to always be '2026-02-21'
        mock_datetime.date.today.return_value = MagicMock()
        mock_datetime.date.today.return_value.__str__.return_value = '2026-02-21'
        mock_datetime.datetime.now.return_value.astimezone.return_value = '2026-02-21 12:00:00+00:00'

        # Attempt to insert future date
        data = {
            'date': '2099-12-31',
            'status_1': '8/8'
        }
        
        response = logged_in_client.post('/register_mowing', data=data)
        
        assert response.status_code == 302
        assert mock_curs.execute.call_count == 1
        calls = mock_curs.execute.call_args_list
        # Should be clamped to today, resulting in the timezone aware timestamp being inserted
        assert calls[0][0][1] == (42, '2026-02-21 12:00:00+00:00', 1, '8/8')

def test_mowing_status(logged_in_client):
    """Test fetching and rendering mowing history."""
    with patch('kiosk.routes.mowing.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # mock first query (history)
        history = [{'date': '21/02/2026', 'customername': 'Test User', 'section_name': 'Hul 1', 'status': 'Mowed'}]
        # mock second query (last_mowed)
        last_mowed = [{'days': 2, 'customername': 'Test User', 'section_name': 'Hul 1'}]
        
        mock_curs.fetchall.side_effect = [history, last_mowed]

        response = logged_in_client.get('/mowing_status')
        assert response.status_code == 200
        assert b'21/02/2026' in response.data
        assert b'Test User' in response.data
        assert b'Hul 1' in response.data

def test_mowing_maintenance_get(logged_in_client):
    """Test getting mowing maintenance form logic."""
    with patch('kiosk.routes.mowing.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_curs.fetchall.return_value = [
            {'id': 1, 'maintenance_type': 'Test Maintenance', 'interval_h': 100, 
             'last_maintained_timestamp': '2026-02-21', 'maintained_by': 'AdminUser', 'used_h': 10.5}
        ]
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn

        response = logged_in_client.get('/mowing_maintenance')
        assert response.status_code == 200
        assert b'Test Maintenance' in response.data
        assert b'AdminUser' in response.data

def test_reset_maintenance_post(logged_in_client):
    """Test posting to reset maintenance."""
    with patch('kiosk.routes.mowing.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn

        response = logged_in_client.post('/reset_maintenance/1')
        
        assert response.status_code == 302
        assert '/mowing_maintenance' in response.headers['Location']
        
        assert mock_curs.execute.call_count == 1
        calls = mock_curs.execute.call_args_list
        # user_id should be 42 (from logged_in_client fixture), maintenance_id should be 1
        assert calls[0][0][1] == (42, 1)
