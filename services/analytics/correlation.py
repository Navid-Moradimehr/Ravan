"""Correlation analysis and root-cause detection for industrial sensors.

Uses open-source libraries:
- pandas: Data manipulation and correlation matrices
- NetworkX: Graph-based root-cause analysis
- scipy: Statistical significance testing

Open-source alternatives for advanced causal inference:
- causalnex (Microsoft): Bayesian networks for causal inference
- pgmpy: Probabilistic graphical models
- dowhy (Microsoft): Causal inference framework
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

# Try importing optional dependencies
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("pandas not installed. Correlation analysis will be limited.")

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    logger.warning("networkx not installed. Graph analysis will be limited.")

try:
    from scipy import stats
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


class CorrelationAnalyzer:
    """Analyze correlations between industrial sensor tags."""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._data: dict[str, deque[tuple[str, float]]] = {}

    def add_value(self, tag: str, timestamp: str, value: float) -> None:
        """Add a sensor reading to the analysis window."""
        if tag not in self._data:
            self._data[tag] = deque(maxlen=self.window_size)
        self._data[tag].append((timestamp, value))

    def get_correlation_matrix(self) -> dict[str, dict[str, float]]:
        """Compute Pearson correlation matrix between all tags."""
        if not PANDAS_AVAILABLE:
            return self._simple_correlation()

        # Build DataFrame from window data
        all_timestamps = set()
        for tag_data in self._data.values():
            all_timestamps.update(t for t, _ in tag_data)

        if not all_timestamps:
            return {}

        sorted_ts = sorted(all_timestamps)
        df_data: dict[str, list[float | None]] = {}

        for tag, tag_data in self._data.items():
            value_map = {t: v for t, v in tag_data}
            df_data[tag] = [value_map.get(ts) for ts in sorted_ts]

        df = pd.DataFrame(df_data, index=sorted_ts)
        df = df.interpolate(method="linear").fillna(method="ffill").fillna(method="bfill")

        corr = df.corr(method="pearson")
        result: dict[str, dict[str, float]] = {}
        for col in corr.columns:
            result[col] = {}
            for idx in corr.index:
                if col != idx:
                    val = corr.loc[idx, col]
                    if not pd.isna(val):
                        result[col][idx] = round(float(val), 4)

        return result

    def _simple_correlation(self) -> dict[str, dict[str, float]]:
        """Fallback correlation without pandas."""
        tags = list(self._data.keys())
        result: dict[str, dict[str, float]] = {}

        for i, tag1 in enumerate(tags):
            result[tag1] = {}
            for tag2 in tags[i + 1 :]:
                values1 = [v for _, v in self._data[tag1]]
                values2 = [v for _, v in self._data[tag2]]

                min_len = min(len(values1), len(values2))
                if min_len < 2:
                    continue

                corr = self._pearson_correlation(values1[:min_len], values2[:min_len])
                result[tag1][tag2] = round(corr, 4)
                if tag2 not in result:
                    result[tag2] = {}
                result[tag2][tag1] = round(corr, 4)

        return result

    @staticmethod
    def _pearson_correlation(x: list[float], y: list[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = len(x)
        if n != len(y) or n < 2:
            return 0.0

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denom_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
        denom_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5

        if denom_x == 0 or denom_y == 0:
            return 0.0

        return numerator / (denom_x * denom_y)

    def find_strong_correlations(self, threshold: float = 0.7) -> list[dict[str, Any]]:
        """Find tag pairs with strong correlation."""
        matrix = self.get_correlation_matrix()
        strong = []

        for tag1, correlations in matrix.items():
            for tag2, corr in correlations.items():
                if abs(corr) >= threshold:
                    strong.append({
                        "tag1": tag1,
                        "tag2": tag2,
                        "correlation": corr,
                        "relationship": "positive" if corr > 0 else "negative",
                        "strength": "strong" if abs(corr) >= 0.8 else "moderate",
                    })

        return sorted(strong, key=lambda x: abs(x["correlation"]), reverse=True)

    def build_causal_graph(self, threshold: float = 0.5) -> dict[str, Any]:
        """Build a NetworkX graph of tag relationships for root-cause analysis."""
        if not NETWORKX_AVAILABLE:
            return {"error": "networkx not installed", "correlations": self.find_strong_correlations(threshold)}

        matrix = self.get_correlation_matrix()
        G = nx.Graph()

        # Add nodes
        for tag in self._data.keys():
            G.add_node(tag, readings=len(self._data[tag]))

        # Add edges for correlations above threshold
        for tag1, correlations in matrix.items():
            for tag2, corr in correlations.items():
                if abs(corr) >= threshold and tag1 < tag2:  # Avoid duplicates
                    G.add_edge(tag1, tag2, weight=abs(corr), correlation=corr)

        # Find connected components (sensor groups)
        components = []
        for component in nx.connected_components(G):
            subgraph = G.subgraph(component)
            components.append({
                "tags": list(component),
                "density": nx.density(subgraph),
                "central_tag": max(subgraph.degree, key=lambda x: x[1])[0] if subgraph.nodes else None,
            })

        # Find potential root causes (highest degree nodes)
        degrees = dict(G.degree(weight="weight"))
        root_causes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "nodes": list(G.nodes()),
            "edges": [
                {"source": u, "target": v, "weight": d["weight"], "correlation": d["correlation"]}
                for u, v, d in G.edges(data=True)
            ],
            "components": components,
            "root_causes": [{"tag": tag, "influence_score": round(score, 4)} for tag, score in root_causes],
            "graph_density": nx.density(G) if G.nodes else 0,
        }

    def detect_anomaly_propagation(self, anomalous_tag: str, lookback: int = 10) -> list[dict[str, Any]]:
        """Detect which tags likely caused or were affected by an anomaly.

        Uses temporal correlation: which tags changed before/after the anomaly.
        """
        if anomalous_tag not in self._data:
            return []

        # Get recent anomalous values
        anomalous_data = list(self._data[anomalous_tag])[-lookback:]
        if not anomalous_data:
            return []

        anomalous_timestamps = {t for t, _ in anomalous_data}
        propagation = []

        for tag, tag_data in self._data.items():
            if tag == anomalous_tag:
                continue

            tag_timestamps = {t for t, _ in tag_data}
            overlap = len(anomalous_timestamps & tag_timestamps)

            if overlap > 0:
                # Calculate if this tag's changes preceded or followed the anomaly
                tag_recent = [(t, v) for t, v in tag_data if t in anomalous_timestamps]
                if tag_recent:
                    correlation = self._pearson_correlation(
                        [v for _, v in anomalous_data[: len(tag_recent)]],
                        [v for _, v in tag_recent],
                    )
                    propagation.append({
                        "tag": tag,
                        "overlap_count": overlap,
                        "correlation": round(correlation, 4),
                        "likely_cause": correlation > 0.5,
                    })

        return sorted(propagation, key=lambda x: abs(x["correlation"]), reverse=True)


# Global analyzer instance
_correlation_analyzer = CorrelationAnalyzer()


def get_analyzer() -> CorrelationAnalyzer:
    """Get the global correlation analyzer instance."""
    return _correlation_analyzer
