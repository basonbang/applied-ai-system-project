# build_database.py — Pipeline Flow

End-to-end flow of the `main()` function in `build_database.py`.

```mermaid
flowchart TD
    A([START]) --> B

    subgraph STEP1["[1/5] Load Slices"]
        B["load_slices(slices_dir, limit)\nRead MPD *.json files\nFilter playlists ≥ 5 tracks"]
    end

    subgraph STEP2["Collect IDs"]
        C["Iterate raw playlists\nExtract all track IDs + artist names\n→ all_track_ids set\n→ all_artist_names set"]
    end

    subgraph STEP3["[2/5] Audio Features via ReccoBeats"]
        D["resolve_rb_uuids()\nSpotify ID → ReccoBeats UUID\ncached in data/cache/rb_uuids.json"]
        E["fetch_audio_features()\nReccoBeats UUID → 5-dim vector\n[energy, danceability, valence,\nacousticness, tempo_norm]\ncached in data/cache/audio_features.json"]
        D --> E
    end

    subgraph STEP4["[3/5] Artist Genres via Last.fm"]
        F["fetch_lastfm_genres()\nArtist name → dominant genre tag\ncached in data/cache/artist_genres.json"]
    end

    subgraph STEP5["[4/5] Build Partial Entries"]
        G["build_partial_entry() per playlist\nFor each track with cached audio features:\n  → accumulate feature vectors"]
        H["base_vector = mean of all track vectors\n(5-dim average)"]
        I["dominant_genre = majority vote\nacross artist genre tags"]
        J["dominant_mood = derive_mood()\nenergy + valence + danceability thresholds"]
        G --> H --> I --> J
    end

    subgraph STEP6["[5/5] Encode Centroids + Write"]
        K["build_genre_vocab(partials)\nSorted genre → float in [0,1]\n(runs once across ALL partials)"]
        L["build_mood_vocab()\nFixed mood → float in [0,1]\n(runs once across ALL partials)"]
        M["Final feature vector (7-dim)\nbase_vector[0:5]\n+ genre_centroid\n+ mood_centroid"]
        N["Append playlist entry\nto db list"]
        K --> M
        L --> M
        M --> N
    end

    O["Write db → playlists.json"] --> P([END])

    B --> C --> D
    E --> F
    F --> G
    J --> K
    N --> O
```

## Step-by-Step Summary

| Step | Function(s) | Output |
|---|---|---|
| 1 | `load_slices()` | Raw playlist list (≥5 tracks each) |
| 2 | _(inline loop)_ | `all_track_ids` set, `all_artist_names` set |
| 3a | `resolve_rb_uuids()` | Spotify ID → ReccoBeats UUID map (cached) |
| 3b | `fetch_audio_features()` | Track ID → 5-dim audio vector (cached) |
| 4 | `fetch_lastfm_genres()` | Artist name → genre string (cached) |
| 5 | `build_partial_entry()` | Per-playlist: base vector, dominant genre, dominant mood |
| 6a | `build_genre_vocab()` | Global genre → float centroid mapping |
| 6b | `build_mood_vocab()` | Fixed mood → float centroid mapping |
| 6c | _(inline loop)_ | Final 7-dim `feature_vector` per playlist |
| 7 | `json.dump()` | `data/playlists.json` written to disk |

## Feature Vector Dimensions

```
[energy, danceability, valence, acousticness, tempo_norm, genre_centroid, mood_centroid]
   0          1           2          3             4             5               6
```

- **Dims 0–4** (`_base_vector`): mean of per-track ReccoBeats audio features
- **Dim 5** (`genre_centroid`): position of dominant genre in sorted global genre vocab → float in [0, 1]
- **Dim 6** (`mood_centroid`): position of dominant mood in fixed 6-label mood vocab → float in [0, 1]
