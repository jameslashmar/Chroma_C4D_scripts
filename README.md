# Chroma_C4D_scripts

A collection of scripts — written by hand or with AI assistance — to automate Windows, Deadline, and repetitive tasks in Cinema 4D.

Everything here is small, self-contained and meant to be dropped straight into a script folder or double-clicked. Nothing needs installing.

---

## Cinema 4D scripts (Python)

Run from **Extensions → User Scripts**. See [Installing the Python scripts](#installing-the-python-scripts) below.

### `find_xpresso_node.py`

Select an object (or tag) in the Object Manager, run the script, and it selects the XPresso node(s) that reference that object.

It searches **every** XPresso tag in the scene, so you don't need to know which rig the object is wired into or have the right tag selected first. Nodes nested inside XGroups are found too. Matching is on object identity first, falling back to a name match if nothing exact turns up — useful in a rig with several objects called `Sweep`. If nothing matches, it prints every node and what it references so you can see why.

Written for a 61-node rig where hunting for "which node drives this null?" by eye was the bottleneck.

### `select_xpresso_reference.py`

The reverse lookup. Select node(s) in the XPresso editor, run the script, and it selects whatever they reference — object, tag or material — in the Object Manager or Material Manager.

It expands collapsed hierarchy on the way, so the target is actually visible on screen rather than selected somewhere inside a folded group. Handles multiple selected nodes across multiple graphs at once, de-duplicates targets, and prints the full path of everything it selected.

### `connect_&_delete_multiple_selected_objects.py`

Runs **Connect Objects + Delete** on each selected object individually, rather than merging the whole selection into one mesh.

Cinema 4D's built-in command collapses a multi-object selection into a single object. This iterates instead: fifty selected nulls with children become fifty connected meshes, not one. `c4d.EventAdd()` fires once at the end so the Object Manager redraws cleanly.

---

## Plugins

### `plugins/chroma_utilities/`

A background listener that starts with Cinema 4D and runs for the whole session — no button, nothing to launch. It renames a generator after the object you put inside it, so an Alt-clicked Extrude stops being called `Extrude`; it names Spline Text and MoText objects after the first few words of their own text, keeping up as you edit; and it turns C4D's `Light.1` duplicate suffix into a proper `Light_02`, taking matching children with it.

It only ever touches a name that's still the type default or one it assigned itself, so a hand-typed name is safe, and it ignores everything that was already in a document when it opened. Settings are constants at the top of the `.pyp`. See [its README](plugins/chroma_utilities/README.md) for behaviour, install and limitations.

Installs to `plugins\`, not `library\scripts\`.

---

## Windows / pipeline utilities

Double-click to run. All of them prompt for their input, so there are no arguments to remember.

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

Drop the `.py` files into your Cinema 4D script folder:

```
%APPDATA%\Maxon\Maxon Cinema 4D 2026_<hash>\library\scripts\
```

They appear under **Extensions → User Scripts**, where they can be bound to a keyboard shortcut or dragged onto a palette.

Cinema 4D caches script files aggressively. If an edit doesn't appear to take effect, reload scripts or restart before assuming the change didn't save.

---

## Compatibility

The XPresso scripts were written and tested against **Cinema 4D 2026 / Python 3.11**, using the classic `c4d` API and `c4d.modules.graphview`. Several API surfaces changed in ways that break older forum examples — those differences are documented in [docs/xpresso-api-notes.md](docs/xpresso-api-notes.md), which is worth reading before writing any new XPresso tooling.

The batch and command files are Windows-only.
