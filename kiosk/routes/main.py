
from flask import Blueprint, render_template, redirect, url_for, session, current_app, flash, request
from ..database import get_db_connection
from . import login_required
import psycopg
import decimal

bp = Blueprint('main', __name__)

@bp.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    customerid = session['customerid']
    customername = session['customername']

    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                curs.execute("SELECT * FROM products where disabled = false ORDER BY sorting")
                products = curs.fetchall()
                
                curs.execute("SELECT * from purchasehistory where customerid = %s ORDER BY id DESC LIMIT 50", (customerid,))
                purchasehistory = curs.fetchall()
                
                # Grass mowing addon
                curs.execute("SELECT 1 FROM mowingusers WHERE customerid = %s", (customerid,))
                greenteam_member = curs.fetchone() is not None
                
        return render_template('index.html', customername=customername, products=products, purchasehistory=purchasehistory, greenteam=greenteam_member, cart=session.get('cart', {}))
    except Exception as e:
        current_app.logger.error(f"Database error on index: {e}")
        return render_template('index.html', customername=customername, products=[], purchasehistory=[], greenteam=False, cart={}, error='Systemfejl: Kunne ikke forbinde til databasen.')

@bp.route('/add_to_cart/<int:productid>')
@login_required
def add_to_cart(productid):
    try:
        cart = session.get('cart', {})
        if str(productid) not in cart:
            with get_db_connection() as conn:
                with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                    curs.execute("SELECT itemprice, productname FROM products where productid = %s", (productid,))
                    product = curs.fetchone()
            if product:
                item = {'itemprice': product['itemprice'], 'productname': product['productname'], 'quantity': 1 }
                cart[str(productid)] = item
        else:
            cart[str(productid)]['quantity'] += 1
        session['cart'] = cart
    except Exception as e:
        current_app.logger.error(f"Database error adding to cart: {e}")

    if request.args.get('ajax') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('partials/cart_table.html', cart=session.get('cart', {}))
    return redirect(url_for('main.index'))

@bp.route('/remove_from_cart/<int:productid>')
@login_required
def remove_from_cart(productid):
    cart = session.get('cart', {})
    key = str(productid)
    if key in cart:
        cart[key]['quantity'] -= 1
        if cart[key]['quantity'] <= 0:
            del cart[key]
        session['cart'] = cart
        
    if request.args.get('ajax') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('partials/cart_table.html', cart=session.get('cart', {}))
    return redirect(url_for('main.index'))

@bp.route('/checkout', methods=['POST'])
@login_required
def checkout():
    customerid = session.get('customerid')
    cart = session.get('cart', {})
    if customerid and cart:
        try:
            # Insert the sale records into the database
            with get_db_connection() as conn:
                with conn.transaction(): 
                    with conn.cursor() as curs:
                        for productid, details in cart.items():
                            solditemprice = decimal.Decimal(details['itemprice'])
                            curs.execute("INSERT INTO sales (customerid, productid, quantity, solditemprice, soldproductname) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                                   (customerid, int(productid), details['quantity'], solditemprice, details['productname']))
                            salesid = curs.fetchone()[0] # Fetch scalar
                            curs.execute("INSERT INTO ecotransfer (salesid) VALUES (%s)",(salesid,))
            session.clear()
            session['purchase'] = 1
            return render_template('purchase.html', purchase=1)
        except Exception as e:
            current_app.logger.error(f"Checkout failed for customer {customerid}: {e}")
            session.clear()
            flash('Fejl ved køb - Køb IKKE gennemført', 'error')
            return redirect(url_for('auth.login'))
    else:
        session.clear()
        flash('Fejl ved køb - Køb IKKE gennemført', 'error')
        return redirect(url_for('auth.login'))

@bp.route('/history')
@login_required
def history():
    customerid = session['customerid']
    customername = session['customername']

    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=psycopg.rows.dict_row) as curs:
                # Fetch more history since we have a full page for it
                curs.execute("SELECT * from purchasehistory where customerid = %s ORDER BY id DESC LIMIT 100", (customerid,))
                purchasehistory = curs.fetchall()
                
        return render_template('history.html', customername=customername, purchasehistory=purchasehistory)
    except Exception as e:
        current_app.logger.error(f"Database error on history: {e}")
        return render_template('history.html', customername=customername, purchasehistory=[], error='Systemfejl: Kunne ikke forbinde til databasen.')

