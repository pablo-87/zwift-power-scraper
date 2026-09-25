import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, UniqueConstraint,BigInteger
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import insert
from dotenv import load_dotenv


load_dotenv()

# Build the connection string
DB_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

engine = create_engine(DB_URL)
Base = declarative_base()

class RiderProfile(Base):
    __tablename__ = 'rider_profiles'
    
    # Auto-incrementing primary key
    id = Column(Integer, primary_key=True)
    zid = Column(Integer, nullable=False, index=True)
    fetched_at = Column(DateTime, nullable=False)
    
    # Profile metrics
    cat = Column(String)
    racing_score = Column(Float)
    zpoints = Column(Float)
    country = Column(String)
    team = Column(String)
    zftp = Column(Float)
    weight = Column(Float)
    age = Column(String)
    
    # Highcharts JS Data
    watts_15s = Column(Integer)
    pct_15s = Column(Float)
    watts_1m = Column(Integer)
    pct_1m = Column(Float)
    watts_5m = Column(Integer)
    pct_5m = Column(Float)
    watts_20m = Column(Integer)
    pct_20m = Column(Float)

    # Prevent duplicate records for the same rider on the same timestamp
    __table_args__ = (UniqueConstraint('zid', 'fetched_at', name='uq_profile_fetch'),)


class RiderEvent(Base):
    __tablename__ = "rider_events"

    # Define columns in the exact order of the provided dataset
    DT_RowId = Column(String)
    ftp = Column(Integer)
    friend = Column(Integer)
    pt = Column(String)
    label = Column(Integer)
    zid = Column(Integer, primary_key=True)  # Primary Key Part 1
    pos = Column(Integer)
    position_in_cat = Column(Integer)
    name = Column(String)
    cp = Column(Integer)
    zwid = Column(Integer)
    res_id = Column(String, primary_key=True) # Primary Key Part 2 (Stored as String to prevent precision loss on values like '5703166.23')
    lag = Column(Integer)
    uid = Column(BigInteger)
    time = Column(Float)
    time_gun = Column(Float)
    gap = Column(Float)
    vtta = Column(String)
    vttat = Column(Float)
    male = Column(Integer)
    tid = Column(Integer)
    topen = Column(String)
    tname = Column(String)
    tc = Column(String)
    tbc = Column(String)
    tbd = Column(String)
    zeff = Column(Integer)
    category = Column(String)
    height = Column(Integer)
    flag = Column(String)
    avg_hr = Column(Integer)
    max_hr = Column(Integer)
    hrmax = Column(Integer)
    hrm = Column(Integer)
    weight = Column(Float)
    power_type = Column(Integer)
    display_pos = Column(Integer)
    src = Column(Integer)
    age = Column(String)
    zada = Column(Integer)
    note = Column(String)
    div = Column(Integer)
    divw = Column(Integer)
    skill = Column(Float)
    skill_b = Column(Float)
    skill_gain = Column(Float)
    np = Column(Integer)
    hrr = Column(Float)
    hreff = Column(Integer)
    avg_power = Column(Integer)
    avg_wkg = Column(Float)
    wkg_ftp = Column(Float)
    wftp = Column(Integer)
    wkg_guess = Column(Integer)
    wkg1200 = Column(Float)
    wkg300 = Column(Float)
    wkg120 = Column(Float)
    wkg60 = Column(Float)
    wkg30 = Column(Float)
    wkg15 = Column(Float)
    wkg5 = Column(Float)
    w1200 = Column(Float)
    w300 = Column(Float)
    w120 = Column(Float)
    w60 = Column(Float)
    w30 = Column(Float)
    w15 = Column(Float)
    w5 = Column(Float)
    is_guess = Column(Integer)
    upg = Column(Integer)
    penalty = Column(String)
    reg = Column(Integer)
    fl = Column(String)
    pts = Column(String)
    pts_pos = Column(String)
    info = Column(Integer)
    info_notes = Column(String)
    strike = Column(Integer)
    event_title = Column(String)
    f_t = Column(String)
    distance = Column(Float)
    event_date = Column(String)
    rt = Column(BigInteger)
    laps = Column(Integer)
    dur = Column(Integer)
    query_zid = Column(Integer)
    


def init_db():
    """Creates the tables in the PostgreSQL database if they do not exist."""
    Base.metadata.create_all(engine)


def psql_insert_do_nothing(table, conn, keys, data_iter):
    """
    Custom Pandas insertion method. 
    Uses PostgreSQL's native ON CONFLICT DO NOTHING to silently skip duplicates.
    """
    data = [dict(zip(keys, row)) for row in data_iter]
    if not data:
        return
    
    # Build a standard insert statement
    stmt = insert(table.table).values(data)
    
    # Convert it to an upsert ignoring conflicts
    on_conflict_stmt = stmt.on_conflict_do_nothing()
    
    conn.execute(on_conflict_stmt)
    
