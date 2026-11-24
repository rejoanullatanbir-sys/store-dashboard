
"""Store Dashboard - a small CLI that reads and writes the course database."""
import os
import sys
 
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
 
load_dotenv()  # reads DATABASE_URL from the .env file
 
 
def get_engine():
    """Create and return a SQLAlchemy engine from DATABASE_URL."""
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit("ERROR: DATABASE_URL is missing. Add it to your .env file.")
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # test that the connection works
    except Exception as error:
        sys.exit(f"ERROR: Could not connect to the database.\n{error}")
    return engine
 
 
def store_report(engine):
    """Print counts, the catalog, and the top 3 customers."""
    with engine.connect() as conn:
        users = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        products = conn.execute(text("SELECT COUNT(*) FROM products")).scalar()
        orders = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar()
 
        catalog = conn.execute(
            text("SELECT name, price, stock FROM products ORDER BY name")
        ).all()
 
        top_customers = conn.execute(text("""
            SELECT u.email, SUM(o.quantity) AS items
            FROM users u
            JOIN orders o ON o.user_id = u.id
            GROUP BY u.email
            ORDER BY items DESC
            LIMIT 3
        """)).all()
 
    print("\n=== Store Dashboard ===")
    print(f"Users: {users} | Products: {products} | Orders: {orders}")
 
    print("\nCatalog:")
    for name, price, stock in catalog:
        print(f"  {name:<28} ${price:>7.2f}   (stock {stock})")
 
    print("\nTop customers:")
    for email, items in top_customers:
        print(f"  {email:<22} - {items} items")
    print()
 
 
def add_product(engine, name, category, price, stock):
    """INSERT a product and return its new id."""
    with engine.begin() as conn:  # begin() commits automatically at the end
        new_id = conn.execute(
            text("""
                INSERT INTO products (name, category, price, stock)
                VALUES (:name, :category, :price, :stock)
                RETURNING id
            """),
            {"name": name, "category": category, "price": price, "stock": stock},
        ).scalar()
    return new_id
 
 
def place_order(engine, email, product_name, quantity):
    """Create an order and decrement stock in one transaction."""
    with engine.begin() as conn:  # commits on success, rolls back on any error
        user_id = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": email},
        ).scalar()
        if user_id is None:
            raise ValueError(f"No user with email {email}")
 
        product = conn.execute(
            text("SELECT id, stock FROM products WHERE name = :name"),
            {"name": product_name},
        ).first()
        if product is None:
            raise ValueError(f"No product named {product_name}")
 
        if product.stock < quantity:
            # Raising an error inside begin() rolls everything back
            raise ValueError(f"Not enough stock (only {product.stock} left)")
 
        order_id = conn.execute(
            text("""
                INSERT INTO orders (user_id, product_id, quantity)
                VALUES (:user_id, :product_id, :quantity)
                RETURNING id
            """),
            {"user_id": user_id, "product_id": product.id, "quantity": quantity},
        ).scalar()
 
        conn.execute(
            text("UPDATE products SET stock = stock - :quantity WHERE id = :id"),
            {"quantity": quantity, "id": product.id},
        )
    return order_id
 
 
def main():
    engine = get_engine()
    store_report(engine)
 
    while True:
        choice = input("1) Add a product  2) Place an order  3) Quit\nChoose: ")
        try:
            if choice == "1":
                name = input("Name: ")
                category = input("Category: ")
                price = float(input("Price: "))
                stock = int(input("Stock: "))
                new_id = add_product(engine, name, category, price, stock)
                print(f"Product added with id {new_id}\n")
            elif choice == "2":
                email = input("User email: ")
                product_name = input("Product name: ")
                quantity = int(input("Quantity: "))
                order_id = place_order(engine, email, product_name, quantity)
                print(f"Order placed with id {order_id}\n")
            elif choice == "3":
                break
            else:
                print("Please choose 1, 2 or 3.\n")
        except ValueError as error:
            print(f"Refused: {error}\n")
        except Exception as error:
            print(f"Database error, nothing was saved: {error}\n")
 
 
if __name__ == "__main__":
    main()
