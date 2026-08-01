"""
Create Instances of Selected Objects
------------------------------------
For every object selected in the Object Manager, this script creates a
Cinema 4D Instance object that references the original, and names it
"<original name>_instance".

Run from: Script Manager (Extensions > Script Manager) in Cinema 4D.
Tested against the R20+ Python API (c4d).
"""

import c4d


def main():
    # Active document
    doc = c4d.documents.GetActiveDocument()
    if doc is None:
        return

    # Get selected objects (top-level selection in the Object Manager)
    selection = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_SELECTIONORDER)
    if not selection:
        c4d.gui.MessageDialog("Please select at least one object.")
        return

    # Start a single undo step for the whole batch
    doc.StartUndo()

    new_instances = []

    for src in selection:
        # Create a new Instance object
        instance = c4d.BaseObject(c4d.Oinstance)
        if instance is None:
            continue

        # Point the instance at the source object
        instance[c4d.INSTANCEOBJECT_LINK] = src

        # Rename it after the original
        instance.SetName(src.GetName() + "_instance")

        # Insert it into the document (as a sibling, just after the source)
        doc.InsertObject(instance, parent=src.GetUp(), pred=src)

        # Inherit the original's transforms AND frozen transforms so the
        # instance matches both the relative and frozen P/R/S exactly.
        for tid in (
            c4d.ID_BASEOBJECT_REL_POSITION,
            c4d.ID_BASEOBJECT_REL_ROTATION,
            c4d.ID_BASEOBJECT_REL_SCALE,
            c4d.ID_BASEOBJECT_FROZEN_POSITION,
            c4d.ID_BASEOBJECT_FROZEN_ROTATION,
            c4d.ID_BASEOBJECT_FROZEN_SCALE,
        ):
            instance[tid] = src[tid]

        # Register the insertion for undo
        doc.AddUndo(c4d.UNDOTYPE_NEW, instance)

        new_instances.append(instance)

    # Replace the selection with the newly created instances
    doc.SetActiveObject(None, c4d.SELECTION_NEW)
    for instance in new_instances:
        doc.SetActiveObject(instance, c4d.SELECTION_ADD)

    # Close the undo step and refresh the viewport
    doc.EndUndo()
    c4d.EventAdd()


if __name__ == "__main__":
    main()