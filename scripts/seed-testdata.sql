INSERT INTO customers (customerid, customername, customergroup) VALUES
(100, 'Gæsteinstruktør', 30),
(123, 'Admin User', 99),
(456, 'Admin User 2', 99),
(1, 'Morten Dalgaard', 30),
(2, 'Christian Jensen', 30),
(3, 'Jesper Christensen', 1),
(4, 'Anette Nielsen', 1),
(5, 'Søren Møller', 1),
(6, 'Pia Mathiasen Hansen (Instruktør)', 1),
(7, 'Lars Pedersen', 1)
ON CONFLICT (customerid) DO NOTHING;

INSERT INTO products (productid, productname, itemprice, imagefilename) VALUES
(1, 'Coca Cola Zero', 15.00, 'placeholder.png'),
(2, 'Mars Bar', 10.00, 'placeholder.png'),
(3, 'Kaffe - Kop (alm)', 5.00, 'placeholder.png'),
(4, 'Faxe Kondi Booster', 20.00, 'placeholder.png'),
(5, 'Fransk Hotdog', 25.00, 'placeholder.png'),
(6, 'Sportscola', 15.00, 'placeholder.png'),
(7, 'Øl - Tuborg Classic', 15.00, 'placeholder.png')
ON CONFLICT (productid) DO NOTHING;

SELECT setval(pg_get_serial_sequence('products', 'productid'), COALESCE((SELECT MAX(productid) FROM products), 1));

INSERT INTO sales (customerid, productid, quantity, solditemprice, soldproductname) VALUES
(1, 1, 1, 15.00, 'Coca Cola Zero'),
(2, 2, 2, 10.00, 'Mars Bar'),
(3, 3, 1, 5.00, 'Kaffe - Kop (alm)'),
(4, 4, 4, 20.00, 'Faxe Kondi Booster'),
(5, 5, 1, 25.00, 'Fransk Hotdog'),
(6, 6, 1, 15.00, 'Sportscola'),
(7, 7, 3, 15.00, 'Øl - Tuborg Classic');

INSERT INTO mowingusers (customerid) VALUES
(1),(2),(3),(4),(5)
ON CONFLICT (customerid) DO NOTHING;

INSERT INTO mowingsections (id, section_name, cutting_time_in_h) VALUES
(1, '"Trekanten" + øko-kant', 1.5),
(2, 'Klubhus bagstykke (øko)', 0.5),
(3, 'Klubhus (øko)', 1),
(4, 'Bane 29 (øst)', 2),
(5, 'Bane 27 (øst)', 2),
(6, 'Bane 09 (vest)', 0.5),
(7, 'Bane 11 (vest)', 2)
ON CONFLICT (id) DO NOTHING;

SELECT setval('mowingsections_id_seq', (SELECT MAX(id) FROM mowingsections));

INSERT INTO mowingmaintenance (id, maintenance_type, interval_h, last_maintained_timestamp, user_id) VALUES
(1, 'Alle åg-ender på PTO-akslen', 25, CURRENT_TIMESTAMP, 1),
(2, 'PTO-slanger', 80, CURRENT_TIMESTAMP, 1),
(3, 'Hydraulikstempel', 40, CURRENT_TIMESTAMP, 1),
(4, 'Hjulets drejepunkt', 80, CURRENT_TIMESTAMP, 1),
(5, 'Hjulets aksel', 80, CURRENT_TIMESTAMP, 1),
(6, 'Kontrollér oliestanden i gearkasserne', 80, CURRENT_TIMESTAMP, 1),
(7, 'Udskift olien i gearkasserne', 400, CURRENT_TIMESTAMP, 1)
ON CONFLICT (id) DO NOTHING;

SELECT setval('mowingmaintenance_id_seq', (SELECT MAX(id) FROM mowingmaintenance));

INSERT INTO mowingactivities (user_id, timestamp, section_id, status) VALUES
(1, CURRENT_TIMESTAMP - INTERVAL '2 days', 1, '8/8'),
(1, CURRENT_TIMESTAMP - INTERVAL '5 days', 2, '8/8'),
(2, CURRENT_TIMESTAMP - INTERVAL '1 day', 3, '4/8'),
(3, CURRENT_TIMESTAMP - INTERVAL '10 days', 4, '8/8'),
(1, CURRENT_TIMESTAMP - INTERVAL '14 days', 5, '8/8'),
(4, CURRENT_TIMESTAMP - INTERVAL '3 days', 6, '8/8'),
(5, CURRENT_TIMESTAMP - INTERVAL '7 days', 7, '8/8'),
(2, CURRENT_TIMESTAMP, 3, '8/8'),
(1, CURRENT_TIMESTAMP - INTERVAL '20 days', 1, '8/8'),
(3, CURRENT_TIMESTAMP - INTERVAL '15 days', 2, '8/8');
