from sqlalchemy import create_engine
import pandas as pd

events_results = pd.read_csv('data/zpwr_events_results_2023-01-04.csv')
events_info = pd.read_csv('data/zpwr_events_info_2023-01-04.csv')

engine = create_engine("postgresql://postgres:tr0t5kyvgn@localhost/ZWIFT_POWER")

events_results.to_sql(
    "event_results",
    engine,
    if_exists="append",
    index=False
)

events_info.to_sql(
    "event_info",
    engine,
    if_exists="append",
    index=False
)

