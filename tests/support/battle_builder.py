"""Test-only document builder (contract 11.7).

It works on primitive documents and builds states only through
``decode_state``. Two rules hold for every helper: no derived values (a
helper never computes anything a clause checks; the test supplies it), and
invalid values pass through untouched. It imports only the standard
library and names in ``imperium.battle.__all__`` (G-BLD-1).
"""

import copy

from imperium.battle import Orientation, Variant, decode_state, encode_state, f01_opening


def opening_document(variant="OPEN", orientation="STANDARD"):
    """``encode_state(f01_opening(...))`` for the named variant and orientation."""
    return encode_state(f01_opening(Variant[variant], Orientation[orientation]))


def as_adversarial(document, label):
    """A deep copy relabelled ADVERSARIAL_TEST with fixture id ``"ADV-" + label``."""
    out = copy.deepcopy(document)
    provenance = out["scenario"]["provenance"]
    provenance["fixture_class"] = "ADVERSARIAL_TEST"
    provenance["fixture_id"] = "ADV-" + label
    return out


def _components(pointer):
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ValueError("a JSON pointer starts with '/'")
    return [p.replace("~1", "/").replace("~0", "~") for p in pointer[1:].split("/")]


def _step(node, component):
    if type(node) is list:
        return node[int(component)]
    return node[component]


def get(document, pointer):
    """The value at ``pointer`` (RFC 6901)."""
    node = document
    for component in _components(pointer):
        node = _step(node, component)
    return node


def edit(document, pointer, value):
    """A deep copy with one value written exactly as given at ``pointer``.

    For an array, the final component may be ``-`` to append. The value
    itself is not copied or converted.
    """
    out = copy.deepcopy(document)
    parts = _components(pointer)
    if not parts:
        return value
    node = out
    for component in parts[:-1]:
        node = _step(node, component)
    last = parts[-1]
    if type(node) is list:
        if last == "-":
            node.append(value)
        else:
            node[int(last)] = value
    else:
        node[last] = value
    return out


def remove(document, pointer):
    """A deep copy with the key or array item at ``pointer`` removed."""
    out = copy.deepcopy(document)
    parts = _components(pointer)
    node = out
    for component in parts[:-1]:
        node = _step(node, component)
    last = parts[-1]
    if type(node) is list:
        del node[int(last)]
    else:
        del node[last]
    return out


def build(document):
    """Exactly ``decode_state(document)``."""
    return decode_state(document)
