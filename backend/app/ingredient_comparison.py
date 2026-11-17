import re
import unicodedata
from collections import defaultdict, deque


_CLASSIFICATION_FIELDS = ("category", "category_label")
_EXPLANATION_FIELDS = (
    "what_it_is",
    "common_purpose",
    "health_considerations",
    "evidence_status",
    "evidence_label",
)


def normalize_ingredient_name(name):
    normalized = unicodedata.normalize("NFKC", name).casefold()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(r"[\W_]+", " ", normalized, flags=re.UNICODE).strip()
    return re.sub(r"\be\s+(\d{3,4})\b", r"e\1", normalized)


def _entries(analysis_result):
    values = analysis_result.get("entries", []) if isinstance(analysis_result, dict) else []
    return [
        entry
        for entry in values
        if isinstance(entry, dict)
        and isinstance(entry.get("name"), str)
        and entry["name"].strip()
    ]


def _field_changes(older, newer, fields):
    changes = []
    for field in fields:
        old_value = older.get(field)
        new_value = newer.get(field)
        if old_value != new_value:
            changes.append(
                {"field": field, "older": old_value, "newer": new_value}
            )
    return changes


def _longest_common_subsequence(first, second):
    lengths = [[0] * (len(second) + 1) for _ in range(len(first) + 1)]
    for first_index in range(len(first) - 1, -1, -1):
        for second_index in range(len(second) - 1, -1, -1):
            if first[first_index] == second[second_index]:
                lengths[first_index][second_index] = (
                    lengths[first_index + 1][second_index + 1] + 1
                )
            else:
                lengths[first_index][second_index] = max(
                    lengths[first_index + 1][second_index],
                    lengths[first_index][second_index + 1],
                )

    matches = set()
    first_index = second_index = 0
    while first_index < len(first) and second_index < len(second):
        if first[first_index] == second[second_index]:
            matches.add((first_index, second_index))
            first_index += 1
            second_index += 1
        elif lengths[first_index + 1][second_index] >= lengths[first_index][second_index + 1]:
            first_index += 1
        else:
            second_index += 1
    return matches


def compare_ingredient_snapshots(older_result, newer_result):
    older_entries = _entries(older_result)
    newer_entries = _entries(newer_result)
    newer_by_name = defaultdict(deque)
    for index, entry in enumerate(newer_entries):
        normalized = normalize_ingredient_name(entry["name"])
        if normalized:
            newer_by_name[normalized].append(index)

    matched = []
    removed = []
    matched_new_indexes = set()
    for older_index, entry in enumerate(older_entries):
        normalized = normalize_ingredient_name(entry["name"])
        matches = newer_by_name[normalized] if normalized else ()
        if matches:
            newer_index = matches.popleft()
            matched_new_indexes.add(newer_index)
            matched.append((older_index, newer_index, normalized))
        else:
            removed.append(
                {
                    "name": entry["name"],
                    "position": older_index + 1,
                    "category": entry.get("category"),
                }
            )

    added = [
        {
            "name": entry["name"],
            "position": index + 1,
            "category": entry.get("category"),
        }
        for index, entry in enumerate(newer_entries)
        if index not in matched_new_indexes
    ]

    older_common = [item for item in matched]
    newer_common = sorted(matched, key=lambda item: item[1])
    stable_order = _longest_common_subsequence(
        [item[2] for item in older_common],
        [item[2] for item in newer_common],
    )
    stable_pairs = {
        (
            older_common[old_common_index][0],
            newer_common[new_common_index][1],
        )
        for old_common_index, new_common_index in stable_order
    }

    unchanged = []
    classification_changes = []
    explanation_changes = []
    order_changes = []
    for older_index, newer_index, _ in matched:
        older_entry = older_entries[older_index]
        newer_entry = newer_entries[newer_index]
        identity = {
            "name": newer_entry["name"],
            "older_name": older_entry["name"],
            "older_position": older_index + 1,
            "newer_position": newer_index + 1,
        }
        unchanged.append(identity)
        classification = _field_changes(
            older_entry, newer_entry, _CLASSIFICATION_FIELDS
        )
        if classification:
            classification_changes.append(
                {**identity, "changes": classification}
            )
        explanations = _field_changes(
            older_entry, newer_entry, _EXPLANATION_FIELDS
        )
        if explanations:
            explanation_changes.append(
                {**identity, "changes": explanations}
            )
        if (older_index, newer_index) not in stable_pairs:
            order_changes.append(identity)

    return {
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "order_changes": order_changes,
        "classification_changes": classification_changes,
        "explanation_changes": explanation_changes,
    }
