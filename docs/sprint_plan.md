# Sprint Plan

The database (`data/playlists.json`) is built. Remaining work is broken into 7 phases. Each task
is small enough to tackle in a single sitting. Tasks within a phase are ordered by dependency —
finish them top-down. Phases 1–3 are sequential; phases 4–6 (the three input modes) can be done
in any order once phase 3 is in.

---

## Phase 1 — Retrieval primitives (`src/retrieval.py`, `src/scoring.py`)

Build the foundation that every input mode will call into.

- [ ] **1.1 — Implement `cosine_similarity(a, b)`** in `src/scoring.py`. Standard NumPy dot-product
  over magnitudes. Acceptance: unit test on two identical vectors → 1.0; orthogonal → 0.0.
- [ ] **1.2 — Implement `load_database()`** in `src/retrieval.py`. Read `data/playlists.json` once
  on first call, cache at module level. Returns the parsed list. Acceptance: second call doesn't
  re-read the file.
- [ ] **1.3 — Implement `confidence_label(score)`** in `src/scoring.py`. ≥0.75 → "High",
  0.50–0.74 → "Medium", <0.50 → "Low".
- [ ] **1.4 — Implement L3 vibe similarity (internal helper)** in `src/retrieval.py`. Given a
  7-dim query vector, score every playlist by cosine on `feature_vector`, return top N sorted
  desc. This is the workhorse used by all three modes.

---

## Phase 2 — Vibe agent (`src/agent.py`)

The vibe mode is the simplest end-to-end path because it doesn't need Spotify lookups. Build the
Gemini integration here, then wire it up in phase 3.

- [ ] **2.1 — Add `google-generativeai` to `requirements.txt`** and pip install. Verify
  `GEMINI_API_KEY` loads from `.env`.
- [ ] **2.2 — Implement `interpret_vibe(vibe_text, history)`**. Build a prompt that asks Gemini
  to map the vibe + Q&A history into a dict of 5 audio targets (`energy`, `danceability`,
  `valence`, `acousticness`, `tempo_norm`), all in [0, 1]. Return the dict. Acceptance: calling
  with `"late night drive, melancholic"` returns plausible targets (e.g. low valence, mid energy).
- [ ] **2.3 — Implement `get_first_question(vibe_text)`**. Prompt Gemini to ask one clarifying
  question about the vibe. Acceptance: returns a non-empty string ending in "?".
- [ ] **2.4 — Implement `get_next_question(history)`**. Same idea but conditioned on prior Q&A.
  Acceptance: returns a different question than `get_first_question` for the same vibe text.
- [ ] **2.5 — Implement `generate_explanation(result, query_vector, mode)`**. Prompt Gemini with
  the playlist's name, dominant genre/mood, and feature vector vs the query vector. Return a 1–2
  sentence plain-English explanation that references at least one audio feature. Acceptance:
  output is non-empty and mentions at least one of: energy, mood, tempo, danceability, etc.

---

## Phase 3 — Vibe mode end-to-end

Connect the vibe agent to retrieval. This is the first complete user flow.

- [ ] **3.1 — Implement `search_by_vibe(targets)`** in `src/retrieval.py`. Build a 7-dim query
  vector from the 5 audio targets + neutral 0.5 for `genre_centroid` and `mood_centroid`. Run L3
  vibe similarity. Return top 5 as result dicts with shape:
  `{name, url, track_count, confidence, is_fallback: False, explanation}`.
- [ ] **3.2 — Implement `hybrid_score(mode='vibe', ...)`** in `src/scoring.py`. For vibe mode:
  `0.70 * vibe_sim + 0.20 * metadata_sim + 0.10 * diversity_bonus`. Metadata sim and diversity
  can start as constants/passthroughs and be refined later.
- [ ] **3.3 — Wire results in `search_by_vibe`** to call `generate_explanation` per result.
- [ ] **3.4 — Smoke test in app**: run `streamlit run app.py`, type a vibe, complete the Q&A, see
  5 ranked playlists with explanations. Iterate on prompt quality if explanations feel weak.

---

## Phase 4 — Playlist URL mode

Reuses the vibe-mode retrieval primitives but starts from a real Spotify playlist.

- [ ] **4.1 — Add `spotipy` back to `requirements.txt`** (only `playlist_tracks` is needed; that
  endpoint still works for new apps). Add `SPOTIPY_CLIENT_ID/SECRET` back to `.env` requirements
  documented in the Credentials section of CLAUDE.md.
- [ ] **4.2 — Implement `search_by_playlist(url)`** in `src/retrieval.py`. Parse playlist ID from
  URL, fetch tracks via `spotipy.playlist_tracks`, look up each track's audio features in the
  ReccoBeats audio cache (`data/cache/audio_features.json`); skip uncached tracks. Average the
  features into a 5-dim base vector + neutral genre/mood centroids → 7-dim query vector. Run L3
  similarity. Return top 5 with `is_fallback: False`.
- [ ] **4.3 — Implement `hybrid_score(mode='playlist', ...)`**:
  `0.60 * playlist_vec_sim + 0.25 * track_overlap + 0.15 * metadata_sim`. Track overlap = Jaccard
  between input track set and playlist `track_ids`.
- [ ] **4.4 — Smoke test in app**: paste a real Spotify playlist URL, see ranked results.

---

## Phase 5 — Reference song mode

Adds the L1 → L2 → L3 fallback cascade.

- [ ] **5.1 — Implement `search_spotify_tracks(query)`** in `src/retrieval.py` for the song
  picker. Uses `spotipy.search(q, type='track', limit=10)`. Return list of
  `{id, name, artist, year}` dicts. Acceptance: typing "bohemian rhapsody" returns a Queen result.
- [ ] **5.2 — Implement L1 (exact containment)** in `src/retrieval.py`. Given a `track_id`,
  return all playlists where `track_id in playlist["track_ids"]`. If ≥1 match, label as L1 hit.
- [ ] **5.3 — Implement L2 (track-level similarity)** in `src/retrieval.py`. Look up the
  reference song's 5-dim vector (from cache or via on-demand ReccoBeats call). For each playlist,
  compute the max cosine similarity between the reference vector and any per-track vector in
  `track_features`. Return top N by that score.
- [ ] **5.4 — Implement `search_by_song(track_id)`** orchestrator. Run L1 first; if results,
  return them with `is_fallback: False`. Else run L2; if scores are confident (≥0.5), return with
  `is_fallback: True`. Else run L3 on the song's vector.
- [ ] **5.5 — Implement `hybrid_score(mode='song', ...)`**:
  `0.50 * playlist_vibe_sim + 0.30 * track_containment_or_sim + 0.20 * metadata_sim`.
- [ ] **5.6 — Smoke test in app**: search by song name, pick a result, see ranked playlists.
  Test both an indexed song (L1 hit) and an obscure one (fallback path).

---

## Phase 6 — Evaluation harness (`evaluate.py`)

A headless test harness that catches regressions.

- [ ] **6.1 — Create `evaluate.py` skeleton** with a list of preset test cases (3 vibe inputs,
  3 playlist URLs, 3 song queries — 9 cases total).
- [ ] **6.2 — Implement assertion checks per case**: results list non-empty, all scores in
  [0, 1], explanations non-empty and mention at least one audio feature, L1 hits labeled
  correctly vs fallback.
- [ ] **6.3 — Add pass/fail summary printer** with per-case status and overall pass rate.
- [ ] **6.4 — Run `python evaluate.py`** and aim for 100% pass rate. Iterate on retrieval/agent
  until all cases pass.

---

## Phase 7 — Polish

Final pass over UX and edge cases.

- [ ] **7.1 — Error handling for malformed inputs**: bad URL, private playlist, song with no
  audio features. Verify the existing `app.py` error branches surface correctly.
- [ ] **7.2 — Confidence label rendering**: ensure `app.py` displays the colored dots correctly
  for High/Medium/Low.
- [ ] **7.3 — Prompt tuning** based on observed explanation quality from phase 6.
- [ ] **7.4 — Update `docs/build_database_flow.md` and `docs/model_card.md`** if the
  implementation deviated from those docs during phases 1–6.
