import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    target_valence: float = 0.5
    target_danceability: float = 0.5
    target_tempo: float = 0.5

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        # TODO: Implement recommendation logic
        return self.songs[:k]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        # TODO: Implement explanation logic
        return "Explanation placeholder"

def load_songs(csv_path: str) -> List[Dict]:
    """Parse a CSV file and return a list of song dicts with typed fields."""
    numeric_fields = {"energy", "tempo_bpm", "valence", "danceability", "acousticness"}
    songs = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)  # reads each row from CSV as a dict, using first row as keys
        for row in reader:
            row["id"] = int(row["id"])  
            for field in numeric_fields:
                row[field] = float(row[field])  
            songs.append(row)
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Return a weighted proximity score and list of match reasons for a song."""
    GENRE_FAMILIES = [
        {"pop", "indie pop"},
        {"lofi", "ambient"},
        {"rock", "metal"},
        {"synthwave", "electronic", "darkwave", "house"},
        {"jazz", "soul", "blues"},
        {"folk", "classical"},
        {"latin"},
        {"emo"},
    ]
    MOOD_FAMILIES = [
        {"chill", "relaxed", "peaceful"},
        {"happy", "euphoric", "festive", "warm"},
        {"intense", "aggressive", "energetic"},
        {"moody", "melancholy", "sad", "dark"},
        {"focused", "nostalgic"},
    ]

    def tiered_match(user_val, song_val, families):
        """Return 1.0 for exact match, 0.5 for same family, or 0.0 for no match."""
        if user_val == song_val:
            return 1.0
        for family in families:
            if user_val in family and song_val in family:
                return 0.5
        return 0.0

    weights = {
        "genre": 0.25,
        "mood": 0.15,
        "energy": 0.15,
        "danceability": 0.12,
        "valence": 0.12,
        "acousticness": 0.11,
        "tempo": 0.10,
    }

    scores = {}
    reasons = []

    # --- Categorical features ---
    scores["genre"] = tiered_match(user_prefs.get("genre", ""), song["genre"], GENRE_FAMILIES)
    if scores["genre"] == 1.0:
        reasons.append(f"Genre match: {song['genre']}")
    elif scores["genre"] == 0.5:
        reasons.append(f"Similar genre: {song['genre']}")

    scores["mood"] = tiered_match(user_prefs.get("mood", ""), song["mood"], MOOD_FAMILIES)
    if scores["mood"] == 1.0:
        reasons.append(f"Mood match: {song['mood']}")
    elif scores["mood"] == 0.5:
        reasons.append(f"Similar mood: {song['mood']}")

    # --- Numerical features (proximity scoring) ---
    for feature in ["energy", "danceability", "valence"]:
        user_target = user_prefs.get(feature, 0.5)
        scores[feature] = 1 - abs(song[feature] - user_target)

    # --- Tempo (normalized proximity) ---
    normalized_tempo = (song["tempo_bpm"] - 60) / 108
    user_tempo_target = user_prefs.get("tempo", 0.5)
    scores["tempo"] = 1 - abs(normalized_tempo - user_tempo_target)

    # --- Acousticness (boolean preference) ---
    likes_acoustic = user_prefs.get("likes_acoustic", True)
    if likes_acoustic:
        scores["acousticness"] = song["acousticness"]
    else:
        scores["acousticness"] = 1 - song["acousticness"]

    # --- Weighted sum ---
    total_score = sum(weights[f] * scores[f] for f in weights)

    # --- Top 2 numerical reasons ---
    numerical_features = ["energy", "danceability", "valence", "acousticness", "tempo"]
    # Each feature is sorted by their score, only taking the top 2 
    top_numerical = sorted(numerical_features, key=lambda f: scores[f], reverse=True)[:2]
    for f in top_numerical:
        reasons.append(f"Strong {f} match ({scores[f]:.2f})")

    return (total_score, reasons)

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Score all songs against user preferences and return the top k sorted by score."""
    scored = []
    for song in songs:
        score, reasons = score_song(user_prefs, song)
        scored.append((song, score, " | ".join(reasons)))

    # Sort songs by their score in descending order, returning the top k
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
