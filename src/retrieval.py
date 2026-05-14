"""
Fallback retrieval engine: L1 containment → L2 track similarity → L3 vibe similarity.
Loads and caches data/playlists.json.
TODO: implement search_by_playlist, search_by_vibe, search_by_song, search_spotify_tracks.
"""

import json

from src.scoring import cosine_similarity

_DB_PATH = "data/playlists.json"
_DB_CACHE: list | None = None


def load_database() -> list:
    """Load and cache data/playlists.json."""
    global _DB_CACHE    # Allow modification of the global cache variable

    # Open cache if it exists, otherwise load from path and store in cache for future calls
    if _DB_CACHE is None:
        with open(_DB_PATH) as f:
            _DB_CACHE = json.load(f)
    return _DB_CACHE


def _rank_by_vibe(query_vector: list, top_n: int | None = None) -> list[tuple[dict, float]]:
    """Score every playlist by cosine similarity on feature_vector; return (entry, score) sorted desc."""
    db = load_database()

    # For every playlist entry, compute cosine similarity score of it's feature vector and the query vector
    scored = [(entry, cosine_similarity(query_vector, entry["feature_vector"])) for entry in db]
    scored.sort(key=lambda x: x[1], reverse=True)   # Sort by score in descending order
    if top_n is not None:
        return scored[:top_n]
    return scored


def search_by_playlist(playlist_url: str) -> list:
    """Fetch Spotify playlist audio features and find similar playlists in the DB."""
    raise NotImplementedError


def search_by_vibe(targets: dict) -> list:
    """Search using interpreted audio feature targets from the vibe agent."""
    raise NotImplementedError


def search_by_song(track_id: str) -> list:
    """
    Fallback retrieval for a reference song.
    L1: exact containment → L2: track similarity → L3: playlist vibe match.
    """
    raise NotImplementedError


def search_spotify_tracks(query: str) -> list:
    """Search Spotify for tracks by name, return top results for user selection."""
    raise NotImplementedError
