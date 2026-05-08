# VibeSearch — Product Requirements Document

**Project Type:** Academic Final Project (Extension of Music Recommender Simulation)  
**Stack:** Python · Streamlit · Spotify Web API · Gemini Flash API · NumPy  
**Version:** 2.0 MVP  

---

## 1. Project Overview

### 1.1 Base Project

VibeSearch extends an existing content-based music recommender simulation built in Python. The original system scores songs from a local CSV catalog against a manually constructed `UserProfile` using weighted proximity scoring across audio features (genre, mood, energy, tempo, valence, danceability, acousticness). It exposes both a functional interface (dict-based) and an OOP interface (`Recommender` class + `Song`/`UserProfile` dataclasses).

**Original system capabilities:**
- Load songs from a CSV catalog
- Score songs against a user preference profile using weighted proximity
- Return top-K recommendations with plain-English explanations
- Tiered categorical matching for genre and mood (exact, family, or no match)

### 1.2 Problem Statement

Spotify's playlist search only finds playlists by keywords in titles and descriptions. There is no way to search for existing user-created playlists by how they actually *sound and feel*. A playlist titled "Late Night Drive" and one titled "3am Thoughts" may be musically identical, but current search would never surface one from the other.

VibeSearch fills this gap using three distinct input modes — natural language vibe description, a Spotify playlist URL, or a reference song — and returns the most musically similar playlists from a curated indexed database, ranked and explained by audio features rather than labels.

### 1.3 Goals

- Demonstrate RAG, agentic workflows, embeddings, and automated evaluation in a working system
- Build something genuinely novel: contextual retrieval over user-created playlists using vibe, playlist, and reference-song signals
- Produce a portfolio-ready project that is explainable in a technical interview
- Satisfy all required and stretch rubric criteria for the final project grade

---

## 2. Users

### Primary User
A heavy Spotify listener who has exhausted algorithmic recommendations and wants to discover playlists that *feel* like ones they already love — without relying on title keywords or genre tags.

**What they want to see:**
- Results that feel surprising in a good way
- Plain-English explanations they can trust ("This matches your chill focus vibe — low energy, mid tempo, mostly instrumental")
- No raw numbers or feature scores surfaced directly in the UI

### Secondary User (Resume/Demo Audience)
A recruiter or technical interviewer evaluating the project as a portfolio piece.

**What they want to see:**
- A visible architecture showing RAG, agent reasoning, and evaluation
- Observable intermediate steps (the agent's interpretation before retrieval)
- A test harness with printed pass/fail results

---

## 3. Core Features (MVP)

### 3.1 Three Input Modes

| Mode | Description |
|---|---|
| **Playlist URL** | User pastes a Spotify playlist URL. System fetches track audio features via the Spotify API, computes a playlist-level feature vector, and retrieves the closest matches from the database using hybrid scoring. |
| **Conversational Vibe** | User describes a vibe in natural language. An AI agent asks 2–3 clarifying follow-up questions to narrow the description into concrete audio feature targets, then retrieves matching playlists. |
| **Reference Song** | User provides a Spotify track URL or searches for a song by name. System runs fallback retrieval: exact containment check first, then similar-track matching, then playlist-level vibe matching. |

All three modes feed into the same retrieval and explanation pipeline once input is resolved.

### 3.2 Conversational Vibe Agent

A multi-turn dialogue flow powered by the Gemini Flash API:

1. User submits a vibe description (e.g. "Sunday morning, raining, making coffee")
2. Agent asks up to 3 targeted clarifying questions (e.g. "More energetic or more relaxed?" / "Vocals or instrumental?")
3. Agent outputs its interpreted audio feature targets visibly before searching (e.g. "Searching for: energy ~0.3, acousticness high, tempo slow")
4. User can confirm or correct the interpretation before retrieval begins
5. Retrieval executes on confirmed targets

This is the **agentic workflow** component — multi-step reasoning with observable intermediate steps.

### 3.3 Fallback Retrieval (RAG)

The reference song mode demonstrates **fallback retrieval** — a real pattern used in production RAG systems where progressively less direct evidence is used when exact matches are unavailable.

**Level 1 — Exact Containment Check:**
```python
if track_id in playlist["track_ids"]:
    # direct hit — strongest possible signal
```
A simple set lookup. Nearly free computationally. When it hits, it is the most trustworthy signal in the system.

**Level 2 — Similar Track Match:**
If no playlist contains the exact song, compare the reference song's audio feature vector against every track vector stored inside each indexed playlist. Playlists with more musically similar tracks score higher.

**Level 3 — Playlist Vibe Match:**
If Level 2 produces weak results, compare the reference song's vector directly against each playlist's single averaged feature vector. This is the same cosine similarity retrieval used for the other two input modes.

The system stops and returns results as soon as a level produces confident matches, rather than running all three levels every time.

### 3.4 Hybrid Scoring

Different input modes use different scoring weights reflecting which signals are available:

**Reference Song Input:**
```python
final_score = (
    0.50 * playlist_vibe_similarity +
    0.30 * track_containment_or_similarity +
    0.20 * metadata_similarity
)
```

**Vibe Description Input:**
```python
final_score = (
    0.70 * interpreted_vibe_similarity +
    0.20 * metadata_similarity +
    0.10 * diversity_bonus
)
```

**Playlist URL Input:**
```python
final_score = (
    0.60 * playlist_vector_similarity +
    0.25 * track_overlap_similarity +
    0.15 * metadata_similarity
)
```

Weights are adjustable during development and evaluation.

### 3.5 Per-Result Explanations

Each of the top 5 results includes:
- Playlist name and a Spotify link
- A 1–2 sentence plain-English explanation referencing actual audio features and match reason
- A confidence label (High / Medium / Low) based on final score

Explanation templates by input mode:

> **Vibe:** "This playlist matches your 'rainy Sunday morning' vibe — lower energy, high acousticness, and a relaxed tempo."

> **Playlist URL:** "This playlist is similar to your source — both have mid-tempo tracks, high acousticness, and a mellow emotional tone."

> **Song (exact):** "This playlist contains your reference song and shares its low-valence, late-night feel."

> **Song (fallback):** "No exact match found, but this playlist contains tracks with similar energy, tempo, and mood to your reference song."

Explanations are generated by the Gemini Flash API using the retrieved playlist's feature data and the query vector as context.

### 3.6 Evaluation Harness

A standalone `evaluate.py` script that:
- Runs 5–10 preset inputs covering all three input modes against the live system
- Checks each output for: results returned, scores in valid range, explanation non-empty, explanation references at least one audio feature
- Verifies exact containment matches are labeled correctly and fallback matches are clearly distinguished
- Prints a summary: inputs tested, pass/fail per case, overall pass rate
- Runs headlessly with no manual input required

This is the **reliability/guardrail component** satisfying the rubric requirement.

---

## 4. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                       Streamlit UI                        │
│  Tab 1: Playlist URL | Tab 2: Vibe Chat | Tab 3: Song    │
└──────────────────────────────┬───────────────────────────┘
                               │
                      ┌────────▼────────┐
                      │   Input Router  │
                      │ URL/vibe/song   │
                      └──┬──────────┬───┘
                         │          │
          ┌──────────────┘          └──────────────┐
          │                                        │
┌─────────▼─────────┐                   ┌──────────▼─────────┐
│   Spotify API     │                   │   Gemini Flash     │
│   (spotipy)       │                   │   Agent            │
│   Playlist/Track  │                   │   Vibe             │
│   audio features  │                   │   Clarification    │
└─────────┬─────────┘                   └──────────┬─────────┘
          │                                        │
          └──────────────────┬─────────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Query Constructor  │
                  │  Normalized NumPy   │
                  │  feature vector     │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Playlist Database  │
                  │  (JSON)             │
                  │  - playlist vectors │
                  │  - track IDs        │
                  │  - track vectors    │
                  │  ~500-1000 playlists│
                  │  (from MPD slice)   │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Fallback Retrieval │
                  │  Engine             │
                  │  L1: containment    │
                  │  L2: track similarity│
                  │  L3: vibe similarity │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Hybrid Scorer      │
                  │  Weighted sum of    │
                  │  available signals  │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Gemini Flash       │
                  │  Explanation        │
                  │  Generator          │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │  Results UI         │
                  │  Top 5 + links +    │
                  │  explanations +     │
                  │  confidence labels  │
                  └─────────────────────┘

  ┌───────────────────────┐    ┌──────────────────────────┐
  │  build_database.py    │    │  evaluate.py             │
  │  One-time script      │    │  Test harness            │
  │  MPD slice → Spotify  │    │  All 3 input modes       │
  │  API enrichment →     │    │  → pass/fail summary     │
  │  JSON database file   │    │                          │
  └───────────────────────┘    └──────────────────────────┘
```

---

## 5. Technical Stack

| Component | Tool | Rationale |
|---|---|---|
| UI | Streamlit | Python-native, no HTML/CSS/JS required |
| Spotify data | `spotipy` library | Simple wrapper around Spotify Web API |
| AI agent + explanations | Google Gemini Flash API | Free tier, 1M token context, no credit card required |
| Vector math | NumPy | Cosine similarity in ~3 lines of code |
| Playlist database | JSON file | No database setup needed for MVP |
| Database source | Spotify Million Playlist Dataset (slice) | Provides playlist + track structure; enriched with audio features via Spotify API |
| Database builder | `build_database.py` (one-time script) | Pre-processes MPD slice → Spotify API → JSON |
| Testing | `evaluate.py` (plain Python) | Standalone, runs headlessly |

### Why Gemini Flash over Claude API

Gemini 1.5 Flash is free with no credit card required (15 requests/minute, 1M token context window). It is capable enough for multi-turn conversation, vibe interpretation, and explanation generation. The Python SDK (`google-generativeai`) is straightforward. The architecture does not change — Gemini Flash simply replaces the Claude API calls in the agent and explanation components.

### Why MPD over a manually curated database

The Spotify Million Playlist Dataset provides realistic user-created playlists with natural track diversity. A slice of 500–1000 playlists gives enough corpus for meaningful retrieval while keeping local storage and API enrichment manageable. `build_database.py` runs once at setup time, fetches audio features for each track via the Spotify API, and writes the enriched JSON database. After that, no live API calls are needed during search.

---

## 6. Database Schema

```json
{
  "id": "spotify_playlist_id",
  "name": "Playlist Name",
  "url": "https://open.spotify.com/playlist/...",
  "track_count": 24,
  "description": "Optional playlist description text",
  "dominant_genre": "lofi",
  "dominant_mood": "chill",
  "feature_vector": [0.61, 0.72, 0.45, 0.38, 0.80, 0.55, 0.49],
  "feature_labels": [
    "energy", "danceability", "valence",
    "acousticness", "tempo_norm",
    "genre_centroid", "mood_centroid"
  ],
  "track_ids": [
    "spotify_track_id_1",
    "spotify_track_id_2"
  ],
  "track_features": {
    "spotify_track_id_1": [0.61, 0.72, 0.45, 0.38, 0.80],
    "spotify_track_id_2": [0.44, 0.68, 0.31, 0.62, 0.70]
  }
}
```

`track_ids` enables Level 1 exact containment lookup. `track_features` enables Level 2 similar-track matching. `feature_vector` enables Level 3 playlist vibe matching and is used by all three input modes.

---

## 7. Edge Cases and Guardrails

| Edge Case | Handling |
|---|---|
| Malformed Spotify playlist URL | Validate URL format before API call; surface clear error in UI |
| Malformed Spotify track URL | Validate before API call; prompt user for a valid track link |
| Private or unavailable playlist | Surface clear error; suggest vibe or song mode instead |
| Playlist with fewer than 5 tracks | Flag as low-confidence input; warn that vector may be unrepresentative |
| Reference song not in any indexed playlist | Skip Level 1; proceed to Level 2 then Level 3; label result as fallback |
| Song in too many playlists | Rank by combined containment + vibe score, not containment alone |
| Song in zero indexed playlists | Display: "No exact matches found — showing playlists with similar tracks and vibe" |
| Vague or contradictory vibe description | Agent surfaces the contradiction and asks user to prioritize |
| No strong match in database | Return closest results with Low confidence label |
| Spotify API unavailable | Catch exception; offer fallback to vibe description mode |
| Missing track audio features | Skip missing features in vector construction; log which tracks were dropped |
| Database too small for exact containment | Note clearly that containment only applies to indexed playlists |

---

## 8. Rubric Coverage Map

| Rubric Requirement | How It's Satisfied |
|---|---|
| Identify base project and scope | Section 1.1 — original recommender described accurately |
| Substantial new AI feature | Conversational vibe agent (agentic) + fallback retrieval pipeline (RAG) |
| Feature integrated into working system | All features are part of the core retrieval pipeline, not isolated demos |
| System architecture diagram | Section 4 |
| Working end-to-end demo | Streamlit UI with all 3 input modes demonstrated |
| 2–3 example inputs demonstrated | Covered by evaluation harness + README sample I/O |
| Reliability/guardrail component | `evaluate.py` test harness + input validation + confidence labeling + fallback labeling |
| README with setup + sample I/O | See Section 9 |
| AI collaboration reflection | See Section 10 |
| **Stretch: RAG** | Playlist database indexed as vectors; fallback retrieval = multi-level RAG |
| **Stretch: Agentic workflow** | Multi-step vibe clarification loop with observable intermediate steps |
| **Stretch: Specialized behavior** | Few-shot prompting in Gemini calls for consistent explanation tone and format |
| **Stretch: Test harness** | `evaluate.py` runs all 3 input modes, prints pass/fail summary |

---

## 9. README Requirements (Checklist)

- [ ] Project summary: what VibeSearch does and why it is novel
- [ ] Explanation of all three input modes
- [ ] Architecture diagram
- [ ] Setup: virtual environment, `pip install -r requirements.txt`
- [ ] Spotify API credential setup (Client ID, Client Secret)
- [ ] Gemini Flash API key setup (free at aistudio.google.com)
- [ ] How to build the database: `python build_database.py`
- [ ] How to run: `streamlit run app.py`
- [ ] How to run the evaluation harness: `python evaluate.py`
- [ ] Three sample inputs with expected outputs:
  - One playlist URL
  - One vibe description
  - One reference song URL
- [ ] Known limitations section
- [ ] Rubric coverage map
- [ ] Note that song-to-playlist discovery only works over the indexed playlist database

---

## 10. Reflection Requirements (Checklist)

- [ ] How the project evolved from vibe-only search into contextual playlist discovery
- [ ] Why reference-song fallback retrieval makes the project more original
- [ ] How AI tools (Gemini, Claude Code) were used during development
- [ ] At least one helpful AI suggestion and one flawed or wrong AI suggestion
- [ ] What was learned by building the retrieval pipeline vs. reading about it
- [ ] Why exact Spotify-wide song-to-playlist lookup is not supported in the MVP
- [ ] Limitations: small database, no popularity signal, subjective genre families, binary acoustic preference
- [ ] Future improvements: live playlist crawling, user feedback loop, collaborative filtering, playlist clustering visualizations

---

## 11. Out of Scope (MVP)

- Searching all Spotify playlists globally
- Real-time crawling of public playlists
- User accounts or saved searches
- Collaborative filtering based on user behavior
- Mobile-optimized UI
- Playlist audio preview playback
- Support for Apple Music, YouTube Music, or SoundCloud
- Training a machine learning model on Spotify content
