# XPresso scripting notes — Cinema 4D 2026

Notes gathered while writing `find_xpresso_node-OM2XP.py` and `select_xpresso_reference-XP2OM.py` against Cinema 4D 2026 / Python 3.11 (`c4d` classic API, `c4d.modules.graphview`).

These are the things that went wrong repeatedly. The API surface is not what autocomplete or older forum posts suggest, and most of these fail *silently* — the script runs, finds nothing, and looks broken rather than incomplete. Worth reading before writing any new XPresso tooling.

## Walking the graph

**`GvNodeMaster` has no node list.** There is no `GetNodes()`, no `GetFirst()`. You reach the graph with `master.GetRoot()`, which returns the top-level XGroup as a `GvNode`, then walk from `root.GetDown()`.

**Nodes nest, so iteration must recurse.** `root.GetChildren()` returns only the direct children of the top XGroup — anything inside a sub-group is invisible to it. On a real rig almost everything lives inside groups, so a non-recursive walk finds nothing. Walk `GetDown()` / `GetNext()` recursively.

**`GetUp()` returns a fresh Python wrapper every call.** This one is nasty because it fails silently: grouping nodes by `id(node.GetUp())` puts every node in its own bucket even when they share a parent, because the wrapper objects differ. Compare with `==` (which does compare the underlying node), or better, group siblings during the recursive walk so identity never comes up.

## Reading a node's references

**`GvNode` has no `GetOperatorObject()`.** The "Reference" field visible in the node's Attribute Manager is a link stored in the node's own data container. Get the container — `GetOpContainerInstance()`, falling back to `GetOperatorContainer()` / `GetDataInstance()` across versions — then resolve links with `bc.GetLink(id, doc)`.

Scanning every id in the container rather than hardcoding `GV_OBJECT_OBJECT_ID` means the same helper catches object, tag and material links from any node type.

**`BaseContainer` has no `GetCount()` in 2026.** Use `len(bc)` with `GetIndexId(i)` to enumerate parameter ids. Enumerate ids rather than iterating values directly — link values need a document to resolve and can throw during conversion.

## Selection and redraw

**`GvNode` has no `GetTitle()` or `SetSelected()`.** Use `GetName()` for the label, and `SetBit(c4d.BIT_ACTIVE)` / `DelBit(c4d.BIT_ACTIVE)` for selection. Call `c4d.modules.graphview.RedrawMaster(master)` afterwards or the editor won't repaint and the selection change is invisible.

## Driving the editor's view (2026-08-07, corrected)

**Centring the graph on a node works.** An earlier version of this file said it was impossible. That was wrong, and it was wrong because it assumed the mechanism had to be a command.

**The editor's framing is a hardcoded dialog key, not a command plugin.** In the XPresso editor, `S` frames the selection and `H` frames the whole graph. Neither is registered as a command, which is why no command id reaches them — and why they can't be bound in Customise Commands either. Send the keystroke at OS level and it lands:

```python
import ctypes
user32 = ctypes.windll.user32
scan = user32.MapVirtualKeyW(0x53, 0)   # 0x53 = S, 0x48 = H
user32.keybd_event(0x53, scan, 0, 0)    # down
user32.keybd_event(0x53, scan, 2, 0)    # up
```

Windows-only. `find_xpresso_node-OM2XP.py` uses exactly this.

**No command id centres an XPresso graph.** Established by enumerating all 3,390 command plugins in a live 2026 install (`probe_xpresso_commands.py`). The entire classic XPresso family is four entries:

| id | name |
|---|---|
| 1001138 | XPresso Pool |
| 1001145 | XPresso Manager |
| 1001148 | *(blank — the editor itself)* |
| 1001149 | XPresso |

None of them frames anything. There are exactly **three** Zoom In/Out pairs in the whole list: `14063`/`14064` (3D viewport), `1016010`/`1016011`, and `465002325`/`465002326`. That third block also owns `Center Selected`, `Frame Selected`, `Center All`, `Arrange Selected Nodes` and `Show All Ports` — node-graph vocabulary — but it belongs to the **new node editor** (scene and material nodes), not to classic XPresso. There is no fourth block.

**`13038` is a 3D viewport command.** Do not use it for graph work. Per Ferdinand at Maxon it "is grouped together with a whole architecture of viewport commands which first check if they can get hold of the active viewport" ([developers.maxon.net/topic/13176](https://developers.maxon.net/topic/13176)). It frames the viewport whichever manager has focus. Any theory about manager focus built on top of it — and the previous version of this file was full of them — is chasing the wrong thing.

**The keystroke must arrive after the script returns**, because keyboard focus is queued: `CallCommand(1001148)` asks for the editor to become active but the activation is processed on the next message loop. This costs nothing to arrange — `keybd_event` posts to the *Windows* input queue, which C4D only drains on its next message pump, so delivery is already deferred. A timer thread adds ~120ms of margin. Safe off the main thread because `keybd_event` touches no c4d API; nothing else may go in that thread.

**A C4D-side deferral is not available to a script.** `RegisterMessagePlugin` fails from the Script Manager with `cannot find pyp file - plugin registration failed`, so there is no `MessageData` listener for `SpecialEventAdd` to wake. Plugin registration needs a real `.pyp`. Also note `c4d.PLUGINTYPE_MESSAGE` does not exist in 2026 Python (C++ SDK only) — `FindPlugin`'s type argument is optional, so omit it.

**The viewport guard could not be carried over.** `S` and `H` are the 3D viewport's framing keys too, so a keystroke that misses the editor zooms the viewport. The old snapshot-and-restore guard worked only because `CallCommand` was synchronous; with an asynchronous keystroke there is no main-thread moment to read the camera afterwards, and reading it from the timer thread would mean calling the c4d API off-thread. Avoid the miss instead: keep the editor open and run from a keyboard shortcut.

**Zoom — open question.** `GvNodeGUI` (the C++ graph view UI layer) has `GetZoom()` with no setter and isn't bridged to Python. But `GvNodeMaster.GetPrefs()` returns `100=1, 101=0, 102=0, 103=1001, 104=200, 105=80.0`, and **`105 = 80.0` has the shape of a zoom percentage** — previously dismissed as unrelated without testing. `SetPrefs` is in the module exports. `probe_xpresso_zoom.py` samples these while the mouse zooms; if 105 tracks, zoom may be both readable and writable. Untested as of this writing.

**Method note.** The single early "it centred once" observation that the previous session built on was never reproduced, and neither was any command-based theory. The thing that actually broke this open was enumerating the real command list and noticing the editor contributes *nothing* to it — which reframes the question from "which command?" to "it isn't a command". Enumerate before theorising.

## Node layout

**Node position lives three containers deep:** `node.GetDataInstance()` → `GetContainerInstance(c4d.ID_SHAPECONTAINER)` → `GetContainerInstance(c4d.ID_OPERATORCONTAINER)`, then ids 100 and 101 for x/y position and 108 and 109 for x/y size, all via `GetReal` / `SetReal`.

Coordinates are relative to the containing group's canvas, so never mix nodes from different groups in a single alignment pass.

## Matching objects

**Object names are not unique.** Match on object identity (`==`) first and only fall back to name comparison — a rig will happily contain several objects called `Sweep`.

## Known unknown: editor selection in 2026

An adapted version of Arttu Rautio's (aturtur) node line-up script reported "nothing to line up" in at least one case where nodes were visibly selected in the editor, after the recursion and sibling-grouping bugs above were fixed. The remaining suspect is the selection flag itself — it assumes editor selection is stored as `c4d.BIT_ACTIVE` on the node, which is what worked in R25.

If you hit this: print a per-graph diagnostic (`XPresso on '<host>': 61 nodes, 3 selected`) before doing any work. A non-zero selected count with nodes that don't move means the fault is in the alignment maths. Zero selected while nodes are clearly highlighted means `BIT_ACTIVE` is the wrong flag in 2026, and the next step is dumping `GetAllBits()` and `GetNBit()` for a known-selected node to find where the editor actually records selection.

## Redshift materials

A Redshift branch reached through `redshift.GetRSMaterialNodeMaster()` only supports legacy RS materials. Node-space Redshift materials return `None` — report that rather than failing silently. Supporting them properly means going through the `maxon` nodes API, which is a separate piece of work.

## Related: driving two Sweeps from one slider

Not an API note, but the problem that prompted these scripts, and the answer is worth keeping.

To drive two Sweeps sequentially from a single 0–100% slider, don't use the Time node (unreliable under network rendering) or the Memory node. Memory's History Depth counts **evaluation passes, not frames** — a pass happens on every scene evaluation, so scrubbing, viewport interaction and frame-jumping all desynchronise it, and each render node starts with an empty history buffer. It's built for feedback loops, not time offsets.

Offset in slider space with Range Mappers instead: Sweep A takes input 0–50 → output 0–100, Sweep B takes 50–100 → output 0–100, both with Clamp Lower and Clamp Upper enabled. The clamping is what holds A at fully grown while B is still at zero. Overlap the ranges (0–55 and 45–100) for a softer handover. Pure maths off a single value with no retained state, so it's identical on every frame, every scrub and every render node.

Watch for percentage data types carrying 0–1 rather than 0–100 in XPresso — if a Sweep snaps to full growth instantly or barely moves, set the Range Mapper's input and output data types to Percent explicitly.
