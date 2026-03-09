import csv
from io import StringIO
from flask import render_template, request, jsonify, Response, current_app
from ...database import get_db_connection
from . import bp, admin_required

@bp.route('/statistics/')
@admin_required
def statistics_dashboard():
    return render_template('admin/statistics.html')

def _build_statistics_query(start_date, end_date, dimension):
    """
    Builds the SQL query and parameters based on the selected dimension and date range.
    """
    
    # Base WHERE clause
    where_clause = "WHERE TRUE"
    params = []
    
    if start_date:
        where_clause += " AND CAST(sales.\"timestamp\" AS date) >= %s"
        params.append(start_date)
    if end_date:
        where_clause += " AND CAST(sales.\"timestamp\" AS date) <= %s"
        params.append(end_date)
        
    # Grouping logic
    limit_clause = ""
    if dimension == 'product':
        select_col = "sales.soldproductname AS label"
        group_by = "sales.soldproductname"
    elif dimension == 'customer':
        select_col = "customers.customername AS label"
        group_by = "customers.customername"
        limit_clause = "LIMIT 10"
    elif dimension == 'date':
        select_col = "CAST(sales.\"timestamp\" AS date) AS label"
        group_by = "CAST(sales.\"timestamp\" AS date)"
    else:
        # Fallback to product
        select_col = "sales.soldproductname AS label"
        group_by = "sales.soldproductname"
        
    query = f"""
        SELECT 
            {select_col},
            SUM(sales.quantity) as total_quantity,
            SUM(sales.soldsum) as total_revenue
        FROM sales
        JOIN customers USING (customerid)
        {where_clause}
        GROUP BY {group_by}
        ORDER BY total_revenue DESC
        {limit_clause}
    """
    
    return query, params

@bp.route('/statistics/data')
@admin_required
def statistics_data():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    dimension = request.args.get('dimension', 'product')
    
    query, params = _build_statistics_query(start_date, end_date, dimension)
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
        # Format for Chart.js
        labels = [str(r[0]) for r in rows]
        quantities = [r[1] for r in rows]
        revenues = [float(r[2]) for r in rows]
        
        return jsonify({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Antal Solgt (Stk)',
                    'data': quantities,
                    'backgroundColor': 'rgba(59, 130, 246, 0.5)', # Tailwind blue-500
                    'borderColor': 'rgb(59, 130, 246)',
                    'yAxisID': 'y-quantity'
                },
                {
                    'label': 'Omsætning (kr)',
                    'data': revenues,
                    'backgroundColor': 'rgba(34, 197, 94, 0.5)', # Tailwind green-500
                    'borderColor': 'rgb(34, 197, 94)',
                    'yAxisID': 'y-revenue'
                }
            ]
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching statistics: {e}")
        return jsonify({'error': 'Kunne ikke hente salgsdata'}), 500

@bp.route('/statistics/export')
@admin_required
def statistics_export():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    where_clause = "WHERE TRUE"
    params = []
    
    if start_date:
        where_clause += " AND CAST(sales.\"timestamp\" AS date) >= %s"
        params.append(start_date)
    if end_date:
        where_clause += " AND CAST(sales.\"timestamp\" AS date) <= %s"
        params.append(end_date)
        
    query = f"""
        SELECT 
            sales."timestamp",
            sales.soldproductname,
            sales.quantity,
            sales.soldsum,
            customers.customername,
            COALESCE(ecotransfer.transferred, FALSE) as transferred
        FROM sales
        JOIN customers USING (customerid)
        LEFT JOIN ecotransfer ON sales.id = ecotransfer.salesid
        {where_clause}
        ORDER BY sales."timestamp" DESC
    """
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
        # Create CSV in memory with semicolon delimiter for better Excel compatibility in DK
        si = StringIO()
        cw = csv.writer(si, delimiter=';')
        
        # Header
        cw.writerow(['Tidspunkt', 'Produkt', 'Antal (Stk)', 'Beløb (kr)', 'Kunde', 'Overført til e-conomic'])
        
        # Data
        for r in rows:
            # r = (timestamp, soldproductname, quantity, soldsum, customername, transferred)
            t = r[0].strftime('%Y-%m-%d %H:%M:%S') if r[0] else ''
            # Format soldsum with comma as decimal separator for Danish Excel
            soldsum_formatted = f"{float(r[3]):.2f}".replace('.', ',')
            # Translate boolean to Ja/Nej
            transferred_text = 'Ja' if r[5] else 'Nej'
            cw.writerow([t, r[1], r[2], soldsum_formatted, r[4], transferred_text])
            
        # Add UTF-8 BOM for Excel to recognize encoding correctly
        output = '\ufeff' + si.getvalue()
        
        filename = f"salg_raadata_{start_date or 'start'}_til_{end_date or 'slut'}.csv"
        
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        current_app.logger.error(f"Error exporting raw statistics: {e}")
        return "Kunne ikke generere CSV eksport", 500

@bp.route('/statistics/data/timeline')
@admin_required
def statistics_data_timeline():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    dimension = request.args.get('dimension', 'product')
    
    where_clause = "WHERE TRUE"
    params = []
    
    if start_date:
        where_clause += " AND CAST(sales.\"timestamp\" AS date) >= %s"
        params.append(start_date)
    if end_date:
        where_clause += " AND CAST(sales.\"timestamp\" AS date) <= %s"
        params.append(end_date)
        
    if dimension == 'customer':
        # Top 10 members by revenue in period
        query = f"""
            WITH top_customers AS (
                SELECT customerid
                FROM sales
                {where_clause}
                GROUP BY customerid
                ORDER BY SUM(soldsum) DESC
                LIMIT 10
            )
            SELECT 
                CAST(sales.\"timestamp\" AS date) as sale_date,
                customers.customername as category,
                SUM(sales.soldsum) as daily_val
            FROM sales
            JOIN customers USING (customerid)
            JOIN top_customers USING (customerid)
            {where_clause}
            GROUP BY sale_date, customers.customername
            ORDER BY sale_date ASC
        """
        # Params used twice in the CTE and Main Query where_clause
        params = params * 2
    else:
        # Default to product quantity
        query = f"""
            SELECT 
                CAST(sales.\"timestamp\" AS date) as sale_date,
                sales.soldproductname as category,
                SUM(sales.quantity) as daily_val
            FROM sales
            {where_clause}
            GROUP BY sale_date, sales.soldproductname
            ORDER BY sale_date ASC
        """
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
        if not rows:
             return jsonify({'labels': [], 'datasets': []})
                
        all_dates = sorted(list(set([str(r[0]) for r in rows])))
        categories = list(set([r[1] for r in rows]))
        
        import random
        datasets = []
        for cat in categories:
            random.seed(cat) 
            r, g, b = random.randint(50, 200), random.randint(50, 200), random.randint(50, 200)
            
            datasets.append({
                'label': cat,
                'data': [0] * len(all_dates),
                'backgroundColor': f'rgba({r}, {g}, {b}, 0.5)',
                'borderColor': f'rgb({r}, {g}, {b})',
                'tension': 0.1,
                'fill': False
            })
            
        cat_idx = {ds['label']: i for i, ds in enumerate(datasets)}
        
        for r in rows:
            date_str = str(r[0])
            category = r[1]
            val = float(r[2]) if dimension == 'customer' else r[2]
            
            date_index = all_dates.index(date_str)
            p_index = cat_idx[category]
            datasets[p_index]['data'][date_index] = val
        
        return jsonify({
            'labels': all_dates,
            'datasets': datasets
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching timeline statistics: {e}")
        return jsonify({'error': 'Kunne ikke hente salgsdata'}), 500
