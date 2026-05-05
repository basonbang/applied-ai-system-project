"""
One-time script: MPD slices → data/playlists.json

Usage:
  python build_database.py [--limit N] [--slices-dir PATH] [--output PATH]

Defaults: --limit 1000, --slices-dir data/slices, --output data/playlists.json
"""

import argparse
import json
import os
import time
from collections import Counter
from glob import glob

import numpy as np
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

AUDIO_CACHE_PATH = "data/cache/audio_features.json"
GENRE_CACHE_PATH = "data/cache/artist_genres.json"
MOOD_VOCAB = ["hype", "dark", "chill", "melancholic", "groovy", "neutral"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_id(uri: str) -> str:
    """Strips the Spotify URI prefix and returns the bare resource ID."""
    return uri.split(":")[-1]


def load_json(path: str, default):
    """Loads a JSON file from disk, returning `default` if the file does not exist."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(obj, path: str) -> None:
    """Serializes `obj` to JSON at `path`, creating parent directories as needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f)


def init_spotify() -> spotipy.Spotify:
    """Initializes and returns an authenticated Spotify client using credentials from the environment."""
    client_id = os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError("SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET must be set in .env")
    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    return spotipy.Spotify(auth_manager=auth)


# ---------------------------------------------------------------------------
# Slice loading
# ---------------------------------------------------------------------------

def load_slices(slices_dir: str, limit: int) -> list:
    """Reads MPD slice JSON files in sorted order and returns up to `limit` playlists with at least 5 tracks."""
    paths = sorted(glob(os.path.join(slices_dir, "*.json")))
    playlists = []
    for path in paths:
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [skip] {path}: {e}")
            continue
        for pl in data.get("playlists", []):
            if pl.get("num_tracks", 0) >= 5:
                playlists.append(pl)
                if len(playlists) >= limit:
                    return playlists
    return playlists


# ---------------------------------------------------------------------------
# Spotify API fetches with rate-limit handling
# ---------------------------------------------------------------------------

def _retry_sleep(exc) -> None:
    """Reads the Retry-After header from a 429 exception and sleeps for that many seconds."""
    retry_after = 5
    if hasattr(exc, "headers") and exc.headers and "Retry-After" in exc.headers:
        try:
            retry_after = int(exc.headers["Retry-After"])
        except ValueError:
            pass
    print(f"  [rate limit] sleeping {retry_after}s …")
    time.sleep(retry_after)


def fetch_audio_features(sp: spotipy.Spotify, track_ids: set, cache: dict) -> None:
    """Fetches Spotify audio features for all uncached track IDs in batches of 100, writing results into `cache`."""
    missing = [tid for tid in track_ids if tid not in cache]
    if not missing:
        return
    print(f"  Fetching audio features for {len(missing)} tracks …")
    batch_size = 100
    for i in range(0, len(missing), batch_size):
        batch = missing[i : i + batch_size]
        while True:
            try:
                results = sp.audio_features(batch)
                break
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 429:
                    _retry_sleep(e)
                else:
                    raise
        for item in results:
            if item is None:
                continue
            tid = item["id"]
            tempo_norm = min(item["tempo"] / 200.0, 1.0)
            cache[tid] = [
                item["energy"],
                item["danceability"],
                item["valence"],
                item["acousticness"],
                tempo_norm,
            ]
        if (i // batch_size) % 10 == 9:
            save_json(cache, AUDIO_CACHE_PATH)
            print(f"    … cached {i + len(batch)}/{len(missing)}")
        time.sleep(0.05)


def fetch_artist_genres(sp: spotipy.Spotify, artist_ids: set, cache: dict) -> None:
    """Fetches genre tags for all uncached artist IDs in batches of 50, writing results into `cache`."""
    missing = [aid for aid in artist_ids if aid not in cache]
    if not missing:
        return
    print(f"  Fetching genres for {len(missing)} artists …")
    batch_size = 50
    for i in range(0, len(missing), batch_size):
        batch = missing[i : i + batch_size]
        while True:
            try:
                results = sp.artists(batch)
                break
            except spotipy.exceptions.SpotifyException as e:
                if e.http_status == 429:
                    _retry_sleep(e)
                else:
                    raise
        for artist in results.get("artists") or []:
            if artist is None:
                continue
            cache[artist["id"]] = artist.get("genres", [])
        if (i // batch_size) % 20 == 19:
            save_json(cache, GENRE_CACHE_PATH)
            print(f"    … cached {i + len(batch)}/{len(missing)}")
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Mood derivation
# ---------------------------------------------------------------------------

def derive_mood(energy: float, valence: float, danceability: float) -> str:
    """Maps average energy, valence, and danceability values to one of six mood labels."""
    if energy > 0.7 and valence > 0.6:
        return "hype"
    if energy > 0.7 and valence <= 0.4:
        return "dark"
    if energy <= 0.4 and valence > 0.6:
        return "chill"
    if energy <= 0.4 and valence <= 0.4:
        return "melancholic"
    if danceability > 0.7:
        return "groovy"
    return "neutral"


# ---------------------------------------------------------------------------
# Playlist entry construction
# ---------------------------------------------------------------------------

def build_partial_entry(raw: dict, audio_cache: dict, genre_cache: dict) -> dict | None:
    """Converts a raw MPD playlist into a partial DB entry with a 5-dim base vector, dominant genre, and mood; returns None if fewer than 5 tracks have audio features."""
    track_ids = []
    track_features = {}
    artist_ids = []

    for t in raw.get("tracks", []):
        tid = extract_id(t.get("track_uri", ""))
        aid = extract_id(t.get("artist_uri", ""))
        if not tid:
            continue
        if tid in audio_cache:
            track_ids.append(tid)
            track_features[tid] = audio_cache[tid]
        if aid:
            artist_ids.append(aid)

    if len(track_ids) < 5:
        return None

    vectors = np.array([track_features[tid] for tid in track_ids])
    base_vector = vectors.mean(axis=0).tolist()  # 5-dim

    # dominant_genre: majority vote across all genres from this playlist's artists
    genre_counter: Counter = Counter()
    for aid in artist_ids:
        for g in genre_cache.get(aid, []):
            genre_counter[g] += 1
    dominant_genre = genre_counter.most_common(1)[0][0] if genre_counter else None

    avg_energy = base_vector[0]
    avg_valence = base_vector[2]
    avg_dance = base_vector[1]
    dominant_mood = derive_mood(avg_energy, avg_valence, avg_dance)

    return {
        "id": str(raw["pid"]),
        "name": raw.get("name", ""),
        "url": None,
        "track_count": len(track_ids),
        "description": None,
        "dominant_genre": dominant_genre,
        "dominant_mood": dominant_mood,
        "_base_vector": base_vector,
        "track_ids": track_ids,
        "track_features": track_features,
    }


# ---------------------------------------------------------------------------
# Centroid encoding
# ---------------------------------------------------------------------------

def build_genre_vocab(partials: list) -> dict:
    """Builds a sorted genre-to-float mapping so each unique genre gets a consistent position in [0, 1]."""
    genres = sorted({p["dominant_genre"] for p in partials if p["dominant_genre"]})
    if not genres:
        return {}
    return {g: i / max(len(genres) - 1, 1) for i, g in enumerate(genres)}


def build_mood_vocab() -> dict:
    """Returns a fixed mood-to-float mapping over the six known mood labels."""
    n = len(MOOD_VOCAB)
    return {m: i / max(n - 1, 1) for i, m in enumerate(MOOD_VOCAB)}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Orchestrates the full pipeline: load slices → fetch API data → build entries → write playlists.json."""
    parser = argparse.ArgumentParser(description="Build VibeSearch playlist database from MPD slices.")
    parser.add_argument("--limit", type=int, default=1000, help="Max playlists to index (default 1000)")
    parser.add_argument("--slices-dir", default="data/slices", help="Path to MPD slice directory")
    parser.add_argument("--output", default="data/playlists.json", help="Output JSON path")
    args = parser.parse_args()

    t0 = time.time()
    print(f"VibeSearch database builder")
    print(f"  slices-dir : {args.slices_dir}")
    print(f"  limit      : {args.limit}")
    print(f"  output     : {args.output}")
    print()

    sp = init_spotify()

    audio_cache: dict = load_json(AUDIO_CACHE_PATH, {})
    genre_cache: dict = load_json(GENRE_CACHE_PATH, {})

    print(f"[1/5] Loading slices …")
    raw_playlists = load_slices(args.slices_dir, args.limit)
    print(f"  Loaded {len(raw_playlists)} playlists")

    all_track_ids: set = set()
    all_artist_ids: set = set()
    for pl in raw_playlists:
        for t in pl.get("tracks", []):
            tid = extract_id(t.get("track_uri", ""))
            aid = extract_id(t.get("artist_uri", ""))
            if tid:
                all_track_ids.add(tid)
            if aid:
                all_artist_ids.add(aid)
    print(f"  Unique tracks : {len(all_track_ids)}")
    print(f"  Unique artists: {len(all_artist_ids)}")

    print(f"\n[2/5] Fetching audio features …")
    fetch_audio_features(sp, all_track_ids, audio_cache)
    save_json(audio_cache, AUDIO_CACHE_PATH)
    print(f"  Audio cache size: {len(audio_cache)}")

    print(f"\n[3/5] Fetching artist genres …")
    fetch_artist_genres(sp, all_artist_ids, genre_cache)
    save_json(genre_cache, GENRE_CACHE_PATH)
    print(f"  Genre cache size: {len(genre_cache)}")

    print(f"\n[4/5] Building playlist entries …")
    partials = []
    skipped = 0
    for raw in raw_playlists:
        entry = build_partial_entry(raw, audio_cache, genre_cache)
        if entry:
            partials.append(entry)
        else:
            skipped += 1
    print(f"  Built {len(partials)} entries, skipped {skipped} (< 5 valid tracks)")

    print(f"\n[5/5] Encoding centroids and writing output …")
    genre_vocab = build_genre_vocab(partials)
    mood_vocab = build_mood_vocab()

    db = []
    for p in partials:
        genre_centroid = genre_vocab.get(p["dominant_genre"], 0.5)
        mood_centroid = mood_vocab.get(p["dominant_mood"], 0.5)
        feature_vector = p["_base_vector"] + [genre_centroid, mood_centroid]
        db.append({
            "id": p["id"],
            "name": p["name"],
            "url": p["url"],
            "track_count": p["track_count"],
            "description": p["description"],
            "dominant_genre": p["dominant_genre"],
            "dominant_mood": p["dominant_mood"],
            "feature_vector": feature_vector,
            "feature_labels": [
                "energy", "danceability", "valence", "acousticness",
                "tempo_norm", "genre_centroid", "mood_centroid",
            ],
            "track_ids": p["track_ids"],
            "track_features": p["track_features"],
        })

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(db, f)

    elapsed = time.time() - t0
    print(f"\nDone. {len(db)} playlists written to {args.output} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
