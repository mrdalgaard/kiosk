import pytest
from unittest.mock import patch, MagicMock

def test_customer_list_success(client):
    """Test successful retrieval and rendering of the customer list limit."""
    
    with patch('kiosk.routes.api.get_db_connection') as mock_db, \
         patch('kiosk.routes.api.Config') as mock_config:
         
        mock_config.CUSTOMER_GROUPS = [10, 20]
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # Mock finding two customers
        mock_curs.fetchall.return_value = [
            {'customerid': 1, 'customername': 'Alice'},
            {'customerid': 2, 'customername': 'Bob'}
        ]
        
        response = client.get('/customerlist')
        
        assert response.status_code == 200
        assert b'Alice' in response.data
        assert b'Bob' in response.data
        
        # Verify db query arguments included customer groups config
        assert mock_curs.execute.call_count == 1
        args = mock_curs.execute.call_args[0]
        assert "SELECT * FROM customers" in args[0]
        assert args[1][0] == [10, 20]

def test_customer_list_db_error(client):
    """Test retrieving customer list handles database failure."""
    
    with patch('kiosk.routes.api.get_db_connection') as mock_db:
        mock_db.side_effect = Exception('DB Timeout connection')
        
        response = client.get('/customerlist')
        
        # Route should handle error by gracefully rendering login.html with an error message
        assert response.status_code == 200
        assert 'Systemfejl: Kunne ikke forbinde til databasen.'.encode() in response.data
