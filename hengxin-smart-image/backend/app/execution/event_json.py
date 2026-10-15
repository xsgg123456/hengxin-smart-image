"""Decode CLI events without relaxing JSON validation for other protocols."""
import json
import re


class _Pairs(list):
    """Retain object pairs so duplicate policy can depend on the exact path."""


def decode_event(raw):
    root = json.loads(raw, object_pairs_hook=_Pairs)

    def convert(value, path=()):
        if isinstance(value, _Pairs):
            result = {}
            duplicates = {}
            for key, child in value:
                if key in result:
                    duplicates.setdefault(key, [result[key]]).append(child)
                result[key] = child
            if duplicates:
                ids = duplicates.get('id', [])
                # CLI 0.162.1 emits an item counter and a search execution ID.
                # Keep the latter, matching existing persisted transcript IDs.
                compatible = (
                    path == ('item',) and duplicates.keys() == {'id'}
                    and result.get('type') == 'web_search'
                    and len(ids) == 2 and all(isinstance(v, str) for v in ids)
                    and re.fullmatch(r'item_[0-9]+', ids[0])
                    and re.fullmatch(r'exec-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', ids[1])
                    and isinstance(root, _Pairs)
                    and [v for k, v in root if k == 'type'] in (
                        ['item.started'], ['item.updated'], ['item.completed']))
                if not compatible:
                    raise ValueError('duplicate event key')
            return {key: convert(child, path + (key,)) for key, child in result.items()}
        if isinstance(value, list):
            return [convert(child, path + (index,)) for index, child in enumerate(value)]
        return value

    event = convert(root)
    if not isinstance(event, dict):
        raise ValueError('Invalid public event')
    return event
