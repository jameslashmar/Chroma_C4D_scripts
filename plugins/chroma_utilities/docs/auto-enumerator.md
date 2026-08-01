# Auto-enumerator — duplicates count up instead of gaining `.1`

*Part of [Chroma Utilities](../README.md). Setting: `AUTO_INCREMENT`.*

C4D names a copy `Light.1`, then `Light.2`, and a copy of *that* `Light.1.1`. This turns them into a proper sequence: `Light_02`, `Light_03`, `Light_04`.

| duplicate of | becomes |
|---|---|
| `Light` | `Light_02` |
| `Light_02` | `Light_03` |
| `Camera 02` | `Camera_03` |
| `cam 19-2` | `cam_20` |
| `Extrude` | `Extrude_02` |

## Rules

- **Normalises onto one form.** However the original was numbered — space, underscore, hyphen, or not numbered at all — the result is `stem_NN`. Duplicating `Camera 02` gives `Camera_03`, not `Camera 03`.
- **Only the first run of digits counts.** `cam 19-2` becomes `cam_20`, not `cam 19-3`. The `19` is treated as the number and the rest is dropped.
- **Padded to at least two digits** (`INCREMENT_PADDING`), so the second copy is `_02` and names sort correctly in the Object Manager. An existing wider number keeps its width — `Sweep_099` goes to `Sweep_100`.
- **Unnumbered originals start at 02.** `Light` → `Light_02`, because the original is conceptually 01.
- **It won't create a clash.** If the next number is already in use somewhere in the scene it keeps counting until it finds a free one, so duplicating `Light` twice gives `Light_02` and `Light_03` rather than two `Light_02`s.
- **Digit-only names are left alone.** An object called `2001` stays `2001.1` rather than being mangled into something meaningless.

## Children follow the parent

Direct children carrying the **same number as the parent** are renumbered to match. Duplicating a `Camera 02` that contains a `target 02` gives:

```
Camera_03
└─ target_03
```

not `Camera_03` containing a stale `target 02`. This keeps a rig's internal numbering consistent when you copy the whole assembly. Children with a different number, or no number, are left alone.

## Separator and padding

```python
INCREMENT_SEPARATOR = "_"    # "" gives Light02, "-" gives Light-02
INCREMENT_PADDING   = 2      # 3 gives Light_002
```

## When it won't fire

- The name doesn't end in C4D's `.N` duplicate suffix — it only ever acts on an actual duplicate.
- The name is nothing but digits.
- Another feature already claimed the name this pass. The enumerator runs **last**: a duplicated default-named `Extrude` with a child in it is more useful taking that child's name than becoming `Extrude_02`.
- The object was already in the document when it was opened.

## Replaces Smart Increment

This covers what [Smart Increment](https://www.romainrosi.com) by Romain Rosi did, including the matching-children behaviour, so the two shouldn't be run together — both would try to rename the same new object. The difference is the output format: Smart Increment preserves the original's numbering style (`Camera 02` → `Camera 03`), while this normalises everything onto the underscore form (`Camera 02` → `Camera_03`).

## Related

- [Parent renamer](generator-parent-renamer.md)
- [Text object renamer](text-object-renamer.md)
