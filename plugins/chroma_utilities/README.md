# Chroma Utilities

A background listener for Cinema 4D. It starts when C4D starts, watches the active document for the whole session, and names things so you don't have to. There's no button and nothing to launch.

**Version:** 1.3.0 · **Plugin ID:** `1069542` (registered with Maxon) · **Requires:** Cinema 4D 2026, Python 3.11

Four features, each independently switchable:

| | Feature | Setting |
|---|---|---|
| 1 | [Parent renamer](#1-parent-renamer) — generators inherit their child's name | `AUTO_NAME_GENERATORS` |
| 2 | [Text object renamer](#2-text-object-renamer) — text objects name themselves after their text | `AUTO_NAME_TEXT` |
| 3 | [Auto-enumerator](#3-auto-enumerator) — duplicates count up instead of gaining `.1` | `AUTO_INCREMENT` |
| 4 | [Multi-wire](#4-multi-wire) — wire (or unwire) one selected XPresso node, do them all | `MULTI_WIRE` |

---

## 1. Parent renamer

Alt-click a generator in the menu or toolbar and C4D inserts it as the parent of your selection. The new Extrude, Cloner, Sweep or Symmetry then takes the name of the object beneath it, instead of staying called `Extrude`.

| you make | containing | it becomes |
|---|---|---|
| `Extrude` | `Logo Outline` | `Logo Outline` |
| `Cloner` | `Brick` | `Brick` |
| `Symmetry` | `Wing L` | `Wing L` |

**It watches for the result, not the click.** There is no hook in the C4D API for "user clicked with a modifier held", so intercepting the Alt-click isn't possible. Instead it looks for a **default-named object that has acquired a child** — which is what an Alt-click produces. That turns out to be the better rule, because it fires however the object got there: Alt-clicking a generator, dragging an object into an existing one, or any script that reparents something under a fresh generator.

- **Any generator, no list to maintain.** The condition is "still has its default name, and has at least one child", so it works for types the plugin has never heard of, including third-party ones.
- **Named from the first child**, if several go in at once.
- **Late children count.** Create the generator empty, drag a spline in ten minutes later, and it still names it.
- **Once only.** After renaming, the name is no longer the type default, so it won't chase the child if you rename that later.

Nulls are included by default, since wrapping something in a null and inheriting the name is usually what you want. To exempt them, or any other type:

```python
SKIP_GENERATOR_TYPES = {c4d.Onull}
```

## 2. Text object renamer

A Spline Text or MoText object is renamed to the first few words of its own text, so an Object Manager full of `Text`, `Text.1`, `Text.2` becomes readable at a glance.

| text | name |
|---|---|
| `Welcome to the show tonight` | `Welcome to the show` |
| `Chroma` | `Chroma` |

- **Four words by default** (`TEXT_WORD_COUNT`), capped at 32 characters (`TEXT_MAX_CHARS`) so a single very long word can't produce an unreadable name.
- **Whitespace is collapsed**, so multi-line text gives one clean single-line name.
- **It keeps up.** Edit the text and the name follows, because the plugin still owns that name.
- **Empty text changes nothing** — it won't blank a name out while you're mid-edit.

**MoText's text parameter isn't exposed as a named constant in the 2026 Python SDK.** Rather than hardcode a guessed id, the plugin tries the ids in `TEXT_PARAM_CANDIDATES` (starting with `PRIM_TEXT_TEXT`) and uses the first that returns a non-empty string. If none work it prints one line naming the object and its type id rather than failing silently — run `[x for x in op.GetDataInstance()]` on that object to find the string parameter's id, and add it to the tuple.

## 3. Auto-enumerator

C4D names a copy `Light.1`, then `Light.2`, and a copy of *that* `Light.1.1`. This turns them into a proper sequence.

| duplicate of | becomes |
|---|---|
| `Light` | `Light_02` |
| `Light_02` | `Light_03` |
| `Camera 02` | `Camera_03` |
| `cam 19-2` | `cam_20` |

- **Normalises onto one form.** However the original was numbered — space, underscore, hyphen, or not at all — the result is `stem_NN`.
- **Only the first run of digits counts.** `cam 19-2` becomes `cam_20`, not `cam 19-3`.
- **Padded to at least two digits** (`INCREMENT_PADDING`), so names sort correctly. A wider existing number keeps its width: `Sweep_099` → `Sweep_100`.
- **Unnumbered originals start at 02**, since the original is conceptually 01.
- **It won't create a clash.** If the next number is taken it keeps counting, so duplicating `Light` twice gives `Light_02` and `Light_03`.
- **Digit-only names are left alone.** An object called `2001` stays `2001.1` rather than being mangled.

**Children follow the parent.** Direct children carrying the same number as the parent are renumbered to match, so duplicating a `Camera 02` containing a `target 02` gives `Camera_03` containing `target_03` — a rig's internal numbering stays consistent. Children with a different number, or none, are left alone.

The separator is `INCREMENT_SEPARATOR`: set it to `""` or `"-"` for `Light02` or `Light-02`.

**This replaces [Smart Increment](https://www.romainrosi.com) by Romain Rosi**, including its matching-children behaviour, so don't run both — they'd each try to rename the same new object. The difference is output format: Smart Increment preserves the original's numbering style (`Camera 02` → `Camera 03`), this normalises onto the underscore form.

## 4. Multi-wire

Select several XPresso nodes, drag a connection onto a port of **one** of them, and the same connection is made on **all** of them. Wiring a rig control into twenty nodes becomes one drag instead of twenty.

C4D only ever wires the node you dropped on, even with a whole selection highlighted. This watches the graph's connections and reacts when a new one appears on a node that's part of a multi-node selection, then mirrors it — same source port, same destination port — onto every other selected node in that graph.

**Matching the port across nodes** is done on the port's `MainID`/`SubID` pair, which is how "the same port" is identified on sibling nodes, rather than by name or index. Nodes are named in the console by what they link to — `'Object' -> Cube_02` — because a graph full of nodes all called `Object` tells you nothing.

Three rules, each chosen deliberately:

- **Ports are created when the node will accept them.** In XPresso a port only exists once something has been dragged onto it, so the other selected nodes usually have no such port at all — mirroring would never fire without creating it. The plugin asks `AddPortIsOK()` first and only adds a port the node genuinely accepts; a node that refuses is skipped and named in the console. Set `MULTI_WIRE_CREATE_PORTS = False` to only ever wire ports that already exist.
- **Differing types are left to C4D.** XPresso converts between compatible types — a real into a vector drives all three components at once, which is a normal and useful thing to do — so the plugin doesn't pre-judge a mismatch. It attempts the connection and only reports if C4D itself refuses.
- **Existing connections are replaced.** If a target port is already fed by something else, that connection is removed first. This is the destructive one — see the limitation below.

Console output when something is skipped:

```
[Chroma Utilities] XPresso on 'RIG': 'Object' -> Cube_03 won't take port 1102/-1, skipped
[Chroma Utilities] XPresso on 'RIG': C4D refused the connection to 'Object' -> Cube_02 - source is real, port is matrix
```

### Disconnecting

It works the same way in reverse. Unplug a port on one selected node and the same connection is removed from every other selected node.

Only the **equivalent** connection is removed — same source, same port. If another selected node has something different plugged into that port, it's left alone rather than being cleared out on the assumption that you meant it.

**The emptied port is then a question.** C4D leaves a disconnected port in place, which is sometimes what you want and sometimes just clutter. `MULTI_WIRE_REMOVE_EMPTY_PORTS` decides:

| value | behaviour |
|---|---|
| `"ask"` (default) | prompts once per disconnection — not once per node, so unwiring twenty nodes is still one question |
| `True` | always removes the emptied port |
| `False` | always leaves it |

A node that won't release its port says so in the console rather than failing quietly. Set `MULTI_WIRE_DISCONNECT = False` to mirror connections only.

**Selection is read via `c4d.BIT_ACTIVE`**, the same flag the repo's XPresso scripts use. If a node is highlighted in the editor but the plugin doesn't see it as selected, that flag is the first suspect — see the [XPresso notes](../../docs/xpresso-api-notes.md).

---

## How the four interact

Features 1–3 rename objects, and only one of them ever renames a given object on a given pass, in this order:

1. Parent renamer
2. Text object renamer
3. Auto-enumerator

The enumerator runs last and only if nothing more specific claimed the name — a duplicated default-named Extrude with a child in it is more useful taking that child's name than becoming `Extrude_02`.

Feature 4 is independent — it operates on XPresso graphs, not object names, and doesn't interact with the other three.

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
| `MULTI_WIRE` | `True` | feature 4 on/off |
| `MULTI_WIRE_CREATE_PORTS` | `True` | add a port the node accepts, rather than only wiring existing ones |
| `MULTI_WIRE_DISCONNECT` | `True` | mirror disconnections as well as connections |
| `MULTI_WIRE_REMOVE_EMPTY_PORTS` | `"ask"` | `True` / `False` / `"ask"` — what to do with a port left empty by a mirrored disconnection |
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

Restart Cinema 4D. On load the console prints the version and which features are active, so you can tell at a glance whether you're running the build you think you are:

```
[Chroma Utilities] v1.3.0 listening - parent renamer, text renamer, auto-enumerator, multi-wire, multi-unwire
```

If a feature is switched off it's absent from that list. `FAILED to register` in place of `listening` means the plugin loaded but C4D rejected the registration.

The version lives in two places that must agree: the `VERSION` constant near the top of the `.pyp`, and the `VERSION` file beside it. Bump both together.

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
- **MoText's text parameter is probed, not assumed** — see feature 2 above.
- **Multi-wire replaces existing connections, and that isn't undoable either.** If a target port was already fed by something, that connection is removed. Combined with the no-undo limitation above, this is the one feature that can lose work — set `MULTI_WIRE = False` if you'd rather not risk it on a rig you can't easily rebuild.
- **It walks the whole object tree every tick**, and every XPresso graph too. Fine on ordinary scenes; on a very heavy one this is the first thing to optimise, by gating the walk on a document dirty check.

## Credit

The always-on `MessageData` + timer + re-entrancy-guard pattern follows Smart Increment by Romain Rosi, which uses it to renumber duplicated objects.
