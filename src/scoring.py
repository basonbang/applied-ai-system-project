"""
Hybrid scorer: mode-specific weighted combinations of retrieval signals.
TODO: implement per-mode weight configs in hybrid_score.
"""

import numpy as np


def cosine_similarity(a: list, b: list) -> float:
    """Cosine similarity between two equal-length vectors; returns 0.0 if either has zero magnitude."""

    # Convert to numpy arrays for efficient computation, then calculate the magnitude of each vector
    va = np.asarray(a, dtype=float)
    vb = np.asarray(b, dtype=float)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)

    # Check for zero magnitude vectors to avoid division by zero; similarity is 0 in that case
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def confidence_label(score: float) -> str:
    """Returns 'High' / 'Medium' / 'Low' based on score thresholds."""
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Medium"
    return "Low"


def hybrid_score(mode: str, playlist_vector: list, query_vector: list, **signals) -> float:
    """
    Compute weighted hybrid score for a playlist given the input mode.
    Modes: 'playlist', 'vibe', 'song'. All signal values in [0.0, 1.0].
    """
    raise NotImplementedError
