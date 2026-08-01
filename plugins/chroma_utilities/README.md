# Chroma Utilities

A background listener for Cinema 4D. It starts when C4D starts, watches the active document for the whole session, and names things so you don't have to. There's no button and nothing to launch.

**Plugin ID:** `1069542` (registered with Maxon) · **Requires:** Cinema 4D 2026, Python 3.11

## What it does

**Generators inherit their child's name.** Alt-click a generator in the menu or toolbar and C4D inserts it as the parent of your selection — the new Extrude, Cloner, Sweep or Symmetry then takes the name of the object beneath it instead of staying called `Extrude`. It also fires if you create the generator empty and drag a child into it afterwards, since it watches for the result rather than for the click.

**Text objects name themselves after their text.** A Spline Text or MoText object is renamed to the first four words of its own text, and keeps up as you edit. `"Welcome to the show tonight"` becomes `Welcome to the show`.

**Duplicates count up instead of gaining `.1`.** C4D names a copy `Light.1`; this makes it `Light_02`. However the original was numbered, the result normalises onto the same underscore form, and direct children carrying the parent's number follow it up — so duplicating `Camera 02` with a `target 02` inside gives `Camera_03` containing `target_03`.

| duplicate of | becomes |
|---|---|
| `Light` | `Light_02` |
| `Light_02` | `Light_03` |
| `Camera 02` | `Camera_03` |
| `cam 19-2` | `cam_20` |

Names that are only digits are left alone, and it counts past any name already in use rather than creating a clash.

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
