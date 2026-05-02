# CLAUDE.md — VibeSearch

This file provides guidance to Claude Code when working with code in this repository.

## What Is VibeSearch

VibeSearch finds Spotify playlists that match a given *feel* rather than a keyword. Users submit
one of three inputs — a playlist URL, a natural-language vibe description, or a reference song —
and get back the 5 most musically similar playlists from a locally indexed database, ranked and
explained by audio features.

---

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Build the playlist database (one-time setup — requires Spotify API credentials)
python build_database.py

# Run the Streamlit app
streamlit run app.py

# Run the evaluation harness (headless, no manual input needed)
python evaluate.py

# Legacy: run original song recommender CLI
PYTHONPATH=legacy python3 legacy/src/main.py

# Legacy: run original recommender tests
PYTHONPATH=legacy python3 -m pytest legacy/tests/
```

---

## Credentials

All API keys live in a `.env` file at the project root (git-ignored). Required variables:

```
SPOTIPY_CLIENT_ID=...
SPOTIPY_CLIENT_SECRET=...
GEMINI_API_KEY=...
```

- Spotify credentials: [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
- Gemini API key: [Google AI Studio](https://aistudio.google.com) (free tier, no credit card)

---

## File Structure

```
applied-ai-system-final/
├── app.py                 — Streamlit UI 
├── build_database.py      — One-time script: source playlists → Spotify audio features → data/playlists.json
├── evaluate.py            — Test harness: 5–10 preset inputs, pass/fail summary
├── .env                   — API credentials (git-ignored)
├── requirements.txt
├── src/
│   ├── retrieval.py       — Fallback retrieval engine (L1/L2/L3) + cosine similarity
│   ├── agent.py           — Gemini Flash vibe clarification agent + explanation generator
│   └── scoring.py         — Hybrid scorer with mode-specific weight configs
├── data/
│   └── playlists.json     — Indexed playlist database (output of build_database.py)
└── legacy/                — Original CSV-based song recommender (untouched, for reference)
    ├── src/
    ├── data/
    └── tests/
```

---

## Architecture

```
Streamlit UI (app.py)
  Tab 1: Playlist URL  |  Tab 2: Describe Your Vibe  |  Tab 3: Reference Song
              │                   │                      │
              └───────────────────┼──────────────────────┘
                                  │
                          Input Router
                         /              \
              Spotify API             Gemini Flash Agent
              (spotipy)               (vibe clarification,
              Fetch audio             2–3 follow-up questions,
              features                outputs interpreted targets)
                         \              /
                     Query Constructor
                     Normalized NumPy feature vector
                     [energy, danceability, valence,
                      acousticness, tempo_norm,
                      genre_centroid, mood_centroid]
                                  │
                     data/playlists.json
                     ~500–1000 indexed playlists
                                  │
                     Fallback Retrieval Engine (src/retrieval.py)
                       L1: exact track containment (set lookup)
                       L2: track-level similarity (per-track vectors)
                       L3: playlist vibe similarity (cosine on avg vector)
                     Stops at first level with confident results
                                  │
                     Hybrid Scorer (src/scoring.py)
                     Mode-specific weighted combination
                                  │
                     Gemini Flash Explanation Generator (src/agent.py)
                     1–2 sentence plain-English explanation per result
                                  │
                     Results UI: top 5 + Spotify links + confidence labels
```

---

## Data Flow

1. **Input resolution** — Playlist URL or song URL is fetched via Spotify API into a feature vector.
   Vibe text goes through the Gemini clarification agent first, producing a feature target dict.
2. **Query vector construction** — All inputs normalize to a 7-dim NumPy vector.
3. **Retrieval** — `src/retrieval.py` runs fallback retrieval against `data/playlists.json`.
4. **Hybrid scoring** — `src/scoring.py` combines available signals with mode-specific weights.
5. **Explanation generation** — `src/agent.py` calls Gemini Flash with the match data and returns
   a plain-English explanation for each top result.
6. **UI rendering** — `app.py` displays top 5 results with name, link, explanation, confidence.

---

## Key Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit UI; owns tab routing and result rendering |
| `build_database.py` | One-time builder: reads source playlist IDs → Spotify audio features → writes `data/playlists.json` |
| `evaluate.py` | Headless test harness; runs 5–10 preset inputs across all 3 modes, prints pass/fail |
| `src/retrieval.py` | Fallback retrieval (L1 containment, L2 track similarity, L3 vibe cosine); loads and caches DB |
| `src/agent.py` | Gemini Flash client; multi-turn vibe clarification loop + explanation generation |
| `src/scoring.py` | Hybrid scoring weights and final score computation |
| `data/playlists.json` | Indexed playlist database (see schema below) |

---

## Scoring Approach

### Hybrid Weights by Input Mode

**Playlist URL input:**
```python
final_score = 0.60 * playlist_vector_similarity + 0.25 * track_overlap_similarity + 0.15 * metadata_similarity
```

**Vibe description input:**
```python
final_score = 0.70 * interpreted_vibe_similarity + 0.20 * metadata_similarity + 0.10 * diversity_bonus
```

**Reference song input:**
```python
final_score = 0.50 * playlist_vibe_similarity + 0.30 * track_containment_or_similarity + 0.20 * metadata_similarity
```

### Fallback Retrieval Levels

- **L1 — Exact containment:** `track_id in playlist["track_ids"]` — strongest signal, nearly free
- **L2 — Track similarity:** compare reference song vector against every per-track vector in each playlist
- **L3 — Playlist vibe match:** cosine similarity between query vector and playlist `feature_vector`

System stops and returns results at the first level that produces confident matches.

### Confidence Labels

| Score range | Label |
|---|---|
| ≥ 0.75 | High |
| 0.50–0.74 | Medium |
| < 0.50 | Low |

---

## Database Schema (`data/playlists.json`)

Each entry in the JSON array:

```json
{
  "id": "spotify_playlist_id",
  "name": "Playlist Name",
  "url": "https://open.spotify.com/playlist/...",
  "track_count": 24,
  "description": "Optional playlist description",
  "dominant_genre": "lofi",
  "dominant_mood": "chill",
  "feature_vector": [0.61, 0.72, 0.45, 0.38, 0.80, 0.55, 0.49],
  "feature_labels": ["energy", "danceability", "valence", "acousticness", "tempo_norm", "genre_centroid", "mood_centroid"],
  "track_ids": ["spotify_track_id_1", "spotify_track_id_2"],
  "track_features": {
    "spotify_track_id_1": [0.61, 0.72, 0.45, 0.38, 0.80],
    "spotify_track_id_2": [0.44, 0.68, 0.31, 0.62, 0.70]
  }
}
```

`track_ids` → L1 exact containment. `track_features` → L2 track similarity. `feature_vector` → L3 vibe match and all input modes.

---

## Building the Database

`build_database.py` is a one-time setup script. Two supported source approaches:

1. **MPD slice** — Download a slice of the [Spotify Million Playlist Dataset](https://www.aicrowd.com/challenges/spotify-million-playlist-dataset-challenge), point the script at the JSON files, and it will enrich each playlist with Spotify audio features.
2. **Manual curation** — Provide a text file of Spotify playlist URLs (one per line). The script fetches each playlist's tracks and their audio features via the Spotify API.

Output is always `data/playlists.json`. Expect ~500–1000 playlists for meaningful retrieval. The file can be large; consider adding it to `.gitignore`.

---

## Evaluation Harness (`evaluate.py`)

Runs headlessly with no manual input. Checks each output for:
- Results returned (non-empty list)
- Scores in valid range [0.0, 1.0]
- Explanation non-empty and references at least one audio feature
- Exact containment matches labeled correctly vs. fallback matches

Prints: inputs tested, pass/fail per case, overall pass rate.

---

## Edge Cases

| Edge case | Handling |
|---|---|
| Malformed Spotify URL | Validate before API call; surface clear UI error |
| Private/unavailable playlist | Surface error; suggest vibe or song mode |
| Playlist with < 5 tracks | Flag as low-confidence input; warn in UI |
| Song not in any indexed playlist | Skip L1; run L2 → L3; label result as fallback |
| Vague or contradictory vibe | Agent surfaces contradiction and asks user to prioritize |
| No strong match in database | Return closest results with Low confidence label |
| Spotify API unavailable | Catch exception; offer fallback to vibe description mode |
| Missing audio features for a track | Skip track in vector construction; log dropped tracks |

---

## Legacy Code

The original CSV-based song recommender lives in `legacy/` and is not part of the VibeSearch
pipeline. It uses a different scoring approach (weighted proximity over a 20-song CSV catalog) and
is kept for reference and grading continuity. See `legacy/src/recommender.py` for the original
`Recommender` class, `score_song()`, and `recommend_songs()` implementations.
