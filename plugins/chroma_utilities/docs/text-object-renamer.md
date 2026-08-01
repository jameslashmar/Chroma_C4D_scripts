# Text object renamer — text objects name themselves after their text

*Part of [Chroma Utilities](../README.md). Setting: `AUTO_NAME_TEXT`.*

A Spline Text or MoText object is renamed to the first few words of its own text, so an Object Manager full of `Text`, `Text.1`, `Text.2` becomes readable at a glance.

| text | name |
|---|---|
| `Welcome to the show tonight` | `Welcome to the show` |
| `Chroma` | `Chroma` |
| `Now\nin\ncinemas` | `Now in cinemas` |

## Rules

- **Four words by default** — `TEXT_WORD_COUNT`.
- **Capped at 32 characters** — `TEXT_MAX_CHARS` — so a single very long word can't produce an unreadable name. The cut is trimmed of trailing spaces.
- **Whitespace is collapsed.** Multi-line text produces one clean single-line name, not a name containing line breaks.
- **It keeps up.** Edit the text and the name follows, because the plugin still owns that name.
- **Empty text changes nothing.** It won't blank out a name while you're mid-edit or clearing the field.

## Taking over, and letting go

It will name a text object that is **still called `Text`** (the type default), and it keeps updating any name **it assigned itself**.

Type your own name over it and it stops immediately and permanently for that object — so if you want `HERO TITLE` to stay `HERO TITLE` while the text says something else, just rename it once.

## Supported types

| type | constant | status |
|---|---|---|
| Spline Text | `c4d.Osplinetext` | confirmed |
| MoText | `c4d.Omgtext` | text parameter probed — see below |

**MoText's text parameter isn't exposed as a named constant in the 2026 Python SDK.** Rather than hardcode a guessed id, the plugin tries the ids in `TEXT_PARAM_CANDIDATES` (starting with `PRIM_TEXT_TEXT`) and uses the first that returns a non-empty string.

If it can't read one, it prints a single line naming the object and its type id rather than failing silently:

```
[Chroma Utilities] couldn't read the text of 'Text' (type 1019268). Run:
[x for x in op.GetDataInstance()] to find the string parameter id, then
add it to TEXT_PARAM_CANDIDATES.
```

Do that once and add the id to the tuple:

```python
TEXT_PARAM_CANDIDATES = (c4d.PRIM_TEXT_TEXT, <the id you found>)
```

## Related

- [Parent renamer](generator-parent-renamer.md)
- [Auto-enumerator](auto-enumerator.md) — runs only if this one didn't claim the name
