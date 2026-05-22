-- TEST: total_order_count
-- STATEMENT 1: SELECT COUNT(*) AS total FROM orders
total
3

-- TEST: orders_summary
-- STATEMENT 1: SELECT COUNT(*) AS total_orders FROM orders
total_orders
3

-- STATEMENT 2: SELECT customer_id, COUNT(*) AS order_count
customer_id,order_count
1,2
2,1

-- STATEMENT 3: SELECT MIN(amount) AS min_amt, MAX(amount) AS max_amt, SUM(amount) AS total_amt
min_amt,max_amt,total_amt
100.000000,200.000000,450.000000

-- TEST: orders_with_variables
-- STATEMENT 1: SET @threshold = 150.00
-- NO RESULT

-- STATEMENT 2: SELECT COUNT(*) AS orders_above_threshold
orders_above_threshold
2

-- STATEMENT 3: SELECT customer_id, SUM(amount) AS total
customer_id,total
1,200.000000
2,150.000000

-- TEST: call_order_summary_procedure
-- STATEMENT 1: DROP PROCEDURE IF EXISTS order_summary
-- NO RESULT

-- STATEMENT 2: CREATE PROCEDURE order_summary()
-- NO RESULT

-- STATEMENT 3: CALL order_summary()
total_orders
3

-- STATEMENT 4: CALL order_summary()
customer_id,order_count,total_amount
1,2,300.000000
2,1,150.000000

-- STATEMENT 5: CALL order_summary()
-- NO RESULT

-- TEST: call_categorise_orders
-- STATEMENT 1: DROP PROCEDURE IF EXISTS categorise_orders
-- NO RESULT

-- STATEMENT 2: CREATE PROCEDURE categorise_orders(IN threshold DECIMAL(10,2))
-- NO RESULT

-- STATEMENT 3: CREATE PROCEDURE categorise_orders(IN threshold DECIMAL(10,2))
id,amount,category
1,50.000000,low

-- STATEMENT 4: CREATE PROCEDURE categorise_orders(IN threshold DECIMAL(10,2))
-- NO RESULT

-- TEST: order_value_category
-- STATEMENT 1: SELECT id,
-- NO RESULT

-- TEST: future_feature
-- STATEMENT 1: SELECT 1
-- NO RESULT

