from framework.executor import _split_statements


# ---------------------------------------------------------------------------
# Basic splitting
# ---------------------------------------------------------------------------

def test_single_statement():
    result = _split_statements("SELECT 1")
    assert result == ["SELECT 1"]


def test_single_statement_with_semicolon():
    result = _split_statements("SELECT 1;")
    assert result == ["SELECT 1"]


def test_multiple_statements():
    result = _split_statements("SELECT 1; SELECT 2; SELECT 3;")
    assert result == ["SELECT 1", "SELECT 2", "SELECT 3"]


def test_empty_string():
    assert _split_statements("") == []


def test_only_whitespace():
    assert _split_statements("   \n   ") == []


def test_trailing_whitespace_stripped():
    result = _split_statements("  SELECT 1  ;  ")
    assert result == ["SELECT 1"]


# ---------------------------------------------------------------------------
# String literal handling
# ---------------------------------------------------------------------------

def test_semicolon_inside_single_quotes_not_split():
    result = _split_statements("SELECT 'a;b' FROM t;")
    assert result == ["SELECT 'a;b' FROM t"]


def test_semicolon_inside_double_quotes_not_split():
    result = _split_statements('SELECT "col;name" FROM t;')
    assert result == ['SELECT "col;name" FROM t']


def test_escaped_single_quote_string():
    result = _split_statements("INSERT INTO t VALUES ('it''s fine'); SELECT 1;")
    assert len(result) == 2
    assert "it''s fine" in result[0]
    assert result[1] == "SELECT 1"


# ---------------------------------------------------------------------------
# Comment handling
# ---------------------------------------------------------------------------

def test_semicolon_in_line_comment_not_split():
    sql = "-- comment; here\nSELECT 1;"
    result = _split_statements(sql)
    assert len(result) == 1
    assert "SELECT 1" in result[0]


def test_statement_after_comment():
    sql = "-- first comment\nSELECT 1;\n-- second comment\nSELECT 2;"
    result = _split_statements(sql)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# BEGIN...END — simple procedure body
# ---------------------------------------------------------------------------

def test_create_procedure_not_split():
    sql = """CREATE PROCEDURE get_orders()
BEGIN
    SELECT * FROM orders;
    SELECT COUNT(*) FROM orders;
END"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "SELECT * FROM orders" in result[0]
    assert "SELECT COUNT(*)" in result[0]


def test_create_procedure_followed_by_call():
    sql = """CREATE PROCEDURE p()
BEGIN
    SELECT 1;
END;
CALL p();"""
    result = _split_statements(sql)
    assert len(result) == 2
    assert "CREATE PROCEDURE" in result[0]
    assert "CALL p()" in result[1]


# ---------------------------------------------------------------------------
# BEGIN...END — nested control flow
# ---------------------------------------------------------------------------

def test_nested_if_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    IF x > 0 THEN
        SELECT 'positive';
    END IF;
    SELECT 'done';
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "END IF" in result[0]
    assert "SELECT 'done'" in result[0]


def test_nested_while_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    WHILE x > 0 DO
        SET x = x - 1;
    END WHILE;
    SELECT x;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "END WHILE" in result[0]
    assert "SELECT x" in result[0]


def test_nested_case_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    CASE x
        WHEN 1 THEN SELECT 'one';
        ELSE SELECT 'other';
    END CASE;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "END CASE" in result[0]


# ---------------------------------------------------------------------------
# Standalone BEGIN — transaction control (must NOT affect depth)
# ---------------------------------------------------------------------------

def test_standalone_begin_splits_correctly():
    sql = "BEGIN; SELECT 1; COMMIT;"
    result = _split_statements(sql)
    assert result == ["BEGIN", "SELECT 1", "COMMIT"]


def test_begin_transaction_followed_by_procedure():
    sql = """BEGIN;
SELECT 1;
COMMIT;
CREATE PROCEDURE p()
BEGIN
    SELECT 2;
END;"""
    result = _split_statements(sql)
    assert len(result) == 4
    assert result[0] == "BEGIN"
    assert result[1] == "SELECT 1"
    assert result[2] == "COMMIT"
    assert "CREATE PROCEDURE" in result[3]


# ---------------------------------------------------------------------------
# Mixed — real-world SUITE_SETUP with procedure creation
# ---------------------------------------------------------------------------

def test_suite_setup_with_create_procedure():
    sql = """CREATE TABLE orders (id INT, amount DECIMAL);

CREATE PROCEDURE order_summary()
BEGIN
    SELECT COUNT(*) AS total FROM orders;
    SELECT SUM(amount) AS total_amount FROM orders;
END;"""
    result = _split_statements(sql)
    assert len(result) == 2
    assert "CREATE TABLE" in result[0]
    assert "CREATE PROCEDURE" in result[1]
    assert "COUNT(*)" in result[1]
    assert "SUM(amount)" in result[1]


# ---------------------------------------------------------------------------
# BEGIN...END — CREATE FUNCTION
# ---------------------------------------------------------------------------

def test_create_function_not_split():
    sql = """CREATE FUNCTION get_discount(amount DECIMAL)
RETURNS DECIMAL
BEGIN
    DECLARE discount DECIMAL DEFAULT 0;
    IF amount > 100 THEN
        SET discount = amount * 0.1;
    END IF;
    RETURN discount;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "DECLARE discount" in result[0]
    assert "RETURN discount" in result[0]


def test_create_function_followed_by_select():
    sql = """CREATE FUNCTION double_it(x INT)
RETURNS INT
BEGIN
    RETURN x * 2;
END;
SELECT double_it(5);"""
    result = _split_statements(sql)
    assert len(result) == 2
    assert "CREATE FUNCTION" in result[0]
    assert "SELECT double_it(5)" in result[1]


# ---------------------------------------------------------------------------
# BEGIN...END — CREATE TRIGGER
# ---------------------------------------------------------------------------

def test_create_trigger_not_split():
    sql = """CREATE TRIGGER before_order_insert
BEFORE INSERT ON orders
FOR EACH ROW
BEGIN
    IF NEW.amount < 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Amount cannot be negative';
    END IF;
    SET NEW.created_at = NOW();
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "SIGNAL SQLSTATE" in result[0]
    assert "SET NEW.created_at" in result[0]


def test_create_trigger_followed_by_insert():
    sql = """CREATE TRIGGER trg_log
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    INSERT INTO audit_log VALUES (NEW.id, NOW());
END;
INSERT INTO orders VALUES (1, 1, 100.00);"""
    result = _split_statements(sql)
    assert len(result) == 2
    assert "CREATE TRIGGER" in result[0]
    assert "INSERT INTO orders" in result[1]


# ---------------------------------------------------------------------------
# BEGIN...END — deeply nested blocks
# ---------------------------------------------------------------------------

def test_if_inside_while_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    WHILE x > 0 DO
        IF x = 5 THEN
            SELECT 'five';
        END IF;
        SET x = x - 1;
    END WHILE;
    SELECT 'done';
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "END IF" in result[0]
    assert "END WHILE" in result[0]
    assert "SELECT 'done'" in result[0]


def test_loop_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    my_loop: LOOP
        SET x = x + 1;
        IF x >= 10 THEN
            LEAVE my_loop;
        END IF;
    END LOOP my_loop;
    SELECT x;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "LEAVE my_loop" in result[0]
    assert "END LOOP" in result[0]


def test_repeat_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    REPEAT
        SET x = x + 1;
    UNTIL x >= 10
    END REPEAT;
    SELECT x;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "END REPEAT" in result[0]
    assert "SELECT x" in result[0]


# ---------------------------------------------------------------------------
# BEGIN...END — case insensitive keywords
# ---------------------------------------------------------------------------

def test_lowercase_begin_end():
    sql = """create procedure p()
begin
    select 1;
    select 2;
end;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "select 1" in result[0]
    assert "select 2" in result[0]


def test_mixed_case_begin_end():
    sql = """Create Procedure p()
Begin
    Select 1;
End;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "Select 1" in result[0]


# ---------------------------------------------------------------------------
# BEGIN...END — semicolons in strings inside procedure body
# ---------------------------------------------------------------------------

def test_semicolon_in_string_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    INSERT INTO log VALUES ('step1; done');
    SELECT COUNT(*) FROM log;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "step1; done" in result[0]
    assert "SELECT COUNT(*)" in result[0]


# ---------------------------------------------------------------------------
# BEGIN...END — comments with semicolons inside procedure body
# ---------------------------------------------------------------------------

def test_comment_with_semicolon_inside_procedure():
    sql = """CREATE PROCEDURE p()
BEGIN
    -- step 1; insert data
    INSERT INTO t VALUES (1);
    -- step 2; query data
    SELECT * FROM t;
END;"""
    result = _split_statements(sql)
    assert len(result) == 1
    assert "INSERT INTO t" in result[0]
    assert "SELECT * FROM t" in result[0]


# ---------------------------------------------------------------------------
# BEGIN...END — procedure with parameters
# ---------------------------------------------------------------------------

def test_procedure_with_parameters():
    sql = """CREATE PROCEDURE get_by_customer(IN cust_id INT, OUT total INT)
BEGIN
    SELECT COUNT(*) INTO total
    FROM orders
    WHERE customer_id = cust_id;
END;
CALL get_by_customer(1, @total);
SELECT @total;"""
    result = _split_statements(sql)
    assert len(result) == 3
    assert "CREATE PROCEDURE" in result[0]
    assert "CALL get_by_customer" in result[1]
    assert "SELECT @total" in result[2]


# ---------------------------------------------------------------------------
# BEGIN...END — multiple procedures in one block
# ---------------------------------------------------------------------------

def test_two_procedures_are_two_statements():
    sql = """CREATE PROCEDURE proc_one()
BEGIN
    SELECT 1;
END;
CREATE PROCEDURE proc_two()
BEGIN
    SELECT 2;
END;"""
    result = _split_statements(sql)
    assert len(result) == 2
    assert "proc_one" in result[0]
    assert "proc_two" in result[1]


# ---------------------------------------------------------------------------
# CASE in SELECT — must NOT affect depth (not a compound block)
# ---------------------------------------------------------------------------

def test_case_in_select_not_treated_as_block():
    sql = """SELECT CASE WHEN amount > 100 THEN 'high' ELSE 'low' END AS level
FROM orders;
SELECT COUNT(*) FROM orders;"""
    result = _split_statements(sql)
    assert len(result) == 2
    assert "CASE WHEN" in result[0]
    assert "SELECT COUNT(*)" in result[1]
