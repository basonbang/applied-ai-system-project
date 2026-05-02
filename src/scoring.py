"""
Hybrid scorer: mode-specific weighted combinations of retrieval signals.
TODO: implement cosine similarity and per-mode weight configs.
"""


def cosine_similarity(a: list, b: list) -> float:
    raise NotImplementedError


def confidence_label(score: float) -> str:
    """Returns 'High' / 'Medium' / 'Low' based on score thresholds."""
    raise NotImplementedError


def hybrid_score(mode: str, playlist_vector: list, query_vector: list, **signals) -> float:
    """
    Compute weighted hybrid score for a playlist given the input mode.
    Modes: 'playlist', 'vibe', 'song'. All signal values in [0.0, 1.0].
    """
    raise NotImplementedError
