"""Agglomerative clustering with silhouette-threshold selection."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .embedding import Embedder, cosine_similarity
from .schemas import CandidatePlan


@dataclass
class ClusterResult:
    labels: List[int]
    threshold: float
    silhouette: float
    dominant_cluster_id: int


def _distance(a: List[float], b: List[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


def _average_linkage_distance(cluster_a: List[int], cluster_b: List[int], vectors: List[List[float]]) -> float:
    pairs = [_distance(vectors[i], vectors[j]) for i in cluster_a for j in cluster_b]
    return sum(pairs) / len(pairs)


def _agglomerative(vectors: List[List[float]], threshold: float) -> List[int]:
    clusters: List[List[int]] = [[i] for i in range(len(vectors))]
    while len(clusters) > 1:
        best = None
        best_dist = float("inf")
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                d = _average_linkage_distance(clusters[i], clusters[j], vectors)
                if d < best_dist:
                    best = (i, j)
                    best_dist = d
        if best is None or best_dist > threshold:
            break
        i, j = best
        clusters[i] = clusters[i] + clusters[j]
        clusters.pop(j)
    labels = [0] * len(vectors)
    for cid, members in enumerate(clusters):
        for m in members:
            labels[m] = cid
    return labels


def _silhouette(labels: List[int], vectors: List[List[float]]) -> float:
    n = len(vectors)
    if n < 3 or len(set(labels)) < 2 or len(set(labels)) == n:
        return 0.0
    score = 0.0
    for i in range(n):
        own = [j for j in range(n) if labels[j] == labels[i] and j != i]
        other_clusters = sorted(set(labels) - {labels[i]})
        a = sum(_distance(vectors[i], vectors[j]) for j in own) / max(len(own), 1)
        b = min(
            sum(_distance(vectors[i], vectors[j]) for j in range(n) if labels[j] == c) /
            max(sum(1 for j in range(n) if labels[j] == c), 1)
            for c in other_clusters
        )
        score += (b - a) / max(a, b, 1e-9)
    return score / n


def cluster_candidate_plans(
    plans: List[CandidatePlan],
    threshold_candidates: List[float] | None = None,
    embedder: Embedder | None = None,
) -> ClusterResult:
    if threshold_candidates is None:
        threshold_candidates = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75]
    embedder = embedder or Embedder()
    vectors = embedder.encode([p.normalized_text() for p in plans])

    best_labels: List[int] = list(range(len(plans)))
    best_threshold = threshold_candidates[0]
    best_sil = -1.0
    for th in threshold_candidates:
        labels = _agglomerative(vectors, th)
        sil = _silhouette(labels, vectors)
        if sil > best_sil:
            best_labels, best_threshold, best_sil = labels, th, sil

    counts: Dict[int, int] = {}
    confidence: Dict[int, float] = {}
    for label, plan in zip(best_labels, plans):
        counts[label] = counts.get(label, 0) + 1
        confidence[label] = confidence.get(label, 0.0) + plan.confidence
    dominant = sorted(counts, key=lambda c: (counts[c], confidence[c] / counts[c]), reverse=True)[0]
    return ClusterResult(best_labels, best_threshold, best_sil, dominant)
