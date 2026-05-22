-- SUITE_SETUP:
CREATE TABLE IF NOT EXISTS orders (
    id          INT PRIMARY KEY,
    customer_id INT,
    amount      DECIMAL(10,2),
    order_date  DATE
);

-- SUITE_TEARDOWN:
DROP TABLE IF EXISTS orders;

-- -----------------------------------------------------------------------
-- Single SELECT — simplest case
-- -----------------------------------------------------------------------

-- TAGS: smoke, orders
-- TEST: total_order_count
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
SELECT COUNT(*) AS total FROM orders;
-- TEARDOWN:
DELETE FROM orders;

-- -----------------------------------------------------------------------
-- Multiple SELECTs in one QUERY block
-- Each SELECT becomes its own STATEMENT block in .res and .exp
-- All are compared pairwise against the expected file
-- -----------------------------------------------------------------------

-- TAGS: orders
-- TEST: orders_summary
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
SELECT COUNT(*) AS total_orders FROM orders;

SELECT customer_id, COUNT(*) AS order_count
FROM orders
GROUP BY customer_id
ORDER BY customer_id;

SELECT MIN(amount) AS min_amt, MAX(amount) AS max_amt, SUM(amount) AS total_amt
FROM orders;
-- TEARDOWN:
DELETE FROM orders;

-- -----------------------------------------------------------------------
-- Mixed statements — SET, INSERT, multiple SELECTs
-- -----------------------------------------------------------------------

-- TAGS: orders
-- TEST: orders_with_variables
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
SET @threshold = 150.00;

SELECT COUNT(*) AS orders_above_threshold
FROM orders
WHERE amount >= @threshold;

SELECT customer_id, SUM(amount) AS total
FROM orders
WHERE amount >= @threshold
GROUP BY customer_id;
-- TEARDOWN:
DELETE FROM orders;

-- -----------------------------------------------------------------------
-- Stored procedure — CREATE in QUERY, CALL result captured
-- Verifies BEGIN...END body is not split on semicolons
-- -----------------------------------------------------------------------

-- TAGS: orders, procedures
-- TEST: call_order_summary_procedure
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
DROP PROCEDURE IF EXISTS order_summary;

CREATE PROCEDURE order_summary()
BEGIN
    -- total count across all customers
    SELECT COUNT(*) AS total_orders FROM orders;

    -- breakdown per customer
    SELECT customer_id,
           COUNT(*)    AS order_count,
           SUM(amount) AS total_amount
    FROM orders
    GROUP BY customer_id
    ORDER BY customer_id;
END;

CALL order_summary();
-- TEARDOWN:
DELETE FROM orders;
DROP PROCEDURE IF EXISTS order_summary;

-- -----------------------------------------------------------------------
-- Stored procedure with IF...END IF inside BEGIN...END
-- Verifies nested control flow does not split the procedure body
-- -----------------------------------------------------------------------

-- TAGS: orders, procedures
-- TEST: call_categorise_orders
-- SETUP:
INSERT INTO orders VALUES (1, 1, 50.00,  '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
DROP PROCEDURE IF EXISTS categorise_orders;

CREATE PROCEDURE categorise_orders(IN threshold DECIMAL(10,2))
BEGIN
    -- high value orders
    IF threshold > 0 THEN
        SELECT id, amount, 'high' AS category
        FROM orders
        WHERE amount >= threshold
        ORDER BY id;
    END IF;

    -- low value orders
    SELECT id, amount, 'low' AS category
    FROM orders
    WHERE amount < threshold
    ORDER BY id;
END;

CALL categorise_orders(100.00);
-- TEARDOWN:
DELETE FROM orders;
DROP PROCEDURE IF EXISTS categorise_orders;

-- -----------------------------------------------------------------------
-- CASE expression inside a SELECT (not a compound block)
-- Verifies CASE in SELECT does not affect BEGIN...END depth
-- -----------------------------------------------------------------------

-- TAGS: orders
-- TEST: order_value_category
-- SETUP:
INSERT INTO orders VALUES (1, 1,  50.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
SELECT id,
       amount,
       CASE
           WHEN amount >= 200 THEN 'premium'
           WHEN amount >= 100 THEN 'standard'
           ELSE 'basic'
       END AS category
FROM orders
ORDER BY id;
-- TEARDOWN:
DELETE FROM orders;

-- -----------------------------------------------------------------------
-- SET variable + comment with semicolon in comment text
-- Verifies -- comments inside QUERY are not split on semicolons
-- -----------------------------------------------------------------------

-- TAGS: orders
-- TEST: filtered_orders_with_comment
-- SETUP:
INSERT INTO orders VALUES (1, 1, 100.00, '2024-01-01'),
                          (2, 1, 200.00, '2024-01-02'),
                          (3, 2, 150.00, '2024-01-03');
-- QUERY:
-- set minimum amount; adjust as needed per environment
SET @min_amount = 100.00;

SELECT customer_id, COUNT(*) AS order_count
FROM orders
WHERE amount >= @min_amount
GROUP BY customer_id
ORDER BY customer_id;
-- TEARDOWN:
DELETE FROM orders;

-- -----------------------------------------------------------------------
-- SKIP example
-- -----------------------------------------------------------------------

-- SKIP: feature not yet deployed
-- TEST: future_feature
-- QUERY:
SELECT 1;
