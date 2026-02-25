from prometheus_client import Counter

cache_hit = Counter("cache_hit_total", "Total cache hits")
cache_miss = Counter("cache_miss_total", "Total cache misses")
cache_error = Counter("cache_error_total", "Total cache errors (Redis down etc.)")