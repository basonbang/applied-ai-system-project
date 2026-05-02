"""
Fallback retrieval engine: L1 containment → L2 track similarity → L3 vibe similarity.
Loads and caches data/playlists.json.
TODO: implement with spotipy + numpy.
"""


def load_database() -> list:
    """Load and cache data/playlists.json."""
    raise NotImplementedError


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
