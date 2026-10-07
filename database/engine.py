import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import insert
from dotenv import load_dotenv

# Load environment variables (mapped via your CasaOS Docker volume)
load_dotenv()

# Build the connection string
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASS", "postgres")
DB_HOST = os.getenv("DB_HOST", "db") # 'db' if using a separate docker service, or host IP
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "zwift")

DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Initialize the SQLAlchemy engine and Base class
engine = create_engine(DATABASE_URI)
Base = declarative_base()

def init_db():
    """
    Creates the tables if they don't exist.
    We import models here inside the function to avoid circular import errors 
    (since models.py needs to import Base from this file).
    """
    from . import models
    Base.metadata.create_all(engine)

def psql_insert_do_nothing(table, conn, keys, data_iter):
    """
    Custom execution method for pandas to_sql().
    Utilizes PostgreSQL's native INSERT ... ON CONFLICT DO NOTHING,
    relying on the Primary Keys defined in models.py to ignore duplicate records.
    """
    data = [dict(zip(keys, row)) for row in data_iter]
    
    # Create the standard insert statement
    stmt = insert(table.table).values(data)
    
    # Append the DO NOTHING rule for primary key collisions
    on_conflict_stmt = stmt.on_conflict_do_nothing()
    
    # Execute
    conn.execute(on_conflict_stmt)