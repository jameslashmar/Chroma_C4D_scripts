"""
Read and write the XPresso editor's view transform.

All of it lives on the ROOT XGroup's operator container:

    root.GetDataInstance()
        .GetContainerInstance(c4d.ID_SHAPECONTAINER)
        .GetContainerInstance(c4d.ID_OPERATORCONTAINER)

    104  float  zoom, 1.0 = 100%          CONFIRMED readable and writable
    102  float  scroll x   } the editor updates these when you pan with the
    103  float  scroll y   } mouse - 100/101 never move
    100  float  root XGroup position x  } writing these MOVES THE GRAPH'S
    101  float  root XGroup position y  } CONTENTS, not the view

(master.GetPrefs() id 105 reads 80.0 regardless and is NOT zoom.)

Set any of the three WRITE_ settings below to a value and run. Leave them all
None for a read-only sample.

Log: C:/Users/james/AppData/Local/Temp/chroma_xpresso_view.txt

Cinema 4D 2026 / Python API
"""

import c4d
from c4d.modules import graphview

# --- what to write (None = leave alone) -----------------------------------

WRITE_ZOOM = None          # float, 1.0 = 100%          -> id 104
WRITE_SCROLL = None        # (x, y) the editor's pan     -> ids 102, 103
WRITE_ROOT_POS = None      # (x, y) moves graph CONTENT  -> ids 100, 101

# --- ids ------------------------------------------------------------------

ZOOM_ID = 104
SCROLL_IDS = (102, 103)
ROOT_POS_IDS = (100, 101)

LOG = "C:/Users/james/AppData/Local/Temp/chroma_xpresso_view.txt"


def active_xpresso(doc):
    """The XPresso tag most likely on screen: the active tag, else the first."""
    try:
        for tag in (doc.GetActiveTags() or []):
            if tag.GetType() == c4d.Texpresso:
                return tag
    except Exception:
        pass

    def walk(op):
        while op:
            tag = op.GetFirstTag()
            while tag:
                if tag.GetType() == c4d.Texpresso:
                    return tag
                tag = tag.GetNext()
            found = walk(op.GetDown())
            if found:
                return found
            op = op.GetNext()
        return None

    return walk(doc.GetFirstObject())


def view_container(master):
    """
    The root XGroup's operator container - the live instance, so writes land
    on the node rather than on a copy.
    """
    root = master.GetRoot()
    if root is None:
        return None
    data = root.GetDataInstance()
    if data is None:
        return None
    shape = data.GetContainerInstance(c4d.ID_SHAPECONTAINER)
    if shape is None:
        return None
    return shape.GetContainerInstance(c4d.ID_OPERATORCONTAINER)


def get(bc, cid):
    try:
        return float(bc[cid])
    except Exception:
        return None


def state(bc):
    return {
        "zoom": get(bc, ZOOM_ID),
        "scroll": (get(bc, SCROLL_IDS[0]), get(bc, SCROLL_IDS[1])),
        "root_pos": (get(bc, ROOT_POS_IDS[0]), get(bc, ROOT_POS_IDS[1])),
    }


def fmt(s):
    return ("zoom=%s  scroll(102,103)=(%s, %s)  root_pos(100,101)=(%s, %s)"
            % (s["zoom"], s["scroll"][0], s["scroll"][1],
               s["root_pos"][0], s["root_pos"][1]))


def main():
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        print("No active document")
        return

    tag = active_xpresso(doc)
    if tag is None:
        print("no XPresso tag found")
        return

    master = tag.GetNodeMaster()
    bc = view_container(master) if master else None
    if bc is None:
        print("couldn't reach the root operator container")
        return

    before = state(bc)
    print("BEFORE  %s" % fmt(before))

    asked = []
    try:
        if WRITE_ZOOM is not None:
            bc.SetFloat(ZOOM_ID, float(WRITE_ZOOM))
            asked.append("zoom -> %s" % float(WRITE_ZOOM))
        if WRITE_SCROLL is not None:
            bc.SetFloat(SCROLL_IDS[0], float(WRITE_SCROLL[0]))
            bc.SetFloat(SCROLL_IDS[1], float(WRITE_SCROLL[1]))
            asked.append("scroll -> (%s, %s)"
                         % (float(WRITE_SCROLL[0]), float(WRITE_SCROLL[1])))
        if WRITE_ROOT_POS is not None:
            bc.SetFloat(ROOT_POS_IDS[0], float(WRITE_ROOT_POS[0]))
            bc.SetFloat(ROOT_POS_IDS[1], float(WRITE_ROOT_POS[1]))
            asked.append("root_pos -> (%s, %s)"
                         % (float(WRITE_ROOT_POS[0]), float(WRITE_ROOT_POS[1])))
    except Exception as exc:
        print("write failed: %s" % exc)

    if not asked:
        print(">> read-only sample. Pan or zoom with the mouse and run again.")
    else:
        try:
            graphview.RedrawMaster(master)
            c4d.EventAdd()
        except Exception as exc:
            print("redraw failed: %s" % exc)

        after = state(bc)
        print("WROTE   %s" % ";  ".join(asked))
        print("AFTER   %s" % fmt(after))

        # Report per field, and say plainly when a value was ALREADY what was
        # asked for - that is not a failure, which the previous version of
        # this script wrongly reported as "the write did not stick".
        for key in ("zoom", "scroll", "root_pos"):
            want = {"zoom": WRITE_ZOOM, "scroll": WRITE_SCROLL,
                    "root_pos": WRITE_ROOT_POS}[key]
            if want is None:
                continue
            if before[key] == after[key]:
                print("   %-9s unchanged - it already held that value"
                      % (key + ":"))
            else:
                print("   %-9s %s -> %s" % (key + ":", before[key], after[key]))

        print(">> now look at the editor: which of those actually moved it?")

    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("BEFORE %s\n" % fmt(before))
            if asked:
                fh.write("WROTE  %s\nAFTER  %s\n"
                         % (";  ".join(asked), fmt(state(bc))))
    except Exception:
        pass


if __name__ == '__main__':
    main()
