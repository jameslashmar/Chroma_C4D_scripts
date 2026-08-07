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

## Driving the editor's view — what is and isn't possible (2026-08-07)

Established by probing a live 2026 session, not from docs. All of it is negative space worth knowing before you spend an evening on it.

> **Read this first: the framing command can hit the 3D viewport instead, so undo it afterwards.** `OpenDialog` only makes the editor active when it actually *opens* it — if the XPresso window is already open it returns `True` and activates nothing. `CallCommand(13038)` then falls through to whichever manager *is* active, and when that is the 3D viewport it frames the selected object there and **zooms the user's viewport**. There is no API to ask which manager is active, so the miss cannot be predicted.
>
> It can be reverted, which is what makes the feature shippable: snapshot the active camera's matrix before the call and restore it if it changed. Use the **local** matrix (`GetMl`/`SetMl`), not the global one — `SetMg` converts through the camera's parent and does not round-trip exactly, leaving drift on every run. Measured over repeated runs, `GetMl`/`SetMl` holds the viewport at 0.0000 units of movement. `c4d.Matrix.__eq__` is a value comparison, so a plain `==` is a sound change test.

**Centring the view on a node cannot be done from a script.** `c4d.CallCommand(13038)` — "Frame Selected Elements" — is the only command that scrolls a graph to its selection, and it dispatches to whichever manager is **active**. A script run has no manager focus, and nothing available in Python makes the XPresso editor active. Every route, tried against a live 2026 session:

| Attempt | Result |
|---|---|
| `CallCommand(13038)` alone | node selected, view unmoved |
| `OpenDialog(1001148, master)` then `13038` | appeared to work **once**, never reproduced |
| `CallCommand(1001145)` then `13038` | `1001145` is the X-Manager, not the editor |
| `CallCommand(1001148)` then `13038` | `IsCommandEnabled(1001148)` is `True`, so it is a real command, but activation is queued for the next message loop and `13038` still reaches the old manager |
| `SendCoreMessage` with `COREMSG_CINEMA_EXECUTEEDITORCOMMAND` + `COREMSG_CINEMA_EXECUTEMANAGER` | accepted, returns a `BaseContainer`, executes nothing |
| `CloseDialog(1001148)` then `OpenDialog` then `13038` | view unmoved |

Confirmed failing both over a socket-plugin bridge **and** when run normally from Extensions → User Scripts, so it isn't an artefact of the test harness.

**When `13038` misses it is not harmless.** It goes to whatever manager *is* active, and if that is the 3D viewport it frames the selected object there and zooms the view the user was working in. Snapshot the active camera's **local** matrix before the call and restore it if it moved (`GetMl`/`SetMl` — `SetMg` converts through the parent and does not round-trip, leaving drift each run). Measured at 0.0000 units across repeated runs.

**Method note.** The single early success was never reproduced under any condition, and building on it cost several rounds of work. One unrepeated positive observation of a UI side effect is noise — reproduce it before designing around it.

The workable pattern is to select the nodes and let the user frame them; the selection is already made when they get there. **`13038` only pans in any case** — it never zooms to fit, even with every node selected, so zoom can't be driven indirectly by widening the selection first.

**Setting the zoom is impossible.** Not merely unexposed:

- `GvNodeGUI` is the graph view's UI layer in the C++ SDK, with `CenterNodes()`, `SetFocus()`, `ShowAllNodes()`, `SetNodePos()` and `GetZoom()` — but **no `SetZoom`**, so no plugin in any language can set it.
- `GvNodeGUI` isn't bridged to Python anyway. `c4d.modules.graphview` exports exactly eleven names — `CloseDialog, GetDefaultOperatorIcon, GetMaster, GetPrefs, GvNode, GvNodeMaster, GvPort, OpenDialog, RedrawMaster, SetPrefs, XPressoTag` — and `GvNodeMaster` has no GUI accessor.
- The editor's View > Zoom entries (25/50/75/100%) have **no command ids**. An enumeration of all 3,390 command plugins turns up one percentage ladder (12.5/25/50/100/200/400/800) which belongs to another manager and stays disabled with XPresso frontmost.
- The only reachable zoom commands, `14063` / `14064`, are the **3D viewport's** — calling them zooms the wrong window.

**Neither prefs container holds the view transform.** `GvNodeMaster.GetPrefs()` returns six unrelated settings (`100=1, 101=0, 102=0, 103=1001, 104=200, 105=80.0`), and `GV_WORLD_CONFIG` carries only undo depth.

**Manager menus aren't reachable from Python.** `c4d.gui.GetMenuResource()` returns a container for `M_EDITOR` only; every manager-menu name tried returns `None`. And `SendCoreMessage` with `COREMSG_CINEMA_EXECUTEEDITORCOMMAND` + `COREMSG_CINEMA_EXECUTEMANAGER` is accepted and returns a container, but does not execute the command in that manager.

The practical upshot: centre, never zoom. The editor's `s` shortcut zooms far too close on a single node; leaving zoom alone means the user sets a comfortable level once and every run lands there.

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
