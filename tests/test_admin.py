import pytest
from unittest.mock import MagicMock, patch
from kiosk.database import get_db_pool

def test_admin_access_unauthenticated(client):
    """Test accessing admin without login redirects to login."""
    response = client.get('/admin/products')
    assert response.status_code == 302
    # Redirects to root (login page)
    assert response.headers['Location'] == '/' or response.headers['Location'] == 'http://localhost/'

def test_admin_access_unauthorized(client):
    """Test accessing admin as a logged-in but non-admin user."""
    with client.session_transaction() as sess:
        sess['customerid'] = 999  # Not in ADMIN_USER_IDS (42)
        sess['customername'] = 'Non Admin'
    
    response = client.get('/admin/products')
    assert response.status_code == 302
    assert '/index' in response.headers['Location'] # Redirects to main

def test_admin_pin_required(client, logged_in_client):
    """Test accessing admin as admin user without PIN redirects to PIN entry."""
    # current_user is 42 (Admin), but no PIN entered
    response = client.get('/admin/products')
    assert response.status_code == 302
    assert '/admin/login' in response.headers['Location']

def test_admin_pin_entry_success(client, logged_in_client):
    """Test entering correct PIN sets session and redirects."""
    response = client.post('/admin/login', data={'pin': '1234'})
    assert response.status_code == 302
    assert '/admin/products' in response.headers['Location']
    
    with client.session_transaction() as sess:
        assert sess['admin_authenticated'] == True

def test_admin_pin_entry_failure(client, logged_in_client):
    """Test entering incorrect PIN shows error."""
    response = client.post('/admin/login', data={'pin': '0000'})
    assert response.status_code == 200
    assert b'Forkert PIN kode' in response.data

def test_product_list(client, logged_in_client):
    """Test product list page loads (mock DB)."""
    # Authenticate first
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    # Mock DB response
    mock_pool = get_db_pool()
    mock_conn = MagicMock()
    mock_curs = MagicMock()
    mock_pool.connection.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_curs
    mock_curs.__enter__.return_value = mock_curs
    
    # Mock products
    mock_curs.fetchall.return_value = [
        {'productid': 1, 'productname': 'Test Cola', 'itemprice': 10.0, 'imagefilename': 'cola.jpg', 'sorting': 10, 'disabled': False}
    ]

    response = client.get('/admin/products')
    assert response.status_code == 200
    assert b'Test Cola' in response.data

def test_add_product(client, logged_in_client):
    """Test adding a new product."""
    # Authenticate
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    # Mock DB
    mock_pool = get_db_pool()
    mock_conn = MagicMock()
    mock_curs = MagicMock()
    mock_pool.connection.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_curs
    mock_curs.__enter__.return_value = mock_curs

    import io
    data = {
        'productname': 'New Product',
        'itemprice': '20.00',
        'sorting': '50',
        'disabled': 'off',
        'imagefile': (io.BytesIO(b"fake image content"), 'test.jpg')
    }
    
    response = client.post('/admin/products/new', data=data, content_type='multipart/form-data')
    
    # Needs to check if INSERT was called
    assert mock_curs.execute.called
    assert "INSERT INTO products" in mock_curs.execute.call_args[0][0]

def test_delete_product_success(client, logged_in_client):
    """Test deleting a product with no sales references."""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    mock_pool = get_db_pool()
    mock_conn = MagicMock()
    mock_curs = MagicMock()
    mock_pool.connection.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_curs
    mock_curs.__enter__.return_value = mock_curs
    
    # 0 sales references
    mock_curs.fetchone.return_value = [0]

    response = client.post('/admin/products/1/delete')
    
    # Verify DELETE was called
    assert "DELETE FROM products" in mock_curs.execute.call_args_list[1][0][0]
    assert response.status_code == 302

def test_delete_product_blocked_by_sales(client, logged_in_client):
    """Test deletion is blocked if sales exist."""
    with client.session_transaction() as sess:
        sess['admin_authenticated'] = True

    mock_pool = get_db_pool()
    mock_conn = MagicMock()
    mock_curs = MagicMock()
    mock_pool.connection.return_value = mock_conn
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_curs
    mock_curs.__enter__.return_value = mock_curs
    
    # 5 sales references
    mock_curs.fetchone.return_value = [5]

    response = client.post('/admin/products/1/delete')
    
    # Verify DELETE was NOT called
    assert not any("DELETE" in call[0][0] for call in mock_curs.execute.call_args_list)
    assert response.status_code == 302
    with client.session_transaction() as sess:
        # Check flash message context if possible, or just redirect
        pass

def test_image_gallery(logged_in_client):
    """Test image gallery loads existing mock images."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.os.listdir') as mock_listdir, \
         patch('kiosk.routes.admin.os.path.isfile') as mock_isfile:
        mock_listdir.return_value = ['image1.jpg', 'image2.png']
        mock_isfile.return_value = True

        response = logged_in_client.get('/admin/images')
        assert response.status_code == 200
        assert b'image1.jpg' in response.data
        assert b'image2.png' in response.data

def test_image_upload(logged_in_client):
    """Test uploading an image."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.os.path.join', return_value='/fake/path/test.jpg'), \
         patch('werkzeug.datastructures.FileStorage.save'):
        import io
        data = {
            'imagefile': (io.BytesIO(b"fake image content"), 'test.jpg')
        }
        response = logged_in_client.post('/admin/images/upload', data=data, content_type='multipart/form-data')
        
        # Verify redirect to gallery
        assert response.status_code == 302
        assert '/admin/images' in response.headers['Location']

def test_image_delete_success(logged_in_client):
    """Test deleting an image not used by products."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db, \
         patch('kiosk.routes.admin.os.path.exists', return_value=True), \
         patch('kiosk.routes.admin.os.remove') as mock_remove:
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # 0 products use this image
        mock_curs.fetchone.return_value = [0]
        
        response = logged_in_client.post('/admin/images/delete/test.jpg')
        assert response.status_code == 302
        assert '/admin/images' in response.headers['Location']
        mock_remove.assert_called_once()

def test_image_delete_blocked(logged_in_client):
    """Test deleting an image block when used by products."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db, \
         patch('kiosk.routes.admin.os.remove') as mock_remove:
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # 2 products use this image
        mock_curs.fetchone.return_value = [2]
        
        response = logged_in_client.post('/admin/images/delete/test.jpg')
        assert response.status_code == 302
        mock_remove.assert_not_called()

def test_product_edit_get(logged_in_client):
    """Test loading product edit form."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db, \
         patch('kiosk.routes.admin._get_available_images', return_value=['img.jpg']):
        
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        mock_curs.fetchone.return_value = {
            'productid': 1, 'productname': 'Cola', 'itemprice': 10.0, 'imagefilename': 'img.jpg'
        }
        
        response = logged_in_client.get('/admin/products/1/edit')
        assert response.status_code == 200
        assert b'Cola' in response.data

def test_product_edit_post(logged_in_client):
    """Test submitting product edits."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        data = {
            'productname': 'Cola Zero',
            'itemprice': '15.00',
            'sorting': '10',
            'disabled': 'off',
            'selected_image': 'img2.jpg'
        }
        
        response = logged_in_client.post('/admin/products/1/edit', data=data)
        
        assert response.status_code == 302
        assert '/admin/products' in response.headers['Location']
        
        assert mock_curs.execute.call_count == 1
        call_args = mock_curs.execute.call_args[0]
        assert "UPDATE products" in call_args[0]
        # (productname, itemprice, image_filename, disabled, sorting, product_id)
        assert call_args[1] == ('Cola Zero', '15.00', 'img2.jpg', False, '10', 1)

def test_product_list_db_error(logged_in_client):
    """Test product list handles DB exception."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection', side_effect=Exception('DB Down')):
        response = logged_in_client.get('/admin/products')
        assert response.status_code == 302
        assert '/' in response.headers['Location']

def test_image_gallery_os_error(logged_in_client):
    """Test image gallery handles OS Exception."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.os.listdir', side_effect=Exception('Permission Denied')):
        response = logged_in_client.get('/admin/images')
        assert response.status_code == 200
        # Should gracefully load with empty images list
        assert b'Billedgalleri' in response.data

def test_image_delete_db_error(logged_in_client):
    """Test image delete handles DB crash trying to verify usage count."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection', side_effect=Exception('DB Crash')):
        response = logged_in_client.post('/admin/images/delete/any.jpg')
        assert response.status_code == 302
        assert '/admin/images' in response.headers['Location']

def test_product_delete_db_error(logged_in_client):
    """Test product delete handles DB crash gracefully."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection', side_effect=Exception('DB Crash')):
        response = logged_in_client.post('/admin/products/1/delete')
        assert response.status_code == 302
        assert '/admin/products' in response.headers['Location']

def test_product_edit_db_error_get(logged_in_client):
    """Test product edit page fetching handles DB error."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection', side_effect=Exception('DB Down')):
        response = logged_in_client.get('/admin/products/1/edit')
        assert response.status_code == 302
        assert '/admin/products' in response.headers['Location']

def test_product_edit_db_error_post(logged_in_client):
    """Test product edit saving handles DB error."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection', side_effect=Exception('DB Crash')):
        data = {'productname': 'Cola'}
        response = logged_in_client.post('/admin/products/1/edit', data=data)
        assert response.status_code == 200
        assert b'Fejl ved gemning' in response.data

def test_mowing_user_list(logged_in_client):
    """Test loading Greenteam user list."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # Two queries executed: mowing users, then available customers
        mock_curs.fetchall.side_effect = [
            [{'customerid': 1, 'customername': 'Mowing User 1'}],
            [{'customerid': 2, 'customername': 'Available User 2'}]
        ]
        
        response = logged_in_client.get('/admin/greenteam')
        assert response.status_code == 200
        assert b'Mowing User 1' in response.data
        assert b'Available User 2' in response.data

def test_mowing_user_add(logged_in_client):
    """Test adding a Greenteam user."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        data = {'customerid': '2'}
        response = logged_in_client.post('/admin/greenteam/add', data=data)
        
        assert response.status_code == 302
        assert '/admin/greenteam' in response.headers['Location']
        
        assert mock_curs.execute.call_count == 1
        assert "INSERT INTO mowingusers" in mock_curs.execute.call_args[0][0]

def test_mowing_user_delete(logged_in_client):
    """Test removing a Greenteam user."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        response = logged_in_client.post('/admin/greenteam/1/delete')
        
        assert response.status_code == 302
        assert '/admin/greenteam' in response.headers['Location']
        
        assert mock_curs.execute.call_count == 1
        assert "DELETE FROM mowingusers" in mock_curs.execute.call_args[0][0]
