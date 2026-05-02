import re
import streamlit as st

from src.agent import get_first_question, get_next_question, interpret_vibe
from src.retrieval import search_by_playlist, search_by_vibe, search_by_song, search_spotify_tracks

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="VibeSearch",
    page_icon="🎵",
    layout="centered",
)

# ── Constants ─────────────────────────────────────────────────────────────────

FEATURE_HELP = {
    "energy": (
        "How intense and active the music feels. "
        "0 = very calm and quiet, 1 = very energetic and loud."
    ),
    "acousticness": (
        "Confidence that the playlist is acoustic or instrumental rather than electronic. "
        "1 = fully acoustic (e.g. a classical or folk playlist), 0 = mostly electronic/produced."
    ),
    "valence": (
        "Musical positivity. "
        "1 = happy, uplifting, euphoric. 0 = sad, melancholic, dark."
    ),
    "danceability": (
        "How suitable the music is for dancing based on rhythm and beat. "
        "1 = very danceable, 0 = not danceable at all."
    ),
    "tempo_norm": (
        "Normalized tempo. "
        "0 = very slow (under 60 BPM), 0.5 = moderate (~120 BPM), 1 = very fast (over 180 BPM)."
    ),
}

FEATURE_DISPLAY_NAMES = {
    "energy": "Energy",
    "acousticness": "Acousticness",
    "valence": "Mood",
    "danceability": "Danceability",
    "tempo_norm": "Tempo",
}

CONFIDENCE_COLORS = {
    "High": "🟢",
    "Medium": "🟡",
    "Low": "🔴",
}

SPOTIFY_PLAYLIST_RE = re.compile(
    r"(https?://)?(open\.spotify\.com/playlist/|spotify:playlist:)[A-Za-z0-9]+"
)
SPOTIFY_TRACK_RE = re.compile(
    r"(https?://)?(open\.spotify\.com/track/|spotify:track:)[A-Za-z0-9]+"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_valid_playlist_url(url: str) -> bool:
    return bool(SPOTIFY_PLAYLIST_RE.search(url.strip()))


def is_spotify_track_url(text: str) -> bool:
    return bool(SPOTIFY_TRACK_RE.search(text.strip()))


def extract_track_id(url: str) -> str:
    url = url.strip()
    if "spotify:track:" in url:
        return url.split("spotify:track:")[-1].split("?")[0]
    return url.rstrip("/").split("/")[-1].split("?")[0]


def format_target_value(feature: str, value: float) -> str:
    if feature == "tempo_norm":
        bpm = int(value * 220)
        return f"~{bpm} BPM"
    labels = {
        (0.0, 0.33): "Low",
        (0.33, 0.66): "Mid",
        (0.66, 1.01): "High",
    }
    for (lo, hi), label in labels.items():
        if lo <= value < hi:
            return label
    return f"{value:.2f}"


def clear_vibe_state():
    for key in ["vibe_phase", "vibe_text", "vibe_history", "current_question", "vibe_targets"]:
        st.session_state.pop(key, None)


def clear_song_state():
    for key in ["song_phase", "song_results", "selected_track_id", "selected_track_name"]:
        st.session_state.pop(key, None)


def clear_all_state():
    clear_vibe_state()
    clear_song_state()
    for key in ["results", "results_mode"]:
        st.session_state.pop(key, None)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("How it works")
    st.markdown(
        """
**🎵 Playlist URL**

Paste any public Spotify playlist. VibeSearch fetches its audio features and finds the most
musically similar playlists in our database.

---

**💬 Describe Your Vibe**

Describe the feel you're looking for in plain words — like "late night drive, melancholic, no
lyrics." The AI asks 2–3 clarifying questions, then searches by interpreted audio targets.

---

**🎸 Reference Song**

Enter a song name or Spotify track URL. VibeSearch checks if any indexed playlist contains
the exact song, then falls back to similar-sounding tracks and overall vibe matching.

---

*Searches against a local database of ~500–1000 indexed playlists. Does not search all of
Spotify.*
        """
    )

# ── Header ────────────────────────────────────────────────────────────────────

st.title("VibeSearch")
st.caption("Find playlists by how they sound and feel, not by their name.")
st.markdown(
    "Paste a Spotify playlist URL, describe a vibe in your own words, or enter a reference song — "
    "VibeSearch finds the most musically similar playlists from our indexed database."
)
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["Playlist URL", "Describe Your Vibe", "Reference Song"])

# ── Tab 1: Playlist URL ───────────────────────────────────────────────────────

with tab1:
    st.subheader("Find playlists similar to one you already love")
    url_input = st.text_input(
        "Paste a Spotify playlist URL",
        placeholder="https://open.spotify.com/playlist/...",
        key="playlist_url_input",
    )
    if st.button("Find Playlists", key="search_playlist"):
        if not url_input.strip():
            st.error("Please paste a Spotify playlist URL.")
        elif not is_valid_playlist_url(url_input):
            st.error(
                "Not a valid Spotify playlist URL. "
                "Expected format: open.spotify.com/playlist/..."
            )
        else:
            try:
                with st.spinner("Fetching playlist audio features from Spotify..."):
                    results = search_by_playlist(url_input.strip())
                if not results:
                    st.warning(
                        "This playlist appears to be empty or has no audio features. "
                        "Try a different playlist."
                    )
                else:
                    st.session_state.results = results
                    st.session_state.results_mode = "playlist"
            except Exception as e:
                err = str(e).lower()
                if "not found" in err or "404" in err:
                    st.error(
                        "This playlist is private or unavailable. "
                        "Try the **Describe Your Vibe** tab instead."
                    )
                elif "unauthorized" in err or "401" in err:
                    st.error("Spotify API credentials are invalid. Check your .env file.")
                else:
                    st.error(
                        f"Could not connect to Spotify. Try the **Describe Your Vibe** tab instead.\n\n"
                        f"Details: {e}"
                    )

# ── Tab 2: Describe Your Vibe ─────────────────────────────────────────────────

with tab2:
    phase = st.session_state.get("vibe_phase", "input")

    if phase == "input":
        st.subheader("Describe the vibe you're looking for")
        vibe_text = st.text_area(
            "What does this playlist feel like?",
            placeholder="Sunday morning, raining, making coffee…",
            height=100,
            key="vibe_text_input",
        )
        if st.button("Start", key="vibe_start"):
            if not vibe_text.strip():
                st.warning("Please describe a vibe before continuing.")
            else:
                st.session_state.vibe_phase = "questions"
                st.session_state.vibe_text = vibe_text.strip()
                st.session_state.vibe_history = []
                st.session_state.current_question = get_first_question(vibe_text.strip())
                st.rerun()

    elif phase == "questions":
        st.subheader("A few quick questions")
        history: list[tuple[str, str]] = st.session_state.get("vibe_history", [])

        # Show answered Q&A so far
        for q, a in history:
            st.markdown(f"**Agent:** {q}")
            st.markdown(f"*You:* {a}")
            st.divider()

        current_q = st.session_state.get("current_question", "")
        st.markdown(f"**Agent:** {current_q}")
        answer = st.text_input(
            "Your answer",
            key=f"vibe_ans_{len(history)}",
            placeholder="Type your answer…",
        )

        col_next, col_back = st.columns([1, 1])
        if col_next.button("Next →", key=f"vibe_next_{len(history)}"):
            if not answer.strip():
                st.warning("Please type an answer before continuing.")
            else:
                updated_history = history + [(current_q, answer.strip())]
                st.session_state.vibe_history = updated_history

                if len(updated_history) >= 3:
                    try:
                        with st.spinner("Interpreting your vibe…"):
                            targets = interpret_vibe(
                                st.session_state.vibe_text, updated_history
                            )
                        st.session_state.vibe_targets = targets
                        st.session_state.vibe_phase = "confirm"
                    except Exception as e:
                        st.error(f"Could not interpret vibe: {e}")
                else:
                    next_q = get_next_question(updated_history)
                    st.session_state.current_question = next_q
                st.rerun()

        if col_back.button("Start over", key=f"vibe_back_{len(history)}"):
            clear_vibe_state()
            st.rerun()

    elif phase == "confirm":
        st.subheader("Here's what I'll search for")
        targets: dict = st.session_state.get("vibe_targets", {})

        st.markdown(f"*Based on your vibe: \"{st.session_state.get('vibe_text', '')}\"*")
        st.markdown("")

        cols = st.columns(len(targets))
        for col, (feature, value) in zip(cols, targets.items()):
            col.metric(
                label=FEATURE_DISPLAY_NAMES.get(feature, feature),
                value=format_target_value(feature, value),
                help=FEATURE_HELP.get(feature, ""),
            )

        st.markdown("")
        col_search, col_restart = st.columns([1, 1])

        if col_search.button("Search with these settings", key="vibe_search"):
            try:
                with st.spinner("Finding similar playlists…"):
                    results = search_by_vibe(targets)
                if not results:
                    st.warning("No matching playlists found. Try describing a different vibe.")
                else:
                    st.session_state.results = results
                    st.session_state.results_mode = "vibe"
            except Exception as e:
                st.error(f"Search failed: {e}")

        if col_restart.button("Start over", key="vibe_restart"):
            clear_vibe_state()
            st.rerun()

# ── Tab 3: Reference Song ─────────────────────────────────────────────────────

with tab3:
    st.subheader("Find playlists that contain or feel like a specific song")
    song_query = st.text_input(
        "Song name or Spotify track URL",
        placeholder="Bohemian Rhapsody   or   https://open.spotify.com/track/…",
        key="song_query_input",
    )

    if st.button("Search Spotify", key="song_search"):
        if not song_query.strip():
            st.warning("Please enter a song name or Spotify track URL.")
        elif is_spotify_track_url(song_query):
            track_id = extract_track_id(song_query)
            st.session_state.selected_track_id = track_id
            st.session_state.selected_track_name = song_query.strip()
            st.session_state.song_phase = "ready"
            st.rerun()
        else:
            try:
                with st.spinner("Searching Spotify…"):
                    track_results = search_spotify_tracks(song_query.strip())
                if not track_results:
                    st.warning("No songs found. Try a different search term.")
                else:
                    st.session_state.song_results = track_results
                    st.session_state.song_phase = "pick"
                    st.rerun()
            except Exception as e:
                st.error(f"Spotify search failed: {e}")

    song_phase = st.session_state.get("song_phase")

    if song_phase == "pick":
        results_list: list[dict] = st.session_state.get("song_results", [])
        options = [f"{t['name']} — {t['artist']} ({t['year']})" for t in results_list]
        choice = st.radio("Select the right song:", options, key="song_pick_radio")
        col_use, col_cancel = st.columns([1, 1])
        if col_use.button("Use this song", key="song_use"):
            idx = options.index(choice)
            selected = results_list[idx]
            st.session_state.selected_track_id = selected["id"]
            st.session_state.selected_track_name = f"{selected['name']} — {selected['artist']}"
            st.session_state.song_phase = "ready"
            st.rerun()
        if col_cancel.button("Search again", key="song_cancel"):
            clear_song_state()
            st.rerun()

    if song_phase == "ready":
        track_name = st.session_state.get("selected_track_name", "Selected track")
        st.success(f"Selected: **{track_name}**")
        col_find, col_clear = st.columns([1, 1])
        if col_find.button("Find Playlists", key="song_find"):
            try:
                with st.spinner("Checking playlist database…"):
                    results = search_by_song(st.session_state.selected_track_id)
                if not results:
                    st.warning("No matching playlists found for this song.")
                else:
                    st.session_state.results = results
                    st.session_state.results_mode = "song"
            except Exception as e:
                st.error(f"Search failed: {e}")
        if col_clear.button("Choose a different song", key="song_clear"):
            clear_song_state()
            st.rerun()

# ── Results ───────────────────────────────────────────────────────────────────

if "results" in st.session_state:
    results: list[dict] = st.session_state.results
    mode: str = st.session_state.get("results_mode", "")

    st.divider()

    # Fallback banner for song mode
    if mode == "song" and any(r.get("is_fallback") for r in results):
        st.warning(
            "No exact match found for this song in our database. "
            "Showing playlists with similar energy and mood instead."
        )

    st.subheader("Top Matches")

    for i, result in enumerate(results[:5], 1):
        with st.container(border=True):
            col_name, col_badge = st.columns([5, 1])

            name = result.get("name", "Untitled Playlist")
            url = result.get("url", "")
            track_count = result.get("track_count", 0)
            confidence = result.get("confidence", "Medium")
            is_fallback = result.get("is_fallback", False)
            explanation = result.get("explanation", "")

            if url:
                col_name.markdown(f"**#{i} [{name}]({url})**")
            else:
                col_name.markdown(f"**#{i} {name}**")
            col_name.caption(f"{track_count} tracks")

            dot = CONFIDENCE_COLORS.get(confidence, "⚪")
            if is_fallback:
                col_badge.markdown(f"{dot} {confidence}  \n`via vibe match`")
            else:
                col_badge.markdown(f"{dot} {confidence}")

            if explanation:
                st.markdown(explanation)

    st.divider()
    if st.button("New Search", key="new_search"):
        clear_all_state()
        st.rerun()
