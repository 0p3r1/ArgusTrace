"""Validation of tool options at the point they enter the system.

`TOOL_FAMILIES` already declares each option's type, bounds and choices, but
nothing checked incoming values against that: the API accepted a bare dict and
handed it straight to the plugin, so every plugin re-coerced in its own way
and disagreed about failure. Sherlock silently clamped an out-of-range
timeout; recherche-entreprises silently dropped a malformed integer, losing
the filter without telling anyone. Both are the same failure the tri-state
`Status` exists to avoid: quietly doing something other than what was asked.

Validation happens once, here, at the API and CLI boundary. Out-of-range and
unparseable values are refused with a message naming the option rather than
being adjusted behind the user's back. Plugins keep their own defensive
clamping for direct library callers who never pass through this.
"""

from argustrace.plugins.registry import TOOL_FAMILIES

TRUE_STRINGS = {"1", "true", "yes", "on"}
FALSE_STRINGS = {"0", "false", "no", "off", ""}


class OptionError(ValueError):
    """An option value the caller needs to fix. Carries no option *value* for
    secrets — see `_describe`."""


def family_of_plugin(plugin: str) -> str | None:
    """Map a plugin/variant key (e.g. "maigret-full") to its family."""
    for family, info in TOOL_FAMILIES.items():
        if plugin in info["variants"]:
            return family
    return None


def specs_for(family: str) -> dict[str, dict]:
    info = TOOL_FAMILIES.get(family)
    return {opt["name"]: opt for opt in info["options"]} if info else {}


def _describe(spec: dict, value: object) -> str:
    """Render a value for an error message, redacting secrets."""
    return "<redacted>" if spec["type"] == "secret" else repr(value)


def _coerce_int(spec: dict, value: object) -> int:
    name = spec["name"]
    if isinstance(value, bool):  # bool is an int subclass; almost never intended
        raise OptionError(f"option {name!r}: expected an integer, got {value!r}")
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise OptionError(f"option {name!r}: expected an integer, got {value!r}") from None

    low, high = spec.get("min"), spec.get("max")
    if (low is not None and number < low) or (high is not None and number > high):
        bounds = f"{low if low is not None else '-∞'}..{high if high is not None else '∞'}"
        raise OptionError(f"option {name!r}: {number} is outside the accepted range ({bounds})")
    return number


def _coerce_bool(spec: dict, value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in TRUE_STRINGS:
            return True
        if lowered in FALSE_STRINGS:
            return False
    raise OptionError(f"option {spec['name']!r}: expected true or false, got {value!r}")


def _coerce_enum(spec: dict, value: object) -> str:
    choices = spec.get("choices") or []
    if value not in choices:
        raise OptionError(
            f"option {spec['name']!r}: {_describe(spec, value)} is not one of {', '.join(choices)}"
        )
    return str(value)


def _coerce_enum_multi(spec: dict, value: object) -> list[str]:
    choices = spec.get("choices") or []
    if isinstance(value, str):
        # The CLI passes a comma-separated string; the API passes a list.
        value = [part.strip() for part in value.split(",") if part.strip()]
    if not isinstance(value, list):
        raise OptionError(f"option {spec['name']!r}: expected a list, got {value!r}")

    unknown = [v for v in value if v not in choices]
    if unknown:
        raise OptionError(
            f"option {spec['name']!r}: {', '.join(map(str, unknown))} "
            f"not among {', '.join(choices)}"
        )
    return [str(v) for v in value]


def _coerce(spec: dict, value: object):
    kind = spec["type"]
    if kind == "int":
        return _coerce_int(spec, value)
    if kind == "bool":
        return _coerce_bool(spec, value)
    if kind == "enum":
        return _coerce_enum(spec, value)
    if kind == "enum_multi":
        return _coerce_enum_multi(spec, value)
    # "str" and "secret" both arrive as free text; a secret differs only in
    # never being echoed back.
    return str(value)


def validate(plugin: str, raw: dict | None) -> dict:
    """Check `raw` against the registry's declared options for `plugin`.

    Returns the coerced options. Raises OptionError, which the API turns into
    a 422 and the CLI into a usage error.
    """
    family = family_of_plugin(plugin)
    if family is None:
        raise OptionError(f"unknown plugin: {plugin!r}")

    raw = raw or {}
    specs = specs_for(family)

    unknown = sorted(set(raw) - set(specs))
    if unknown:
        known = ", ".join(sorted(specs)) or "(none)"
        raise OptionError(
            f"unknown option(s) for {plugin!r}: {', '.join(unknown)} — accepted: {known}"
        )

    coerced = {}
    for name, spec in specs.items():
        if name not in raw:
            if spec.get("required"):
                raise OptionError(f"option {name!r} is required for {plugin!r}")
            continue
        value = raw[name]
        # An explicit null means "not set", which is how the web form clears
        # a field — that is not the same as an invalid value.
        if value is None:
            continue
        coerced[name] = _coerce(spec, value)
    return coerced
