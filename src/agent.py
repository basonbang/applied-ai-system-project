"""
Gemini Flash agent: multi-turn vibe clarification + explanation generation.
TODO: implement with google-generativeai SDK.
"""


def get_first_question(vibe_text: str) -> str:
    raise NotImplementedError


def get_next_question(history: list) -> str:
    raise NotImplementedError


def interpret_vibe(vibe_text: str, history: list) -> dict:
    """Returns dict with keys: energy, acousticness, valence, danceability, tempo_norm (all floats 0–1)."""
    raise NotImplementedError


def generate_explanation(result: dict, query_vector: list, mode: str) -> str:
    """Returns a 1–2 sentence plain-English explanation for a playlist match."""
    raise NotImplementedError
