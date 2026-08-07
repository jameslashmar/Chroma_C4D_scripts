"""
Poll whatever the XPresso editor stores about its view, so we can see if zoom
is readable (and maybe settable) from Python.

Run it, zoom the graph with the mouse, run it again. Anything that changes
between runs is part of the view state. Prints to the console AND appends to
a log so runs can be diffed properly.

  Log: C:/Users/james/AppData/Local/Temp/chroma_xpresso_zoom.txt

Watch id 105 in the node master prefs - it read 80.0 in an earlier session,
which is what a zoom percentage looks like. If it tracks the mouse wheel,
graphview.SetPrefs may be able to write it back.

Cinema 4D 2026 / Python API
"""

import c4d
from c4d.modules import graphview

LOG = "C:/Users/james/AppData/Local/Temp/chroma_xpresso_zoom.txt"


def dump_container(bc, label, out):
    """Every id/value in a BaseContainer, flat, without exploding on links."""
    if bc is None:
        out.append("%s: <none>" % label)
        return
    try:
        count = len(bc)
    except Exception:
        out.append("%s: <unreadable>" % label)
        return

    out.append("%s: %d entries" % (label, count))
    for i in range(count):
        try:
            cid = bc.GetIndexId(i)
        except Exception:
            break
        if cid == c4d.NOTOK:
            break
        try:
            val = bc[cid]
        except Exception:
            val = "<unreadable>"
        out.append("    %-8s %-14s %s" % (cid, type(val).__name__, val))


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


def run_number():
    try:
        with open(LOG, "r", encoding="utf-8") as fh:
            return fh.read().count("=== SAMPLE ") + 1
    except Exception:
        return 1


def main():
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        print("No active document")
        return

    out = []
    n = run_number()
    out.append("=== SAMPLE %d ===" % n)

    # graphview module exports - confirm what's actually available in 2026
    out.append("graphview exports: %s"
               % ", ".join(sorted(x for x in dir(graphview)
                                  if not x.startswith("_"))))

    # world/global prefs
    try:
        dump_container(graphview.GetPrefs(), "graphview.GetPrefs()", out)
    except Exception as exc:
        out.append("graphview.GetPrefs(): %s" % exc)

    tag = active_xpresso(doc)
    if tag is None:
        out.append("no XPresso tag found")
    else:
        out.append("tag: '%s' on '%s'" % (tag.GetName(), tag.GetObject().GetName()))

        master = tag.GetNodeMaster()
        if master:
            # THE candidate - watch id 105
            try:
                dump_container(master.GetPrefs(), "master.GetPrefs()", out)
            except Exception as exc:
                out.append("master.GetPrefs(): %s" % exc)

            # the root XGroup's own containers, in case the view rides there
            root = master.GetRoot()
            if root:
                try:
                    data = root.GetDataInstance()
                    dump_container(data, "root.GetDataInstance()", out)
                    shape = data.GetContainerInstance(c4d.ID_SHAPECONTAINER)
                    dump_container(shape, "root ID_SHAPECONTAINER", out)
                    if shape:
                        dump_container(
                            shape.GetContainerInstance(c4d.ID_OPERATORCONTAINER),
                            "root ID_OPERATORCONTAINER", out)
                except Exception as exc:
                    out.append("root containers: %s" % exc)

        dump_container(tag.GetDataInstance(), "tag.GetDataInstance()", out)

    out.append("")
    text = "\n".join(out)

    print(text)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(">> sample %d appended to %s" % (n, LOG))
    except Exception as exc:
        print(">> couldn't write log (%s) - console output above is all of it" % exc)


if __name__ == '__main__':
    main()
