"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from recommender import load_songs, recommend_songs


def print_recommendations(label: str, user_prefs: dict, songs: list, k: int = 5) -> None:
    """Print top-k recommendations for a user profile."""
    recommendations = recommend_songs(user_prefs, songs, k=k)

    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"  Prefs: {user_prefs}")
    print(f"{'=' * 60}\n")

    for rank, (song, score, explanation) in enumerate(recommendations, 1):
        reasons = explanation.split(" | ")
        print(f"  #{rank}  {song['title']} by {song['artist']}")
        print(f"       Score: {score:.2f}")
        for reason in reasons:
            print(f"         - {reason}")
        print()


def main() -> None:
    songs = load_songs("data/songs.csv")

    # --- Distinct user profiles ---
    profiles = [
        ("High-Energy Pop", {
            "genre": "pop",
            "mood": "happy",
            "energy": 0.9,
            "danceability": 0.85,
            "valence": 0.8,
            "tempo": 0.7,
            "likes_acoustic": False,
        }),
        ("Chill Lofi", {
            "genre": "lofi",
            "mood": "chill",
            "energy": 0.3,
            "danceability": 0.5,
            "valence": 0.6,
            "tempo": 0.2,
            "likes_acoustic": True,
        }),
        ("Deep Intense Rock", {
            "genre": "rock",
            "mood": "intense",
            "energy": 0.95,
            "danceability": 0.6,
            "valence": 0.3,
            "tempo": 0.9,
            "likes_acoustic": False,
        }),
    ]

    # --- Adversarial / edge-case profiles ---
    adversarial = [
        ("EDGE: High Energy + Sad Mood (conflicting vibes)", {
            "genre": "pop",
            "mood": "sad",
            "energy": 0.9,
            "danceability": 0.8,
            "valence": 0.2,
            "tempo": 0.6,
            "likes_acoustic": False,
        }),
        ("EDGE: Non-existent Genre + Extreme Acousticness", {
            "genre": "country",
            "mood": "happy",
            "energy": 0.5,
            "danceability": 0.5,
            "valence": 0.5,
            "tempo": 0.5,
            "likes_acoustic": True,
        }),
        ("EDGE: All-Zero Numericals (minimum everything)", {
            "genre": "rock",
            "mood": "chill",
            "energy": 0.0,
            "danceability": 0.0,
            "valence": 0.0,
            "tempo": 0.0,
            "likes_acoustic": True,
        }),
    ]

    for label, prefs in profiles:
        print_recommendations(label, prefs, songs)

    print("\n" + "#" * 60)
    print("  ADVERSARIAL / EDGE-CASE PROFILES")
    print("#" * 60)

    for label, prefs in adversarial:
        print_recommendations(label, prefs, songs)


if __name__ == "__main__":
    main()
