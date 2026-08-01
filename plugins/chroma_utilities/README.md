# Chroma Utilities

A background listener for Cinema 4D. It starts when C4D starts, watches the active document for the whole session, and names things so you don't have to. There's no button and nothing to launch.

**Plugin ID:** `1069542` (registered with Maxon) · **Requires:** Cinema 4D 2026, Python 3.11

## The three features

Each has its own page, and each can be switched off on its own.

### [Parent renamer](docs/generator-parent-renamer.md) · `AUTO_NAME_GENERATORS`

A generator takes the name of the object you put inside it. Alt-click Extrude on a spline called `Logo Outline` and you get an Extrude called `Logo Outline`, not `Extrude`. Works for any generator, and for children dragged in later.

### [Text object renamer](docs/text-object-renamer.md) · `AUTO_NAME_TEXT`

Spline Text and MoText objects name themselves after the first four words of their own text, and keep up as you edit. `Welcome to the show tonight` → `Welcome to the show`.

### [Auto-enumerator](docs/auto-enumerator.md) · `AUTO_INCREMENT`

Duplicates count up properly instead of collecting C4D's `.1` suffix. `Light` → `Light_02` → `Light_03`, with matching children renumbered alongside their parent. Replaces Romain Rosi's Smart Increment — don't run both.

---

## How the three interact

Only one of them ever renames a given object on a given pass, in this order:

1. Generator naming
2. Text naming
3. Increment

The increment runs last and only if nothing more specific claimed the name — a duplicated default-named Extrude is more useful taking its child's name than becoming `Extrude_02`.

## It won't fight you

The rule for all three is the same: it only touches a name that is **still the default** for that object type, or one **it assigned itself**. The moment you rename something by hand, it backs off that object permanently.

- **Ownership survives save and reload.** The last name it assigned is stored in the object's own container under the plugin id, so reopening a scene doesn't reset who owns what.
- **It works in any interface language.** Default names are read from a throwaway instance of the type rather than compared against a hardcoded list of English names.
- **Existing scenes are left alone.** It snapshots each document when it first sees it and never touches anything in that snapshot. Opening an old scene full of default-named Extrudes won't set off a mass rename — only objects created after the document was opened are eligible.
- **Your own renames aren't undone.** Because a hand-typed name breaks ownership immediately, there's no tug-of-war where you rename something and it renames it back a third of a second later.

## Settings

Constants at the top of the `.pyp`:

| Setting | Default | |
|---|---|---|
| `AUTO_NAME_GENERATORS` | `True` | feature 1 on/off |
| `AUTO_NAME_TEXT` | `True` | feature 2 on/off |
| `AUTO_INCREMENT` | `True` | feature 3 on/off |
| `TEXT_WORD_COUNT` | `4` | words of text to use as the name |
| `TEXT_MAX_CHARS` | `32` | hard cap on a generated name |
| `INCREMENT_SEPARATOR` | `"_"` | what sits between stem and number |
| `INCREMENT_PADDING` | `2` | minimum digits, so the second copy is `_02` |
| `SKIP_GENERATOR_TYPES` | `set()` | types that keep their default name — add `c4d.Onull` if you'd rather nulls stayed called `Null` |
| `TIMER_MS` | `300` | how often it looks |
| `VERBOSE` | `False` | print every rename |

## Install

Drop the `chroma_utilities` folder into your plugins directory:

```
%APPDATA%\Maxon\Maxon Cinema 4D 2026_<hash>\plugins\
```

Restart Cinema 4D. The console prints `[Chroma Utilities] listening` on load.

## Building a `.pypv`

The source `.pyp` runs as-is. To ship a compiled copy instead, encrypt it with `c4dpy`, which ships with every C4D install — no GUI needed:

```
c4dpy stub.py -g_encryptPypFile="C:\path\to\chroma_utilities.pyp"
```

The positional `stub.py` is required but its contents don't matter (`pass` is enough) — encryption is a side effect of the flag. The `.pypv` lands **next to the input**, so copy it to the plugin folder and remove the `.pyp`; ship one or the other, not both.

**Don't gate the build on the exit code.** `c4dpy` boots the whole of C4D, so an unrelated plugin can crash at *shutdown* long after encryption succeeded — a `0xC0000409` with a valid `.pypv` on disk is normal. Confirm by the `... encrypted to file:///....pypv` log line and the file's timestamp. A real failure looks different: `0xC0000005` and no `.pypv` produced at all.

## How it works

A `c4d.plugins.MessageData` plugin registered with `RegisterMessagePlugin`. C4D loads it at startup and calls `CoreMessage()` for the rest of the session; `GetTimer()` adds a 300 ms tick on top of the scene-change messages. This is the supported way to run continuously in the background — `SceneHookData`, the other candidate, is not exposed in the 2026 Python SDK.

Object identity comes from `GetGUID()`, which is derived from the object's marker and stays stable across calls, rather than `id()` on the Python wrapper, which does not.

## Known limitations

- **Renames are not undoable.** They happen outside any undo block, because opening one from a background message handler can interleave badly with whatever the user is doing. Ctrl+Z won't put an auto-assigned name back.
- **MoText's text parameter is probed, not assumed.** The 2026 Python SDK exposes no named constant for it, so the plugin tries `PRIM_TEXT_TEXT` and reports once if it comes back empty. If that happens, find the string parameter's id and add it to `TEXT_PARAM_CANDIDATES`.
- **It walks the whole object tree every tick.** Fine on ordinary scenes; on a very heavy one this is the first thing to optimise, by gating the walk on a document dirty check.

## Credit

The always-on `MessageData` + timer + re-entrancy-guard pattern follows [Smart Increment](https://www.romainrosi.com) by Romain Rosi, which uses it to renumber duplicated objects.
