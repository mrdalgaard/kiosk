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
    assert '/admin/' in response.headers['Location']
    
    with client.session_transaction() as sess:
        assert sess['admin_authenticated'] == True

def test_admin_pin_entry_failure(client, logged_in_client):
    """Test entering incorrect PIN shows error."""
    response = client.post('/admin/login', data={'pin': '0000'})
    assert response.status_code == 200
    assert b'Forkert PIN kode' in response.data

def test_admin_pin_lockout_after_max_attempts(client, logged_in_client):
    """Test that too many failed PIN attempts triggers a lockout."""
    from kiosk.routes.admin import _pin_attempts, _pin_lock
    # Clear any previous state
    with _pin_lock:
        _pin_attempts.clear()
    
    # Fail 5 times
    for _ in range(5):
        response = client.post('/admin/login', data={'pin': '0000'})
        assert b'Forkert PIN kode' in response.data
    
    # 6th attempt should be locked out
    response = client.post('/admin/login', data={'pin': '0000'})
    assert response.status_code == 200
    assert 'mange' in response.data.decode('utf-8')  # "For mange forsøg"
    
    # Cleanup
    with _pin_lock:
        _pin_attempts.clear()

def test_admin_pin_lockout_resets_on_success(client, logged_in_client):
    """Test that a successful login clears the failed attempt counter."""
    from kiosk.routes.admin import _pin_attempts, _pin_lock
    with _pin_lock:
        _pin_attempts.clear()
    
    # Fail 3 times
    for _ in range(3):
        client.post('/admin/login', data={'pin': '0000'})
    
    # Succeed
    client.post('/admin/login', data={'pin': '1234'})
    
    # Counter should be cleared
    with _pin_lock:
        ip_entry = _pin_attempts.get('127.0.0.1')
    assert ip_entry is None
    
    with _pin_lock:
        _pin_attempts.clear()

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

    with patch('kiosk.routes.admin.images.os.listdir') as mock_listdir, \
         patch('kiosk.routes.admin.images.os.path.isfile') as mock_isfile:
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

    with patch('kiosk.routes.admin.images.os.path.join', return_value='/fake/path/test.jpg'), \
         patch('werkzeug.datastructures.FileStorage.save'):
        import io
        data = {
            'imagefile': (io.BytesIO(b"fake image content"), 'test.jpg')
        }
        response = logged_in_client.post('/admin/images/upload', data=data, content_type='multipart/form-data')
        
        # Verify redirect to gallery
        assert response.status_code == 302
        assert '/admin/images' in response.headers['Location']

def test_image_upload_rejected_extension(logged_in_client):
    """Test uploading a file with a disallowed extension is rejected."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    import io
    data = {
        'imagefile': (io.BytesIO(b"not an image"), 'malware.exe')
    }
    response = logged_in_client.post('/admin/images/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    assert '/admin/images' in response.headers['Location']

def test_image_upload_rejected_too_large(logged_in_client):
    """Test uploading a file larger than 100KB is rejected."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    import io
    oversized_content = b"x" * (101 * 1024)  # 101 KB
    data = {
        'imagefile': (io.BytesIO(oversized_content), 'large.png')
    }
    with patch('werkzeug.datastructures.FileStorage.save'):
        response = logged_in_client.post('/admin/images/upload', data=data, content_type='multipart/form-data')
    assert response.status_code == 302
    assert '/admin/images' in response.headers['Location']

def test_product_upload_rejected_extension(logged_in_client):
    """Test adding a product with a disallowed image extension is rejected."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.products._get_available_images', return_value=['img.jpg']):
        import io
        data = {
            'productname': 'Bad Product',
            'itemprice': '20.00',
            'sorting': '50',
            'disabled': 'off',
            'imagefile': (io.BytesIO(b"not an image"), 'file.pdf')
        }
        response = logged_in_client.post('/admin/products/new', data=data, content_type='multipart/form-data')
        assert response.status_code == 200  # Re-renders form with error

def test_image_delete_success(logged_in_client):
    """Test deleting an image not used by products."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.images.get_db_connection') as mock_db, \
         patch('kiosk.routes.admin.images.os.path.exists', return_value=True), \
         patch('kiosk.routes.admin.images.os.remove') as mock_remove:
        
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

    with patch('kiosk.routes.admin.images.get_db_connection') as mock_db, \
         patch('kiosk.routes.admin.images.os.remove') as mock_remove:
        
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

    with patch('kiosk.routes.admin.products.get_db_connection') as mock_db, \
         patch('kiosk.routes.admin.products._get_available_images', return_value=['img.jpg']):
        
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

    with patch('kiosk.routes.admin.products.get_db_connection') as mock_db:
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

    with patch('kiosk.routes.admin.products.get_db_connection', side_effect=Exception('DB Down')):
        response = logged_in_client.get('/admin/products')
        assert response.status_code == 302
        assert '/' in response.headers['Location']

def test_image_gallery_os_error(logged_in_client):
    """Test image gallery handles OS Exception."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.images.os.listdir', side_effect=Exception('Permission Denied')):
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

    with patch('kiosk.routes.admin.images.get_db_connection', side_effect=Exception('DB Crash')):
        response = logged_in_client.post('/admin/images/delete/any.jpg')
        assert response.status_code == 302
        assert '/admin/images' in response.headers['Location']

def test_product_delete_db_error(logged_in_client):
    """Test product delete handles DB crash gracefully."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_users.get_db_connection', side_effect=Exception('DB Crash')):
        response = logged_in_client.post('/admin/products/1/delete')
        assert response.status_code == 302
        assert '/admin/products' in response.headers['Location']

def test_product_edit_db_error_get(logged_in_client):
    """Test product edit page fetching handles DB error."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.products.get_db_connection', side_effect=Exception('DB Down')):
        response = logged_in_client.get('/admin/products/1/edit')
        assert response.status_code == 302
        assert '/admin/products' in response.headers['Location']

def test_product_edit_db_error_post(logged_in_client):
    """Test product edit saving handles DB error."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.products.get_db_connection', side_effect=Exception('DB Crash')):
        data = {'productname': 'Cola'}
        response = logged_in_client.post('/admin/products/1/edit', data=data)
        assert response.status_code == 200
        # Assert that the error is flashed
        assert b"Der opstod en systemfejl ved gemning af produktet." in response.data

def test_mowing_user_list(logged_in_client):
    """Test loading Greenteam user list."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_users.get_db_connection') as mock_db:
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

    with patch('kiosk.routes.admin.mowing_users.get_db_connection') as mock_db:
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

    with patch('kiosk.routes.admin.mowing_users.get_db_connection') as mock_db:
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

def test_section_list(logged_in_client):
    """Test loading Sections list."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_sections.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        mock_curs.fetchall.return_value = [
            {'id': 1, 'section_name': 'Test Bane 1', 'cutting_time_in_h': 1.5, 'disabled': False}
        ]
        
        response = logged_in_client.get('/admin/sections')
        assert response.status_code == 200
        assert b'Test Bane 1' in response.data

def test_section_add(logged_in_client):
    """Test adding a Section."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_sections.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        data = {'section_name': 'New Section', 'cutting_time_in_h': '2.5'}
        response = logged_in_client.post('/admin/sections/new', data=data)
        
        assert response.status_code == 302
        assert '/admin/sections' in response.headers['Location']
        assert "INSERT INTO mowingsections" in mock_curs.execute.call_args[0][0]

def test_section_delete_fallback_to_disable(logged_in_client):
    """Test deleting a Section that has history falls back to disabling it."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    import psycopg
    with patch('kiosk.routes.admin.mowing_sections.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        
        # When get_db_connection is called twice in the route, return the same mocked connection
        mock_db.return_value = mock_conn
        
        # We need to simulate the execute throwing a ForeignKeyViolation on the DELETE
        # but succeeding on the UPDATE
        def mock_execute(query, args=None):
            if "DELETE FROM mowingsections" in query:
                raise Exception('foreign key constraint violation')
            return MagicMock()
            
        mock_curs.execute.side_effect = mock_execute
        
        response = logged_in_client.post('/admin/sections/1/delete')
        
        assert response.status_code == 302
        
        # Second execute should be UPDATE disabled = true
        assert "UPDATE mowingsections SET disabled = true" in mock_curs.execute.call_args_list[1][0][0]

def test_maintenance_list(logged_in_client):
    """Test loading Maintenance list."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_maintenance.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        mock_curs.fetchall.return_value = [
            {'id': 1, 'maintenance_type': 'Test Olieskift', 'interval_h': 15.0}
        ]
        
        response = logged_in_client.get('/admin/maintenance')
        assert response.status_code == 200
        assert b'Test Olieskift' in response.data

def test_maintenance_add(logged_in_client):
    """Test adding a Maintenance Task."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_maintenance.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        data = {'maintenance_type': 'Knivskift', 'interval_h': '30.0'}
        response = logged_in_client.post('/admin/maintenance/new', data=data)
        
        assert response.status_code == 302
        assert '/admin/maintenance' in response.headers['Location']
        assert "INSERT INTO mowingmaintenance" in mock_curs.execute.call_args[0][0]

def test_maintenance_delete(logged_in_client):
    """Test deleting a Maintenance task."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.mowing_maintenance.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.transaction.return_value.__enter__.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        response = logged_in_client.post('/admin/maintenance/1/delete')
        
        assert response.status_code == 302
        assert '/admin/maintenance' in response.headers['Location']
        assert "DELETE FROM mowingmaintenance" in mock_curs.execute.call_args[0][0]

def test_admin_html_responses_have_cache_control(logged_in_client):
    """Test that authenticated admin pages include Cache-Control headers."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['customername'] = 'Admin'
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.products.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        mock_curs.fetchall.return_value = []

        response = logged_in_client.get('/admin/products')
        
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store, no-cache, must-revalidate, max-age=0'
        assert response.headers['Pragma'] == 'no-cache'
        assert response.headers['Expires'] == '0'
        assert response.headers['Vary'] == 'Cookie'

def test_statistics_dashboard_access(logged_in_client):
    """Test accessing the statistics dashboard HTML page."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    response = logged_in_client.get('/admin/statistics/')
    assert response.status_code == 200
    assert b'Salgsstatistik' in response.data

def test_statistics_data_endpoint(logged_in_client):
    """Test the JSON data endpoint for Chart.js."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.statistics.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # Mock 2 rows (Label, Quantity, Revenue)
        mock_curs.fetchall.return_value = [
            ('Test Product A', 10, 50.00),
            ('Test Product B', 5, 25.00)
        ]
        
        response = logged_in_client.get('/admin/statistics/data?dimension=product')
        assert response.status_code == 200
        assert response.is_json
        
        data = response.get_json()
        assert 'labels' in data
        assert 'datasets' in data
        assert data['labels'] == ['Test Product A', 'Test Product B']
        assert data['datasets'][0]['data'] == [10, 5]  # Quantity
        assert data['datasets'][1]['data'] == [50.0, 25.0]  # Revenue

def test_statistics_export_endpoint(logged_in_client):
    """Test the CSV export endpoint."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.statistics.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # Mock 1 row (timestamp, soldproductname, quantity, soldsum, customername, transferred)
        from datetime import datetime
        dt = datetime(2023, 10, 1, 14, 30, 0)
        mock_curs.fetchall.return_value = [
            (dt, 'Test Product', 2, 40.50, 'Member X', True)
        ]
        
        response = logged_in_client.get('/admin/statistics/export?start_date=2023-10-01')
        assert response.status_code == 200
        assert response.mimetype == 'text/csv'
        assert b'attachment;filename=salg_raadata_2023-10-01_til_slut.csv' in response.headers.get('Content-Disposition').encode('utf-8')
        
        # Verify CSV content
        csv_content = response.data.decode('utf-8')
        assert '\ufeffTidspunkt;Produkt;Antal (Stk);Beløb (kr);Kunde;Overført til e-conomic' in csv_content
        assert '2023-10-01 14:30:00;Test Product;2;40,50;Member X;Ja' in csv_content
        
def test_statistics_timeline_endpoint(logged_in_client):
    """Test the JSON timeline endpoint for Chart.js."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.statistics.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # Mock 3 rows (sale_date, soldproductname, daily_quantity)
        mock_curs.fetchall.return_value = [
            ('2023-10-01', 'Cola', 5),
            ('2023-10-02', 'Cola', 2),
            ('2023-10-02', 'Fanta', 1)
        ]
        
        response = logged_in_client.get('/admin/statistics/data/timeline')
        assert response.status_code == 200
        assert response.is_json
        
        data = response.get_json()
        assert data['labels'] == ['2023-10-01', '2023-10-02']
        
        # We expect 2 datasets (Cola and Fanta)
        assert len(data['datasets']) == 2
        
        datasets_by_label = {ds['label']: ds for ds in data['datasets']}
        assert 'Cola' in datasets_by_label
        assert 'Fanta' in datasets_by_label
        
        # Cola: 5 on the 1st, 2 on the 2nd
        assert datasets_by_label['Cola']['data'] == [5, 2]
        # Fanta: 0 on the 1st, 1 on the 2nd
        assert datasets_by_label['Fanta']['data'] == [0, 1]

def test_statistics_timeline_endpoint_customer(logged_in_client):
    """Test the JSON timeline endpoint specifically for the 'customer' dimension."""
    with logged_in_client.session_transaction() as sess:
        sess['customerid'] = 42
        sess['admin_authenticated'] = True

    with patch('kiosk.routes.admin.statistics.get_db_connection') as mock_db:
        mock_conn = MagicMock()
        mock_curs = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_curs
        mock_db.return_value = mock_conn
        
        # Mock rows: sale_date, customername, daily_val (revenue)
        mock_curs.fetchall.return_value = [
            ('2023-11-01', 'Member A', 15.50),
            ('2023-11-02', 'Member A', 12.00)
        ]
        
        response = logged_in_client.get('/admin/statistics/data/timeline?dimension=customer')
        assert response.status_code == 200
        assert response.is_json
        
        data = response.get_json()
        assert data['labels'] == ['2023-11-01', '2023-11-02']
        assert len(data['datasets']) == 1
        assert data['datasets'][0]['label'] == 'Member A'
        # Validates that daily_val is correctly passed as float
        assert data['datasets'][0]['data'] == [15.50, 12.00]
