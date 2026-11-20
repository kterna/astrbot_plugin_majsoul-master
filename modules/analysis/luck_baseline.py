"""Versioned 13-tile starting-hand baselines and distribution-based scores."""

import json
from pathlib import Path
from typing import Any, Dict


def build_baselines(document: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Derive displayed means and rates from the bundled simulation counts."""
    if document.get("schema_version") != 1 or document.get("hand_size") != 13:
        raise ValueError("Unsupported starting-hand baseline format")
    baselines = {}
    for mode, label in (("4p", "四麻"), ("3p", "三麻")):
        data = document["modes"][mode]
        samples = data["sample_count"]
        counts = {int(key): value for key, value in data["shanten_counts"].items()}
        if (
            type(samples) is not int
            or samples <= 0
            or not counts
            or any(key not in range(7) or type(value) is not int or value < 0 for key, value in counts.items())
            or sum(counts.values()) != samples
        ):
            raise ValueError(f"Invalid {mode} starting-hand baseline counts")
        rewards = data["reward_sums"]
        if any(type(rewards[key]) is not int or rewards[key] < 0 for key in ("normal_dora", "red_dora", "north_tiles")):
            raise ValueError(f"Invalid {mode} starting-hand reward counts")
        baselines[mode] = {
            "label": label,
            "sample_count": samples,
            "shanten_counts": counts,
            "avg_shanten": sum(shanten * count for shanten, count in counts.items()) / samples,
            "good_hands": 100 * sum(count for shanten, count in counts.items() if shanten <= 2) / samples,
            "bad_hands": 100 * sum(count for shanten, count in counts.items() if shanten >= 4) / samples,
            "avg_dora": (rewards["normal_dora"] + rewards["red_dora"]) / samples,
            "avg_north": rewards["north_tiles"] / samples,
        }
    return baselines


with Path(__file__).with_name("luck_baselines.json").open(encoding="utf-8") as stream:
    BASELINE_DOCUMENT = json.load(stream)

BASELINES = build_baselines(BASELINE_DOCUMENT)


def shanten_quality_score(shanten: int, is_3p: bool = False) -> float:
    """Score one 13-tile hand by its midrank; random hands average 50 points.

    A lower shanten gets a higher score. Equal-shanten hands share the middle
    position of their group. Averaging these scores is a hand-quality score,
    not a player's percentile, win probability, or prediction of future draws.
    """
    if type(shanten) is not int or shanten not in range(7):
        raise ValueError("Expected a valid 13-tile shanten in 0..6")
    baseline = BASELINES["3p" if is_3p else "4p"]
    counts = baseline["shanten_counts"]
    worse = sum(count for value, count in counts.items() if value > shanten)
    tied = counts.get(shanten, 0)
    return 100 * (worse + tied / 2) / baseline["sample_count"]
