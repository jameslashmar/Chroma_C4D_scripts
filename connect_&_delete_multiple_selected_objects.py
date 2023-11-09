from typing import Optional
import c4d

doc: c4d.documents.BaseDocument  # The active document
op: Optional[c4d.BaseObject]  # The active object, None if unselected


def main() -> None:
    objs = doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_NONE)
    for obj in objs:
        doc.SetActiveObject(obj)
        c4d.CallCommand(16768)
    c4d.EventAdd()

if __name__ == '__main__':
    main()