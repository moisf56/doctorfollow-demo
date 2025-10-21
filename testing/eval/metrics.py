"""
Metrics tracking for iterative RAG development
Track performance improvements across iterations
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime


@dataclass
class QueryMetrics:
    """Metrics for a single query execution"""
    query_id: str
    query_text: str
    iteration: str  # "iter1_opensearch", "iter2_pgvector", etc.

    # Latency (milliseconds)
    total_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    kg_latency_ms: float = 0.0

    # Retrieval metrics
    num_chunks_retrieved: int = 0
    opensearch_top_score: float = 0.0
    pgvector_top_score: float = 0.0

    # Answer metrics
    answer_text: str = ""
    answer_length_chars: int = 0
    num_citations: int = 0
    citations_valid: bool = False

    # Function calling
    function_called: Optional[str] = None
    function_success: bool = False

    # KG metrics (Iteration 3+)
    kg_entities_found: int = 0
    kg_relationships_used: int = 0
    contradictions_detected: int = 0

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class IterationReport:
    """Aggregate report for an iteration"""
    iteration: str
    description: str
    total_queries: int

    # Average latencies
    avg_total_latency_ms: float
    avg_retrieval_latency_ms: float
    avg_llm_latency_ms: float

    # Retrieval quality
    avg_chunks_retrieved: float
    avg_opensearch_score: float
    avg_pgvector_score: float

    # Answer quality
    avg_answer_length: float
    avg_citations: float
    citation_accuracy_pct: float

    # Function calling
    function_call_rate_pct: float
    function_success_rate_pct: float

    # KG metrics
    avg_kg_entities: float = 0.0
    avg_kg_relationships: float = 0.0
    avg_contradictions: float = 0.0

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MetricsTracker:
    """
    Track and compare metrics across iterations

    Usage:
        tracker = MetricsTracker()

        # Track a query
        with tracker.track_query("q001", "What is amoxicillin?", "iter1") as m:
            # Your code
            results = search(...)
            m.num_chunks_retrieved = len(results)
            m.answer_text = generate(...)

        # Generate report
        report = tracker.generate_report("iter1", "OpenSearch only")
        tracker.print_report("iter1")

        # Compare iterations
        comparison = tracker.compare("iter1", "iter2")
    """

    def __init__(self, results_dir: str = "eval/results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.metrics: List[QueryMetrics] = []

    def track_query(self, query_id: str, query_text: str, iteration: str):
        """Context manager for tracking query execution"""
        return _QueryContext(self, query_id, query_text, iteration)

    def add_metric(self, metric: QueryMetrics):
        """Add completed metric"""
        self.metrics.append(metric)
        self._save_metric(metric)

    def _save_metric(self, metric: QueryMetrics):
        """Save individual query metric to JSON"""
        filename = self.results_dir / f"{metric.iteration}_{metric.query_id}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(asdict(metric), f, indent=2, ensure_ascii=False)

    def generate_report(self, iteration: str, description: str = "") -> IterationReport:
        """Generate aggregate report for an iteration"""
        iter_metrics = [m for m in self.metrics if m.iteration == iteration]

        if not iter_metrics:
            # Try loading from disk
            iter_metrics = self._load_metrics_from_disk(iteration)

        if not iter_metrics:
            raise ValueError(f"No metrics found for iteration: {iteration}")

        n = len(iter_metrics)

        report = IterationReport(
            iteration=iteration,
            description=description,
            total_queries=n,

            avg_total_latency_ms=sum(m.total_latency_ms for m in iter_metrics) / n,
            avg_retrieval_latency_ms=sum(m.retrieval_latency_ms for m in iter_metrics) / n,
            avg_llm_latency_ms=sum(m.llm_latency_ms for m in iter_metrics) / n,

            avg_chunks_retrieved=sum(m.num_chunks_retrieved for m in iter_metrics) / n,
            avg_opensearch_score=sum(m.opensearch_top_score for m in iter_metrics) / n,
            avg_pgvector_score=sum(m.pgvector_top_score for m in iter_metrics) / n,

            avg_answer_length=sum(m.answer_length_chars for m in iter_metrics) / n,
            avg_citations=sum(m.num_citations for m in iter_metrics) / n,
            citation_accuracy_pct=sum(1 for m in iter_metrics if m.citations_valid) / n * 100,

            function_call_rate_pct=sum(1 for m in iter_metrics if m.function_called) / n * 100,
            function_success_rate_pct=(
                sum(1 for m in iter_metrics if m.function_success) /
                max(1, sum(1 for m in iter_metrics if m.function_called)) * 100
            ),

            avg_kg_entities=sum(m.kg_entities_found for m in iter_metrics) / n,
            avg_kg_relationships=sum(m.kg_relationships_used for m in iter_metrics) / n,
            avg_contradictions=sum(m.contradictions_detected for m in iter_metrics) / n,
        )

        self._save_report(report)
        return report

    def _save_report(self, report: IterationReport):
        """Save iteration report"""
        filename = self.results_dir / f"REPORT_{report.iteration}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)

    def _load_metrics_from_disk(self, iteration: str) -> List[QueryMetrics]:
        """Load metrics from saved JSON files"""
        metrics = []
        pattern = f"{iteration}_q*.json"
        for filepath in self.results_dir.glob(pattern):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                metrics.append(QueryMetrics(**data))
        return metrics

    def compare(self, iter1: str, iter2: str) -> Dict[str, Any]:
        """Compare two iterations"""
        r1_path = self.results_dir / f"REPORT_{iter1}.json"
        r2_path = self.results_dir / f"REPORT_{iter2}.json"

        if not r1_path.exists() or not r2_path.exists():
            raise ValueError(f"Reports not found for {iter1} or {iter2}")

        with open(r1_path, 'r') as f:
            r1 = json.load(f)
        with open(r2_path, 'r') as f:
            r2 = json.load(f)

        comparison = {
            'baseline': iter1,
            'new': iter2,
            'improvements': {},
            'regressions': {},
            'neutral': {}
        }

        # Metrics to compare (metric_name, lower_is_better)
        metrics_to_compare = [
            ('avg_total_latency_ms', True),
            ('avg_retrieval_latency_ms', True),
            ('avg_llm_latency_ms', True),
            ('avg_chunks_retrieved', False),
            ('avg_opensearch_score', False),
            ('avg_pgvector_score', False),
            ('citation_accuracy_pct', False),
            ('function_success_rate_pct', False),
            ('avg_kg_entities', False),
            ('avg_contradictions', False),
        ]

        for metric, lower_is_better in metrics_to_compare:
            val1 = r1.get(metric, 0)
            val2 = r2.get(metric, 0)

            if val1 == 0 and val2 == 0:
                continue

            delta = val2 - val1
            delta_pct = (delta / val1 * 100) if val1 != 0 else 0

            result = {
                'before': round(val1, 2),
                'after': round(val2, 2),
                'delta': round(delta, 2),
                'delta_pct': round(delta_pct, 1)
            }

            # Classify as improvement/regression
            is_better = (delta < 0 if lower_is_better else delta > 0)
            threshold = 2.0  # 2% change threshold

            if abs(delta_pct) < threshold:
                comparison['neutral'][metric] = result
            elif is_better:
                comparison['improvements'][metric] = result
            else:
                comparison['regressions'][metric] = result

        # Save comparison
        filename = self.results_dir / f"COMPARE_{iter1}_vs_{iter2}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)

        return comparison

    def print_report(self, iteration: str):
        """Print formatted report to console"""
        report_path = self.results_dir / f"REPORT_{iteration}.json"

        if not report_path.exists():
            print(f"❌ No report found for: {iteration}")
            return

        with open(report_path, 'r') as f:
            r = json.load(f)

        print(f"\n{'='*70}")
        print(f"📊 ITERATION REPORT: {r['iteration']}")
        print(f"{'='*70}")
        print(f"Description: {r.get('description', 'N/A')}")
        print(f"Total Queries: {r['total_queries']}")
        print(f"\n{'─'*70}")
        print("⏱️  LATENCY")
        print(f"{'─'*70}")
        print(f"  Total:     {r['avg_total_latency_ms']:>8.1f} ms")
        print(f"  Retrieval: {r['avg_retrieval_latency_ms']:>8.1f} ms")
        print(f"  LLM:       {r['avg_llm_latency_ms']:>8.1f} ms")
        print(f"\n{'─'*70}")
        print("🔍 RETRIEVAL")
        print(f"{'─'*70}")
        print(f"  Chunks Retrieved: {r['avg_chunks_retrieved']:>6.1f}")
        print(f"  OpenSearch Score: {r['avg_opensearch_score']:>6.3f}")
        print(f"  pgvector Score:   {r['avg_pgvector_score']:>6.3f}")
        print(f"\n{'─'*70}")
        print("📝 ANSWER QUALITY")
        print(f"{'─'*70}")
        print(f"  Avg Length:        {r['avg_answer_length']:>6.0f} chars")
        print(f"  Avg Citations:     {r['avg_citations']:>6.1f}")
        print(f"  Citation Accuracy: {r['citation_accuracy_pct']:>6.1f}%")

        if r.get('avg_kg_entities', 0) > 0:
            print(f"\n{'─'*70}")
            print("🕸️  KNOWLEDGE GRAPH")
            print(f"{'─'*70}")
            print(f"  Entities Found:      {r['avg_kg_entities']:>6.1f}")
            print(f"  Relationships Used:  {r['avg_kg_relationships']:>6.1f}")
            print(f"  Contradictions:      {r['avg_contradictions']:>6.1f}")

        print(f"{'='*70}\n")

    def print_comparison(self, iter1: str, iter2: str):
        """Print formatted comparison"""
        comp_path = self.results_dir / f"COMPARE_{iter1}_vs_{iter2}.json"

        if not comp_path.exists():
            # Generate if doesn't exist
            self.compare(iter1, iter2)

        with open(comp_path, 'r') as f:
            c = json.load(f)

        print(f"\n{'='*70}")
        print(f"📈 COMPARISON: {c['baseline']} → {c['new']}")
        print(f"{'='*70}")

        if c['improvements']:
            print(f"\n✅ IMPROVEMENTS:")
            for metric, data in c['improvements'].items():
                arrow = "↓" if data['delta'] < 0 else "↑"
                print(f"  {metric:30s} {data['before']:>8.2f} → {data['after']:>8.2f} "
                      f"({arrow} {abs(data['delta_pct']):>5.1f}%)")

        if c['regressions']:
            print(f"\n❌ REGRESSIONS:")
            for metric, data in c['regressions'].items():
                arrow = "↓" if data['delta'] < 0 else "↑"
                print(f"  {metric:30s} {data['before']:>8.2f} → {data['after']:>8.2f} "
                      f"({arrow} {abs(data['delta_pct']):>5.1f}%)")

        print(f"{'='*70}\n")


class _QueryContext:
    """Context manager for tracking individual queries"""

    def __init__(self, tracker: MetricsTracker, query_id: str, query_text: str, iteration: str):
        self.tracker = tracker
        self.metric = QueryMetrics(query_id=query_id, query_text=query_text, iteration=iteration)
        self.start_time = 0

    def __enter__(self) -> QueryMetrics:
        self.start_time = time.time()
        return self.metric

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.metric.total_latency_ms = (time.time() - self.start_time) * 1000
        self.metric.answer_length_chars = len(self.metric.answer_text)
        self.tracker.add_metric(self.metric)
        return False


if __name__ == "__main__":
    # Demo
    print("=== Metrics Tracker Demo ===\n")

    tracker = MetricsTracker()

    # Simulate some queries
    for i in range(3):
        with tracker.track_query(f"q00{i+1}", f"Test query {i+1}", "demo") as m:
            time.sleep(0.05)
            m.num_chunks_retrieved = 5
            m.num_citations = 2
            m.citations_valid = True
            m.answer_text = "This is a test answer with citations [1], [2]."
            m.opensearch_top_score = 0.85

    report = tracker.generate_report("demo", "Demo iteration")
    tracker.print_report("demo")
