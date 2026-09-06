"""Stage 3: Action + IT-object candidate gate."""
from __future__ import annotations

from .constants import IT_OBJECTS, SERVICE_ACTIONS
from .models import ClassifierDecision


def apply_action_object(normalized_text: str, max_distance: int = 200) -> ClassifierDecision:
    """Check for service action + IT object pair in text. High-recall gate."""
    found_actions: list[str] = []
    found_objects: list[str] = []

    for action in SERVICE_ACTIONS:
        if action in normalized_text:
            found_actions.append(action)

    for obj in IT_OBJECTS:
        if obj in normalized_text:
            found_objects.append(obj)

    if found_actions and found_objects:
        # Check that at least one pair is within max_distance
        for action in found_actions:
            action_pos = normalized_text.find(action)
            for obj in found_objects:
                obj_pos = normalized_text.find(obj)
                if abs(obj_pos - action_pos) <= max_distance:
                    return ClassifierDecision(
                        candidate=True,
                        confidence=0.85,
                        reason="action_object_pair",
                        detail={
                            "matched_action": action,
                            "matched_object": obj,
                            "all_actions": found_actions,
                            "all_objects": found_objects,
                        },
                    )

    return ClassifierDecision(candidate=False, confidence=0.0, reason="no_action_object_pair")