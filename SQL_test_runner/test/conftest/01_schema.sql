-- SUITE_SETUP:
CREATE TABLE IF NOT EXISTS customers (
    id          INT PRIMARY KEY,
    name        VARCHAR(100),
    status      VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS orders (
    id          INT PRIMARY KEY,
    customer_id INT,
    amount      DECIMAL(10,2),
    order_date  DATE,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- SUITE_TEARDOWN:
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
