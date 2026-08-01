# Chroma Utilities

A background listener for Cinema 4D. It starts when C4D starts, watches the active document for the whole session, and names things so you don't have to. There's no button and nothing to launch.

**Plugin ID:** `1069542` (registered with Maxon) · **Requires:** Cinema 4D 2026, Python 3.11

## What it does

**Generators inherit their child's name.** Alt-click a generator in the menu or toolbar and C4D inserts it as the parent of your selection — the new Extrude, Cloner, Sweep or Symmetry then takes the name of the object beneath it instead of staying called `Extrude`. It also fires if you create the generator empty and drag a child into it afterwards, since it watches for the result rather than for the click.

**Text objects name themselves after their text.** A Spline Text or MoText object is renamed to the first three words of its own text, and keeps up as you edit. `"Welcome to the show"` becomes `Welcome to the`.

## It won't fight you

The rule for both features is the same: it only touches a name that is **still the default** for that object type, or one **it assigned itself**. The moment you rename something by hand, it backs off that object permanently.

The last name it assigned is stored in the object's own container under the plugin id, so ownership survives saving and reloading the scene. Default names are read from a throwaway instance of the type rather than compared against a hardcoded English list, so it works in any interface language.

It also takes a snapshot when it first sees a document and leaves everything in that snapshot alone. Opening an old scene full of default-named Extrudes won't set off a mass rename — only objects created after the document was opened are eligible.

## Settings

Constants at the top of the `.pyp`:

| Setting | Default | |
|---|---|---|
| `AUTO_NAME_GENERATORS` | `True` | feature 1 on/off |
| `AUTO_NAME_TEXT` | `True` | feature 2 on/off |
| `TEXT_WORD_COUNT` | `3` | words of text to use as the name |
| `TEXT_MAX_CHARS` | `32` | hard cap on a generated name |
| `SKIP_GENERATOR_TYPES` | `set()` | types that keep their default name — add `c4d.Onull` if you'd rather nulls stayed called `Null` |
| `TIMER_MS` | `300` | how often it looks |
| `VERBOSE` | `False` | print every rename |

## Install

Drop the `chroma_utilities` folder into your plugins directory:

```
%APPDATA%\Maxon\Maxon Cinema 4D 2026_<hash>\plugins\
```

Restart Cinema 4D. The console prints `[Chroma Utilities] listening` on load.

## How it works

A `c4d.plugins.MessageData` plugin registered with `RegisterMessagePlugin`. C4D loads it at startup and calls `CoreMessage()` for the rest of the session; `GetTimer()` adds a 300 ms tick on top of the scene-change messages. This is the supported way to run continuously in the background — `SceneHookData`, the other candidate, is not exposed in the 2026 Python SDK.

Object identity comes from `GetGUID()`, which is derived from the object's marker and stays stable across calls, rather than `id()` on the Python wrapper, which does not.

## Known limitations

- **Renames are not undoable.** They happen outside any undo block, because opening one from a background message handler can interleave badly with whatever the user is doing. Ctrl+Z won't put an auto-assigned name back.
- **MoText's text parameter is probed, not assumed.** The 2026 Python SDK exposes no named constant for it, so the plugin tries `PRIM_TEXT_TEXT` and reports once if it comes back empty. If that happens, find the string parameter's id and add it to `TEXT_PARAM_CANDIDATES`.
- **It walks the whole object tree every tick.** Fine on ordinary scenes; on a very heavy one this is the first thing to optimise, by gating the walk on a document dirty check.

## Credit

The always-on `MessageData` + timer + re-entrancy-guard pattern follows [Smart Increment](https://www.romainrosi.com) by Romain Rosi, which uses it to renumber duplicated objects.
