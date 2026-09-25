-- Optional initialization script for PostgreSQL
-- This file is automatically executed when the database is first created

-- Create extensions if needed
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Grant privileges (tables will be created by SQLAlchemy)
GRANT ALL PRIVILEGES ON DATABASE zwift_racing TO zwift_user;

-- You can add custom indexes here if needed
-- Example:
-- CREATE INDEX IF NOT EXISTS idx_rider_events_event_date ON rider_events(event_date);
-- CREATE INDEX IF NOT EXISTS idx_rider_events_query_zid ON rider_events(query_zid);
