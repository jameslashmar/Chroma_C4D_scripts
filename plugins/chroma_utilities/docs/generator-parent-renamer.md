# Parent renamer — generators inherit their child's name

*Part of [Chroma Utilities](../README.md). Setting: `AUTO_NAME_GENERATORS`.*

Alt-click a generator in the menu or toolbar and C4D inserts it as the parent of your selection. The new Extrude, Cloner, Sweep or Symmetry then takes the name of the object beneath it, instead of staying called `Extrude`.

| you make | containing | it becomes |
|---|---|---|
| `Extrude` | `Logo Outline` | `Logo Outline` |
| `Cloner` | `Brick` | `Brick` |
| `Symmetry` | `Wing L` | `Wing L` |
| `Sweep` | `Cable Profile` | `Cable Profile` |

## What triggers it

**It watches for the result, not the click.** There is no hook in the C4D API for "user clicked with a modifier held", so intercepting the Alt-click directly isn't possible. Instead it looks for a **default-named object that has acquired a child** — which is what an Alt-click produces.

That turns out to be the better rule, because it fires however the object got there:

- Alt-clicking a generator with something selected
- Dragging an object into an existing generator
- Any script or plugin that reparents something under a fresh generator

**Late children count.** Create the generator empty, then drag a spline into it ten minutes later, and it still names it. Objects created during the session stay eligible until they have been named.

## Rules

- **Any generator, no list to maintain.** The condition is "still has its default name, and has at least one child", so it works for object types the plugin has never heard of, including third-party ones.
- **Named from the first child.** If several objects go in at once, the first child wins.
- **Once only.** After renaming, the name is no longer the type default, so it won't fire again on that object — it won't chase the child if you rename that later.
- **C4D's `.1` suffix is ignored when checking.** A duplicated `Extrude.1` still counts as default-named.

## Nulls

Nulls are included by default, since wrapping something in a null and having it inherit the name is usually what you want. If you'd rather they stayed called `Null`:

```python
SKIP_GENERATOR_TYPES = {c4d.Onull}
```

Any type ids in that set keep their default name no matter what goes inside them.

## When it won't fire

- The object already has a name you (or the plugin) gave it — see [ownership](../README.md#it-wont-fight-you).
- The object has no children.
- The object was already in the document when it was opened. Existing scenes are left alone.
- Its type is in `SKIP_GENERATOR_TYPES`.

## Related

- [Text object renamer](text-object-renamer.md)
- [Auto-enumerator](auto-enumerator.md) — runs only if this one didn't claim the name
