from prometheus_client import Counter, Gauge

cache_hit = Counter("cache_hit_total", "Total cache hits")
cache_miss = Counter("cache_miss_total", "Total cache misses")
cache_error = Counter("cache_error_total", "Total cache errors (Redis down etc.)")
cache_hit_rate = Gauge("cache_hit_rate", "Cache hit ratio")
