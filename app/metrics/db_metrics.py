import time
from sqlalchemy import event
from prometheus_client import Histogram, Counter
from app.core.config import settings

db_query_latency = Histogram(
    "db_query_latency_seconds",
    "Database query latency",
    ["operation"],
    buckets=(0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2),
)


db_slow_queries = Counter(
    "db_slow_queries_total", "Queries slower than threshold", ["operation"]
)


def setup_db_metrics(engine):
    # engine.sync_engine-> This is required because async SQLAlchemy wraps a sync engine internally.
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):

        start_time = conn.info["query_start_time"].pop(-1)
        duration = time.perf_counter() - start_time

        operation = statement.lstrip().split(" ", 1)[0].upper()
        db_query_latency.labels(operation=operation).observe(duration)

        if duration > settings.PROMETHEUS_DB_SLOWQUERY_THRESHOLD:
            db_slow_queries.labels(operation=operation).inc()
