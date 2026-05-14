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
import requests
from dotenv import load_dotenv

load_dotenv()

AUDIO_CACHE_PATH = "data/cache/audio_features.json"
GENRE_CACHE_PATH = "data/cache/artist_genres.json"
UUID_CACHE_PATH = "data/cache/rb_uuids.json"
MOOD_VOCAB = ["hype", "dark", "chill", "melancholic", "groovy", "neutral"]
RB_API_BASE = "https://api.reccobeats.com"
RB_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; VibeSearch/1.0)"}
RB_BATCH_SIZE = 40  # hard limit enforced by ReccoBeats on both /v1/track and /v1/audio-features
LASTFM_API_BASE = "http://ws.audioscrobbler.com/2.0/"
GENRE_ALLOWLIST = {
    # Rock
    "rock", "classic rock", "alternative rock", "indie rock", "hard rock", "soft rock",
    "punk", "punk rock", "pop punk", "post-punk", "art rock", "prog rock", "progressive rock",
    "psychedelic rock", "psychedelic", "garage rock", "surf rock", "blues rock", "folk rock",
    "country rock", "grunge", "emo", "screamo", "math rock", "noise rock", "shoegaze",
    "post-rock", "stoner rock", "doom metal", "power pop", "powerpop", "new wave",
    # Metal
    "metal", "heavy metal", "death metal", "black metal", "thrash metal", "nu metal",
    "symphonic metal", "doom metal", "hardcore", "emo violence",
    # Pop
    "pop", "indie pop", "dream pop", "bedroom pop", "synthpop", "electropop", "power pop",
    "baroque pop", "chamber pop", "twee pop", "minimal pop", "chillwave", "k-pop", "j-pop",
    "city pop", "eurodance", "dance pop",
    # Hip-hop / R&B
    "hip-hop", "hip hop", "rap", "underground hip-hop", "cloud rap", "trap", "drill",
    "grime", "boom bap", "horrorcore", "christian rap", "conscious hip-hop",
    "r&b", "rnb", "alternative rnb", "neo soul", "soul", "funk", "motown", "quiet storm",
    # Electronic / Dance
    "electronic", "electronica", "electro", "edm", "dance", "house", "deep house",
    "tech house", "french house", "acid house", "electro house", "future house", "ambient house",
    "techno", "minimal techno", "industrial techno", "detroit techno", "chicago house",
    "trance", "psytrance", "progressive trance", "dubstep", "future bass", "drum and bass",
    "dnb", "jungle", "breakbeat", "garage", "uk garage", "ambient", "downtempo", "chillout",
    "idm", "glitch", "vaporwave", "synthwave", "lo-fi", "chillhop", "moombahton",
    "electroclash", "indietronica", "folktronica",
    # Folk / Country / Americana
    "folk", "indie folk", "folk rock", "singer-songwriter", "acoustic", "americana",
    "country", "bluegrass", "outlaw country", "a cappella",
    # Jazz / Blues / Soul
    "jazz", "nu-jazz", "smooth jazz", "free jazz", "bebop", "big band", "swing",
    "blues", "soul", "gospel", "blue-eyed soul",
    # Other genres
    "latin", "reggae", "ska", "dancehall", "reggaeton", "afrobeats", "afropop",
    "classical", "contemporary classical", "chamber music", "opera", "new age",
    "bossa nova", "flamenco", "world music", "celtic", "tuareg",
    "industrial", "noise", "avant-garde", "experimental", "ambient",
    "disco", "funk rock", "doo wop", "trip-hop", "darkwave", "goth",
    "musical", "musical theatre", "broadway", "soundtrack", "comedy", "spoken word",
    "christian rock", "gospel", "disney",
    "j-rock", "anime", "visual kei",
}


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


# ---------------------------------------------------------------------------
# Slice loading
# ---------------------------------------------------------------------------

def load_slices(slices_dir: str, limit: int) -> list:
    """Reads MPD slice JSON files in sorted order and returns up to `limit` playlists with at least 5 tracks."""
    paths = sorted(glob(os.path.join(slices_dir, "*.json")))
    playlists = []
    
    # Open each slice file, skipping the invalid or corrupted ones
    for path in paths:
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [skip] {path}: {e}")
            continue

        # Extract the playlists from the slice, filtering out those with less than 5 songs
        for pl in data.get("playlists", []):
            if pl.get("num_tracks", 0) >= 5:
                playlists.append(pl)

                # Stop extracting once we reach the limit 
                if len(playlists) >= limit:
                    return playlists
    return playlists


# ---------------------------------------------------------------------------
# ReccoBeats API fetches (audio features — Spotify endpoint deprecated Nov 2024)
# ---------------------------------------------------------------------------

def resolve_rb_uuids(spotify_ids: list, uuid_cache: dict) -> None:
    """Resolves uncached Spotify track IDs to ReccoBeats internal UUIDs via /v1/track?ids=, writing into `uuid_cache`."""
    missing = [sid for sid in spotify_ids if sid not in uuid_cache]
    if not missing:
        return
    print(f"  Resolving {len(missing)} Spotify IDs → ReccoBeats UUIDs …")
    for i in range(0, len(missing), RB_BATCH_SIZE):
        batch = missing[i : i + RB_BATCH_SIZE]
        resp = requests.get(f"{RB_API_BASE}/v1/track?ids={','.join(batch)}", headers=RB_HEADERS, timeout=30)
        resp.raise_for_status()
        for track in resp.json().get("content", []):
            # Match returned tracks back to their Spotify ID via the href field
            spotify_id = track.get("href", "").split("/")[-1]
            if spotify_id:
                uuid_cache[spotify_id] = track["id"]
        if (i // RB_BATCH_SIZE) % 10 == 9:
            save_json(uuid_cache, UUID_CACHE_PATH)
            print(f"    … resolved {i + len(batch)}/{len(missing)}")
        time.sleep(0.05)


def fetch_audio_features(track_ids: set, uuid_cache: dict, audio_cache: dict) -> None:
    """Fetches audio features from ReccoBeats for all uncached track IDs in batches of 100, writing results into `audio_cache`."""
    missing = [tid for tid in track_ids if tid not in audio_cache and tid in uuid_cache]
    if not missing:
        return
    print(f"  Fetching audio features for {len(missing)} tracks …")
    for i in range(0, len(missing), RB_BATCH_SIZE):
        batch = missing[i : i + RB_BATCH_SIZE]
        uuids = [uuid_cache[tid] for tid in batch]
        resp = requests.get(f"{RB_API_BASE}/v1/audio-features?ids={','.join(uuids)}", headers=RB_HEADERS, timeout=30)
        resp.raise_for_status()
        for item in resp.json().get("content", []):
            # Map ReccoBeats UUID back to Spotify ID via the href field
            spotify_id = item.get("href", "").split("/")[-1]
            if not spotify_id:
                continue
            # Skip tracks where any required field is null
            required = ["energy", "danceability", "valence", "acousticness", "tempo"]
            if any(item.get(k) is None for k in required):
                continue
            tempo_norm = min(item["tempo"] / 200.0, 1.0)    # normalize tempo to [0,1] assuming 200 BPM max
            audio_cache[spotify_id] = [
                item["energy"],
                item["danceability"],
                item["valence"],
                item["acousticness"],
                tempo_norm,
            ]
        # Save the cache to disk every 10 batches to avoid losing progress
        if (i // RB_BATCH_SIZE) % 10 == 9:
            save_json(audio_cache, AUDIO_CACHE_PATH)
            print(f"    … cached {i + len(batch)}/{len(missing)}")
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# Last.fm API fetches (genre tags — keyed by lowercased artist name)
# ---------------------------------------------------------------------------

def fetch_lastfm_genres(artist_names: set, cache: dict) -> None:
    """Fetches the top genre tag per artist from Last.fm, writing results into `cache` keyed by lowercased artist name."""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        raise RuntimeError("LASTFM_API_KEY must be set in .env")
    missing = [name for name in artist_names if name not in cache]
    if not missing:
        return
    print(f"  Fetching Last.fm genre tags for {len(missing)} artists …")
    for i, name in enumerate(missing):
        try:
            resp = requests.get(
                LASTFM_API_BASE,
                params={"method": "artist.getTopTags", "artist": name, "api_key": api_key, "format": "json"},
                timeout=10,
            )
            resp.raise_for_status()
            tags = resp.json().get("toptags", {}).get("tag", [])
            # Take the first tag that has a meaningful count and isn't a non-genre label
            genre = next(
                (t["name"].lower() for t in tags if int(t.get("count", 0)) >= 5 and t["name"].lower() in GENRE_ALLOWLIST),
                None,
            )
        except Exception:
            genre = None
        cache[name] = genre
        # Save progress every 100 artists to avoid losing work on interruption
        if (i + 1) % 100 == 0:
            save_json(cache, GENRE_CACHE_PATH)
            print(f"    … cached {i + 1}/{len(missing)}")
        time.sleep(0.25)


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
    artist_names = []

    # For each raw track from the MPD slice, extract the track ID and artist name
    for track in raw.get("tracks", []):
        tid = extract_id(track.get("track_uri", ""))
        aname = track.get("artist_name", "").lower()
        if not tid:
            continue
        # Only include this raw track if we have audio features for it in the cache
        if tid in audio_cache:
            track_ids.append(tid)
            track_features[tid] = audio_cache[tid]
        # Collect artist names for genre majority vote
        if aname:
            artist_names.append(aname)
            

    if len(track_ids) < 5:
        return None

    # Compute the playlist's base vector as the average of its tracks' audio features
    vectors = np.array([track_features[tid] for tid in track_ids])
    base_vector = vectors.mean(axis=0).tolist()  # 5-dim

    # dominant_genre: majority vote across all artists' Last.fm genre tags
    genre_counter: Counter = Counter()
    for aname in artist_names:
        stored = genre_cache.get(aname)
        for g in ([stored] if stored else []):
            genre_counter[g] += 1
    dominant_genre = genre_counter.most_common(1)[0][0] if genre_counter else None

    # dominant_mood: derived from the average energy, valence, and danceability of the playlist's tracks
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

    audio_cache: dict = load_json(AUDIO_CACHE_PATH, {})
    uuid_cache: dict = load_json(UUID_CACHE_PATH, {})

    print(f"[1/5] Loading slices …")
    raw_playlists = load_slices(args.slices_dir, args.limit)
    print(f"  Loaded {len(raw_playlists)} playlists")

    all_track_ids: set = set()
    all_artist_names: set = set()
    for pl in raw_playlists:
        for t in pl.get("tracks", []):
            tid = extract_id(t.get("track_uri", ""))
            aname = t.get("artist_name", "").lower()
            if tid:
                all_track_ids.add(tid)
            if aname:
                all_artist_names.add(aname)
    print(f"  Unique tracks : {len(all_track_ids)}")
    print(f"  Unique artists: {len(all_artist_names)}")

    print(f"\n[2/5] Fetching audio features (via ReccoBeats) …")
    resolve_rb_uuids(list(all_track_ids), uuid_cache)
    save_json(uuid_cache, UUID_CACHE_PATH)
    print(f"  UUID cache size: {len(uuid_cache)}")
    fetch_audio_features(all_track_ids, uuid_cache, audio_cache)
    save_json(audio_cache, AUDIO_CACHE_PATH)
    print(f"  Audio cache size: {len(audio_cache)}")

    print(f"\n[3/5] Fetching artist genres (via Last.fm) …")
    genre_cache: dict = load_json(GENRE_CACHE_PATH, {})
    fetch_lastfm_genres(all_artist_names, genre_cache)
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
        # Creates the final 7-dim feature vector
        genre_centroid = genre_vocab.get(p["dominant_genre"], 0.5)
        mood_centroid = mood_vocab.get(p["dominant_mood"], 0.5)
        feature_vector = p["_base_vector"] + [genre_centroid, mood_centroid]

        # Final playlist entry written into playlists.json
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
