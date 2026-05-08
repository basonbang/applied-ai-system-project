# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name

**Find My Playlist 1.0**

---

## 2. Intended Use

This system suggests 5 songs from a small catalog based on a listener's preferred genre, mood, energy level, and other taste settings. It is built for classroom exploration only — not for real users or production music apps.

It assumes the user can describe their taste as a single fixed profile (one genre, one mood, a few sliders). It does not handle users who like multiple genres, users whose taste changes by time of day, or users who want surprise and discovery.

**Not intended for:** real product recommendations, commercial use, or any setting where bad suggestions could affect user trust or revenue. The catalog is 20 songs — far too small to serve real listeners.

---

## 3. How the Model Works

Every song in the catalog has seven features: genre, mood, energy, tempo, valence (how positive it sounds), danceability, and acousticness. The user provides a profile with their preferred values for each of these.

The system compares each song to the user's profile feature by feature. For genre and mood, it checks whether they match exactly, match within a family of related styles (like "rock" and "metal"), or don't match at all. For the numerical features, it measures how close the song's value is to what the user wants — the closer, the better.

Each feature has a weight that controls how much it matters. Genre has the biggest single weight (0.25), but the five numerical features together add up to 0.60, so a song that nails the vibe but misses the genre can still rank well. The system multiplies each feature's score by its weight, adds them up, and sorts all songs from highest to lowest. The top 5 are returned as recommendations, each with a short explanation of why it scored well.

Think of it like a checklist with priorities. Genre is the most important single checkbox, but if a song checks almost every other box, it can still beat a genre match that fails everywhere else.

---

## 4. Data

The catalog has 20 songs stored in a CSV file. Each song has an ID, title, artist, genre, mood, and five numerical attributes (energy, tempo, valence, danceability, acousticness).

There are 17 different genres across 8 genre families. The largest families are lofi/ambient (4 songs) and electronic/synthwave/house/darkwave (4 songs). Latin and emo each have just 1 song. There are 16 different moods, with "chill" (3 songs) and "happy" (2 songs) being the most common.

No songs were added or removed from the starter dataset. The catalog skews slightly upbeat — average energy is 0.61 and average valence is 0.60, both above the midpoint. There are no hip-hop, R&B, country, reggae, or K-pop songs, so listeners of those genres are completely unserved.

---

## 5. Strengths

The system works well for users whose taste aligns with a well-represented genre family and whose numerical preferences are consistent with that genre's typical sound. A Chill Lofi listener gets Library Rain and Midnight Coding at the top — exactly the quiet, acoustic, mellow tracks you would pick by hand. A Deep Intense Rock listener gets Storm Runner first with a 0.95 score.

The tiered genre and mood matching is a nice touch. It lets "indie pop" partially satisfy a "pop" listener and "metal" partially satisfy a "rock" listener, which feels natural. Without it, a rock fan would get zero credit for metal songs.

The explanations are genuinely useful. Each recommendation says why it scored well (e.g., "Genre match: lofi | Strong valence match (1.00)"), so you can tell whether the system recommended a song for the right reasons or just because the numbers happened to line up.

---

## 6. Limitations and Bias

The proximity formula gives mushier rankings for users with mid-range preferences. If you want energy around 0.5, most songs score 0.7+ on that feature because few songs are more than 0.3 away from the center. Users at the extremes (energy 0.0 or 1.0) get sharper, more meaningful differentiation.

Genre families are unevenly sized. Lofi/ambient and electronic/synthwave each have 4 songs, while Latin and emo have just 1. A Latin fan will see their one matching song surrounded by unrelated genres to fill out the top 5. The system structurally under-serves listeners whose taste falls into small genre families.

Acousticness is treated as a yes/no toggle, but real preference is a spectrum. You either boost all acoustic songs or penalize all of them — there is no way to say "I like moderately acoustic music." Our mood-removal experiment showed that this binary choice can push unexpected songs (like a folk track) into top results purely because their acousticness number is high.

The catalog skews upbeat. Average energy is 0.61 and average valence is 0.60. A user seeking low-energy, low-valence music (like our All-Zero edge case) finds that even the best matches score below 0.57 because the catalog simply lacks enough quiet, sad songs.

---

## 7. Evaluation

We tested six user profiles — three distinct listener types and three adversarial edge cases.

**Standard profiles:**
- **High-Energy Pop** got Sunrise City and Gym Hero at the top — both upbeat pop tracks, exactly right.
- **Chill Lofi** got Library Rain and Midnight Coding — quiet, acoustic lofi, exactly right.
- **Deep Intense Rock** got Storm Runner first at 0.95 — loud, fast rock, exactly right.

**Edge cases:**
- **High Energy + Sad Mood** tested conflicting preferences. The system compromised: pop songs ranked top on genre + energy, but the emo song Broken Neon snuck into #3 on mood alone.
- **Non-existent Genre (country)** showed what happens when genre contributes zero for every song. Rankings became flat and incoherent — no song scored above 0.58.
- **All-Zero Numericals** was the most surprising. The user asked for rock, but got mostly ambient and classical music. Rock songs have high energy (0.91–0.96), so the proximity penalty on five numerical features (0.60 total weight) crushed the genre bonus (0.25 weight).

We also ran an experiment removing mood entirely. Without it, the "High Energy + Sad" profile lost Broken Neon from its top 5 completely, and rankings collapsed into pure genre-plus-energy matching. This confirmed that mood was the main way unexpected songs could surface through vibe alignment.

---

## 8. Future Work

- **Replace the acoustic boolean with a numeric target.** Let users say "I want acousticness around 0.5" instead of forcing a yes/no choice. This would use the same proximity formula as energy and valence, and fix the oversimplification problem we observed.
- **Add a diversity constraint.** Right now the system returns the 5 highest-scoring songs, even if they all sound the same. A simple improvement would be to penalize songs that are too similar to ones already in the list, so the top 5 covers more ground.
- **Handle missing genres gracefully.** When a user asks for a genre that doesn't exist in the catalog, the system should say so instead of silently returning low-confidence results. A fallback strategy — like recommending based on mood and numerical features only, with a warning — would be more honest.

---

## 9. Personal Reflection

My biggest learning moment was realizing just how much planning is required to understand the underlying system for even a basic algorithm. There are tons of different directions and decisions you can make — how to weight features, how to group genres, whether acousticness should be a boolean or a slider — and it is helpful to note them down so you can come back to old ideas or explore different directions. When we removed mood from scoring as an experiment, the entire ranking behavior shifted in ways I would not have predicted just from reading the weights. That one change taught me more about how features interact than anything else in the project.

AI tools like Claude Code practically generated the whole project and guided my direction. I learned a lot about how music recommendation systems work thanks to AI, as well as coding practices like proximity scoring and weighted sums. I made sure to verify and read everything the AI generated, and when code confused me I would ask it to explain and often rewrote it in a simpler way. The AI was strongest at scaffolding and structure, but the interesting decisions — which genre families to group, what edge cases reveal real weaknesses — all required human judgment.

Building this also changed how I think about real music apps. The algorithm treats everyone equally, but equal treatment on unequal data produces unequal outcomes. With only 1 Latin song and 1 emo song, fans of those genres will always get worse recommendations than pop or lofi fans — not because the algorithm is unfair, but because the data is. That is something I will think about differently the next time Spotify gives me a recommendation that feels off.
