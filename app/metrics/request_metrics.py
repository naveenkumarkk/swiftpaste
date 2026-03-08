from prometheus_client import Counter, Histogram

request_count = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)

request_errors = Counter(
    "http_request_errors_total", "Total HTTP errors", ["method", "endpoint"]
)

request_latency = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

request_size = Histogram(
    "http_request_size_bytes",
    "Request payload size"
)

response_size = Histogram(
    "http_response_size_bytes",
    "Response payload size"
)