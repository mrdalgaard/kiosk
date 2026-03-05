import pytest
from unittest.mock import MagicMock, patch, mock_open
from kiosk.database import init_db_schema

def test_init_db_schema(app):
    """Test schema initialization logic."""
    
    # Mock file existence, directory listing, and content
    with patch('os.path.exists', return_value=True), \
         patch('os.listdir', return_value=[]), \
         patch('builtins.open', mock_open(read_data="CREATE TABLE test;")):
         
        with patch('kiosk.database.get_db_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_curs = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value = mock_curs
            mock_curs.__enter__.return_value = mock_curs
            
            init_db_schema(app)
            
            # Verify SQL execution
            mock_curs.execute.assert_any_call("CREATE TABLE test;")
            mock_conn.commit.assert_called()

def test_init_db_schema_missing_file(app):
    """Test schema init skips if file missing."""
    with patch('os.path.exists', return_value=False):
        with patch('kiosk.database.get_db_connection') as mock_get_conn:
            init_db_schema(app)
            
            # Should not call DB
            mock_get_conn.assert_not_called()
