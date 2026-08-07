# Chroma_C4D_scripts

A collection of scripts — written by hand or with AI assistance — to automate Windows, Deadline, and repetitive tasks in Cinema 4D.

Everything here is small and self-contained. The scripts are meant to be dropped straight into a script folder or double-clicked; the one plugin is the exception and installs properly.

```
cinema4d/   Python scripts, run from Extensions → User Scripts
windows/    batch and command files, double-click to run
plugins/    installs to the C4D plugins folder, not library\scripts
docs/       API notes worth reading before writing new C4D tooling
```

---

## `cinema4d/` — Cinema 4D scripts (Python)

Run from **Extensions → User Scripts**. See [Installing the Python scripts](#installing-the-python-scripts) below.

The `-OM2XP` / `-XP2OM` suffixes are direction: Object Manager → XPresso, and back again.

### `find_xpresso_node-OM2XP.py`

Select an object (or tag) in the Object Manager, run the script, and it selects the XPresso node(s) that reference that object.

It searches **every** XPresso tag in the scene, so you don't need to know which rig the object is wired into or have the right tag selected first. Nodes nested inside XGroups are found too. Matching is on object identity first, falling back to a name match if nothing exact turns up — useful in a rig with several objects called `Sweep`. If nothing matches, it prints every node and what it references so you can see why.

It then **brings the XPresso editor forward on the graph that matched and centres the view on the node**, so on a big rig you land on it instead of going looking. Where several graphs matched, the first is shown and the rest are named in the console — their nodes stay selected, so switching to one of those tags shows the selection already made.

**The centring can miss, and the script cleans up after it when it does.** `CallCommand(13038)` is the only way to scroll a graph to its selection, and it dispatches to whichever manager is *active*. `OpenDialog` makes the XPresso editor active when it opens it — but if the window is already open it returns `True` and activates nothing, and the command then falls through to the 3D viewport and frames the selected object there instead. C4D offers no way to ask which manager is active, so the miss can't be predicted. It can be undone: `PROTECT_VIEWPORT` snapshots the active camera's **local** matrix before the call and restores it if it changed, so a miss costs you nothing and the console says the graph didn't centre. Measured across repeated runs, the viewport moves 0.0000 units. (Snapshot the local matrix, not the global one — writing a global matrix back converts through the parent and leaves drift on every run.)

**Zoom cannot be set at all**, so nothing here tries. `GvNodeGUI`, the graph view's UI layer in the C++ SDK, exposes `GetZoom()` with no setter, and isn't bridged to Python in the first place; the editor's View > Zoom entries have no command ids; and the only reachable zoom commands drive the 3D viewport.

Written for a 61-node rig (since grown to 80) where hunting for "which node drives this null?" by eye was the bottleneck.

### `select_xpresso_reference-XP2OM.py`

The reverse lookup. Select node(s) in the XPresso editor, run the script, and it selects whatever they reference — object, tag or material — in the Object Manager or Material Manager.

It expands collapsed hierarchy on the way, so the target is actually visible on screen rather than selected somewhere inside a folded group. Handles multiple selected nodes across multiple graphs at once, de-duplicates targets, and prints the full path of everything it selected.

## One at a time, not all at once

The next two both exist for the same reason: **they apply an operation to each selected object individually, instead of treating the selection as one thing.** That's the difference between doing something fifty times and doing it once to fifty objects, and Cinema 4D gives you the second when you usually want the first.

### `multiple-instances_from_multiple-selected.py`

An Instance of **every** selected object, one each, named `<original>_instance`.

Select fifty objects and you get fifty instances — not one instance of the first, and no clicking through them one at a time. Beyond the batching:

- Each instance is inserted as a **sibling directly after its source**, so the hierarchy stays readable instead of everything piling up at the bottom of the Object Manager.
- It copies the source's relative **and frozen** P/R/S, so each instance lands exactly on top of its original rather than at the parent's origin. That's the part that's fiddly to get right by hand.
- The whole batch is **one undo step**.
- The selection is swapped to the new instances afterwards, so you can move them straight away.

### `connect_&_delete_multiple_selected_objects.py`

**Connect Objects + Delete** run on each selected object individually, rather than merging the whole selection into one mesh.

C4D's built-in command collapses a multi-object selection into a single object — which is right when you want one mesh, and wrong when you have fifty separate assemblies to flatten. This iterates instead: fifty selected nulls with children become fifty connected meshes, each keeping its own identity. `c4d.EventAdd()` fires once at the end so the Object Manager redraws cleanly.

---

## `plugins/` — Plugins

### `chroma_utilities/`

A background listener that starts with Cinema 4D and runs for the whole session — no button, nothing to launch. It does five things, each switchable on its own.

**Parent renamer.** A generator takes the name of the object you put inside it. Alt-click Extrude on a spline called `Logo Outline` and you get an Extrude called `Logo Outline`, not `Extrude`. Works for any generator type, and for children dragged in later — it watches for the result rather than for the click.

**Text object renamer.** Spline Text and MoText objects name themselves after the first four words of their own text, and keep up as you edit. `Welcome to the show tonight` becomes `Welcome to the show`.

**Auto-enumerator.** Duplicates count up properly instead of collecting C4D's `.1` suffix: `Light` → `Light_02` → `Light_03`. Whatever numbering the original used is normalised onto the same form, and matching children are renumbered alongside their parent, so duplicating `Camera 02` containing `target 02` gives `Camera_03` containing `target_03`. Replaces Romain Rosi's Smart Increment — don't run both.

**Multi-wire.** Select several XPresso nodes, drag a connection onto a port of one of them, and the same connection is made on all of them — one drag instead of twenty when wiring a rig control into a row of nodes. Disconnecting mirrors too, with a prompt about removing the emptied port. Ports are created when the node accepts them, and existing connections are replaced.

**Duplicate-wire.** Copy an XPresso node and it keeps whatever was feeding it, instead of arriving with every input empty. Only incoming connections — an XPresso input port holds one wire, so reconnecting the copy's output would unplug the original rather than duplicate anything. Duplicating a whole selection works too: the wires between the copied nodes survive on their own, and only the inputs from outside are put back. It never replaces a connection that's already there.

The three renamers only ever touch a name that's still the type default or one the plugin assigned itself, so a hand-typed name is safe, and everything already in a document when it opened is left alone. Settings are constants at the top of the `.pyp`. See [its README](plugins/chroma_utilities/README.md) for the full rules, install and limitations.

Installs to `plugins\`, not `library\scripts\`. Ships as a compiled `.pypv`; the `.pyp` source is kept private.

---

## `windows/` — Windows / pipeline utilities

Double-click to run. All of them prompt for their input, so there are no arguments to remember. `C4D_migration.bat` lives here rather than under `cinema4d/` because it's a Windows batch file that happens to move a C4D install around — nothing in it runs inside Cinema 4D.

### `C4D_migration.bat` — legacy

> **Superseded.** A cross-platform replacement is in development: **C4D Migrator**, a Python tool that auto-detects installed C4D versions, reads `version.h` for the real version numbers, skips C++ plugins on major-version migrations because they won't load anyway, discovers external plugin folders from `plugins.json`, lets you opt in and out of each category from a UI, and writes an HTML report of what it did. This batch script is preserved here, and in that project's `docs/`, as the thing it replaces.
>
> Still fine to use on Windows in the meantime — it works, it just hardcodes a lot.

Migrates a Cinema 4D setup from one release to the next.

Prompts for the old and new release numbers plus the unique install hash from each `%APPDATA%\Maxon\Maxon Cinema 4D <ver>_<hash>` folder, then copies across `new.c4d` (the default scene), user scripts, keyboard shortcuts, browser catalogs, layouts and plugins — from both the AppData and Program Files locations.

It then creates junctions from the commandline (`_x`) and Team Render (`_c`) preference folders back into the main plugins folder for **Greyscalegorilla**, **Motion Manager** and **MSLiveLink**, so render nodes see the same plugins as the workstation without a second copy on disk. Edit that block if you run a different plugin set.

### `run_deadline_custom_delay.bat`

Delayed Deadline Worker startup for a workstation you're about to use yourself.

Kills `deadlinelauncher.exe` and `deadlineworker.exe`, asks how many minutes to wait, counts down, then relaunches both. Use it to take a machine out of the farm for a couple of hours without having to remember to put it back. Assumes a default Deadline 10 install path (`C:\Program Files\Thinkbox\Deadline10\bin`).

### `system shutdown.cmd`

Prompts for a delay in minutes, then shuts the machine down. For leaving an overnight render with a clean end.

### `system standby.cmd`

Same, but suspends to standby instead of shutting down, via `powrprof.dll,SetSuspendState`.

---

## Installing the Python scripts

Drop the `.py` files from `cinema4d/` into your Cinema 4D script folder:

```
%APPDATA%\Maxon\Maxon Cinema 4D 2026_<hash>\library\scripts\
```

They appear under **Extensions → User Scripts**, where they can be bound to a keyboard shortcut or dragged onto a palette.

Cinema 4D caches script files aggressively. If an edit doesn't appear to take effect, reload scripts or restart before assuming the change didn't save.

---

## Compatibility

The XPresso scripts were written and tested against **Cinema 4D 2026 / Python 3.11**, using the classic `c4d` API and `c4d.modules.graphview`. Several API surfaces changed in ways that break older forum examples — those differences are documented in [docs/xpresso-api-notes.md](docs/xpresso-api-notes.md), which is worth reading before writing any new XPresso tooling.

The batch and command files are Windows-only.
