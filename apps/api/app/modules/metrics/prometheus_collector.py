"""
Prometheus Metrics Collector
============================
Comprehensive metrics exporter for:
- API requests & latency histograms
- Database queries & connection pools
- Redis cache hits/misses & latency
- Celery Queue backlogs & job durations
- Search query & autocomplete latencies
- AI token usage, costs, and inference durations per Organization
"""
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PrometheusMetricsCollector:
    """Enterprise Prometheus metrics registry and exporter."""

    def __init__(self):
        # HTTP Metrics
        self.http_requests_total: Dict[str, int] = {} # "method:path:status" -> count
        self.http_request_duration_sum: float = 0.0
        self.http_request_count: int = 0

        # DB Metrics
        self.db_queries_total: int = 0
        self.db_slow_queries_total: int = 0
        self.db_query_duration_sum: float = 0.0

        # Redis Metrics
        self.redis_cache_hits: int = 0
        self.redis_cache_misses: int = 0

        # Queue Metrics
        self.queue_jobs_total: Dict[str, int] = {} # "queue:status" -> count

        # Search Metrics
        self.search_queries_total: int = 0
        self.search_duration_sum: float = 0.0

        # AI Metrics per Org
        self.ai_requests_total: int = 0
        self.ai_prompt_tokens_total: Dict[str, int] = {} # "org_id" -> count
        self.ai_completion_tokens_total: Dict[str, int] = {} # "org_id" -> count
        self.ai_cost_usd_total: Dict[str, float] = {} # "org_id" -> cost

    def record_http_request(self, method: str, path: str, status: int, duration_seconds: float) -> None:
        key = f'{method}:{path}:{status}'
        self.http_requests_total[key] = self.http_requests_total.get(key, 0) + 1
        self.http_request_count += 1
        self.http_request_duration_sum += duration_seconds

    def record_db_query(self, duration_seconds: float, is_slow: bool = False) -> None:
        self.db_queries_total += 1
        self.db_query_duration_sum += duration_seconds
        if is_slow:
            self.db_slow_queries_total += 1

    def record_cache_hit(self) -> None:
        self.redis_cache_hits += 1

    def record_cache_miss(self) -> None:
        self.redis_cache_misses += 1

    def record_queue_job(self, queue_name: str, status: str) -> None:
        key = f'{queue_name}:{status}'
        self.queue_jobs_total[key] = self.queue_jobs_total.get(key, 0) + 1

    def record_search_query(self, duration_seconds: float) -> None:
        self.search_queries_total += 1
        self.search_duration_sum += duration_seconds

    def record_ai_usage(
        self, organization_id: str, prompt_tokens: int, completion_tokens: int, cost_usd: float
    ) -> None:
        self.ai_requests_total += 1
        self.ai_prompt_tokens_total[organization_id] = self.ai_prompt_tokens_total.get(organization_id, 0) + prompt_tokens
        self.ai_completion_tokens_total[organization_id] = self.ai_completion_tokens_total.get(organization_id, 0) + completion_tokens
        self.ai_cost_usd_total[organization_id] = round(self.ai_cost_usd_total.get(organization_id, 0.0) + cost_usd, 6)

    def export_prometheus_text(self) -> str:
        """Exports metrics in standard Prometheus exposition format."""
        lines = []

        # HTTP Requests Total
        lines.append("# HELP http_requests_total Total number of HTTP requests processed")
        lines.append("# TYPE http_requests_total counter")
        for key, count in self.http_requests_total.items():
            method, path, status = key.split(":")
            lines.append(f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

        # HTTP Average Latency
        avg_http_latency = (self.http_request_duration_sum / self.http_request_count) if self.http_request_count > 0 else 0.0
        lines.append("\n# HELP http_request_duration_avg_seconds Average request duration")
        lines.append("# TYPE http_request_duration_avg_seconds gauge")
        lines.append(f"http_request_duration_avg_seconds {avg_http_latency:.4f}")

        # DB Metrics
        lines.append("\n# HELP db_queries_total Total database queries executed")
        lines.append("# TYPE db_queries_total counter")
        lines.append(f"db_queries_total {self.db_queries_total}")
        lines.append("db_slow_queries_total " + str(self.db_slow_queries_total))

        # Cache Metrics
        lines.append("\n# HELP redis_cache_hits_total Total cache hits")
        lines.append("# TYPE redis_cache_hits_total counter")
        lines.append(f"redis_cache_hits_total {self.redis_cache_hits}")
        lines.append(f"redis_cache_misses_total {self.redis_cache_misses}")

        # AI Usage Metrics per Org
        lines.append("\n# HELP ai_prompt_tokens_total Total AI prompt tokens consumed per org")
        lines.append("# TYPE ai_prompt_tokens_total counter")
        for org, count in self.ai_prompt_tokens_total.items():
            lines.append(f'ai_prompt_tokens_total{{organization_id="{org}"}} {count}')

        lines.append("\n# HELP ai_cost_usd_total Total AI spend in USD per org")
        lines.append("# TYPE ai_cost_usd_total counter")
        for org, cost in self.ai_cost_usd_total.items():
            lines.append(f'ai_cost_usd_total{{organization_id="{org}"}} {cost:.6f}')

        return "\n".join(lines) + "\n"


# Global Prometheus collector singleton
metrics = PrometheusMetricsCollector()
