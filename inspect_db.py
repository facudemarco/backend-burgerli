from sqlalchemy import text, inspect
from Database.getConnection import engine

def inspect_table():
    inspector = inspect(engine)
    columns = inspector.get_columns('fries_main_imgs')
    for column in columns:
        print(f"Column: {column['name']}, Type: {column['type']}")

if __name__ == "__main__":
    inspect_table()
