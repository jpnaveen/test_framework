-- SUITE_SETUP:
INSERT INTO customers VALUES (1, 'Alice', 'active'),
                             (2, 'Bob',   'active'),
                             (3, 'Carol', 'inactive');

-- SUITE_TEARDOWN:
DELETE FROM customers;
