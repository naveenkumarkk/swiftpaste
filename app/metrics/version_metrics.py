from prometheus_client import Counter

version_creations = Counter(
    "snippet_versions_created_total",
    "Number of snippet versions created"
)