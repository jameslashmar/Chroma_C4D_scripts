"""
Select an object (or tag) in the Object Manager, run this script.
It searches every XPresso tag in the scene, finds the nodes that reference
that object, selects them in the XPresso editor, brings that editor forward
on the right graph, and centres the view on what it found.

Cinema 4D 2026 / Python API. No platform dependency.
"""

import c4d
from c4d.modules import graphview

# --- settings -------------------------------------------------------------

# Bring the XPresso editor forward on the graph that matched, and centre the
# view on the node(s) found.
FOCUS_XPRESSO_EDITOR = True
CENTRE_ON_MATCH = True

# Zoom to land on. 1.0 = 100%. This is yours to pick - the old approach sent
# the editor's 's' key, which zooms hard into a single node and gives you no
# say in it.
CENTRE_ZOOM = 2.0

XPRESSO_EDITOR_ID = 1001148           # "XPresso Editor" in the plugin list

# The view transform lives on the ROOT XGroup's operator container:
#     root.GetDataInstance()
#         .GetContainerInstance(c4d.ID_SHAPECONTAINER)
#         .GetContainerInstance(c4d.ID_OPERATORCONTAINER)
VIEW_ZOOM_ID = 104                    # float, 1.0 = 100%
VIEW_SCROLL_IDS = (102, 103)          # view top-left, in graph units
NODE_POS_IDS = (100, 101)             # node x/y within its canvas
NODE_SIZE_IDS = (108, 109)            # node width/height

# 1. The view transform is readable AND writable, which earlier notes in this
#    repo said was impossible. Measured against a live 2026 session:
#
#        view_centre_in_graph_units = -scroll
#
#    so centring on a point is simply scroll = -point. No viewport size is
#    involved, and none is needed - which is just as well, because C4D gives
#    no way to ask how big the editor is.
#
#    How that was pinned down, because it is easy to get wrong: press 'h' in
#    the editor (frame all) and 's' (frame selection) and read the container
#    each time. Both leave scroll at exactly (0, 0) - 'h' with the graph's
#    bounding box symmetric about the origin, 's' with the selected node's
#    centre on it. The editor re-bases every node coordinate so the view
#    centre is the origin, rather than keeping an offset. That also explains
#    why node coordinates jump wholesale between runs: framing rebases them.
#
#    The sign has to be measured, not assumed. Writing scroll = (500, 0)
#    moves the node to the RIGHT, i.e. the view centre goes to -500. Fitting
#    a model to a single hand-centred sample cannot tell you this: the offset
#    silently absorbs into whatever viewport size you invent, and every
#    centring then lands mirrored about the origin.
#
#    Writing scroll and zoom is navigation, not editing: shifting scroll by
#    thousands of units and root position by hundreds moved 0 of 80 node
#    coordinates in a production rig. Do not confuse ids 102/103 (the view)
#    with 100/101 on the root, which are the root XGroup's own position -
#    writing those really does move the graph's contents.
#
# 2. There is no command that centres an XPresso graph, so don't look for one.
#    Enumerating all 3,390 command plugins shows the entire classic XPresso
#    family is 1001138 "XPresso Pool", 1001145 "XPresso Manager", 1001148 (the
#    editor, blank name) and 1001149 "XPresso" - none of which frames
#    anything. The Frame/Center/Zoom block at 465002xxx belongs to the new
#    node editor (scene and material nodes), not to XPresso.
#
#    In particular 13038 "Frame Selected Elements" is a 3D VIEWPORT command.
#    Per Ferdinand at Maxon it "is grouped together with a whole architecture
#    of viewport commands which first check if they can get hold of the active
#    viewport" (developers.maxon.net/topic/13176). It frames the viewport
#    whichever manager has focus, so it can never centre a graph.
#
# 3. The editor does have hardcoded framing keys - 's' frames the selection,
#    'h' frames the whole graph - and an earlier version of this script drove
#    them with a synthetic Windows keystroke. That worked, but it was
#    Windows-only, it had to be timed against the editor taking keyboard
#    focus, it gave no control over zoom, and if focus landed elsewhere the
#    keystroke framed the 3D viewport instead. Writing the transform directly
#    has none of those problems. Keep 's' in mind only as a manual fallback.
#
# 4. Coordinates are per-canvas: each XGroup has its own. A node inside a
#    group cannot be centred by scrolling the root canvas, because it isn't on
#    it. When the match is nested, this centres on its top-level ancestor
#    instead - the group you need to open - and says so.


def collect_nodes(node, out, top=None):
    """
    Every GvNode, paired with the top-level node it sits under.

    The pairing matters because graph coordinates are relative to the
    containing group's canvas, so only top-level nodes can be centred on
    directly.
    """
    while node:
        anchor = top if top is not None else node
        out.append((node, anchor))
        collect_nodes(node.GetDown(), out, anchor)
        node = node.GetNext()


def get_op_container(node):
    """The node's data container - where its object link lives."""
    for name in ("GetOpContainerInstance", "GetOperatorContainer", "GetDataInstance"):
        fn = getattr(node, name, None)
        if fn:
            try:
                bc = fn()
                if bc is not None:
                    return bc
            except Exception:
                pass
    return None


def container_ids(bc):
    """Every parameter id in a BaseContainer, without touching the values."""
    ids = []

    get_index_id = getattr(bc, "GetIndexId", None)
    if get_index_id:
        try:
            count = len(bc)
        except Exception:
            count = None
        if count is not None:
            for i in range(count):
                cid = get_index_id(i)
                if cid == c4d.NOTOK:
                    break
                ids.append(cid)
            return ids

    # fallback: iterate the container directly
    try:
        for item in bc:
            ids.append(item[0])
    except Exception:
        pass
    return ids


def node_links(node, doc):
    """Every object this node links to (Object nodes, and anything else holding a link)."""
    links = []
    bc = get_op_container(node)
    if bc is None:
        return links

    for cid in container_ids(bc):
        try:
            linked = bc.GetLink(cid, doc)
        except Exception:
            continue
        if linked is not None:
            links.append(linked)
    return links


def all_xpresso_tags(doc):
    """Every XPresso tag in the scene, wherever it lives in the hierarchy."""
    found = []

    def walk(op):
        while op:
            tag = op.GetFirstTag()
            while tag:
                if tag.GetType() == c4d.Texpresso:
                    found.append((op, tag))
                tag = tag.GetNext()
            walk(op.GetDown())
            op = op.GetNext()

    walk(doc.GetFirstObject())
    return found


# --- view transform -------------------------------------------------------

def operator_container(node):
    """
    A node's operator container - position, size, and on the root node the
    editor's view transform. Three containers deep and undocumented.
    """
    try:
        data = node.GetDataInstance()
        if data is None:
            return None
        shape = data.GetContainerInstance(c4d.ID_SHAPECONTAINER)
        if shape is None:
            return None
        return shape.GetContainerInstance(c4d.ID_OPERATORCONTAINER)
    except Exception:
        return None


def node_centre(node):
    """The centre of a node's box, in its canvas's coordinates."""
    bc = operator_container(node)
    if bc is None:
        return None
    try:
        x = float(bc[NODE_POS_IDS[0]])
        y = float(bc[NODE_POS_IDS[1]])
        w = float(bc[NODE_SIZE_IDS[0]])
        h = float(bc[NODE_SIZE_IDS[1]])
    except Exception:
        return None
    return (x + w / 2.0, y + h / 2.0)


def centre_view(master, point, zoom):
    """
    Put `point` (in root-canvas coordinates) at the middle of the editor.

    The view centre is -scroll, so this is just the negated point. The sign is
    measured, not assumed - see note 1.
    """
    root = master.GetRoot()
    if root is None:
        return False
    bc = operator_container(root)
    if bc is None:
        return False

    try:
        bc.SetFloat(VIEW_ZOOM_ID, float(zoom))
        bc.SetFloat(VIEW_SCROLL_IDS[0], -point[0])
        bc.SetFloat(VIEW_SCROLL_IDS[1], -point[1])
    except Exception as exc:
        print("couldn't write the view transform: %s" % exc)
        return False
    return True


# --- editor ---------------------------------------------------------------

def reveal(matched):
    """
    Bring the XPresso editor forward on the graph that matched and centre the
    view on the selected nodes.

    Only one graph can be on screen at a time, so when several matched, the
    first is shown and the rest are named - their nodes stay selected, so
    switching to one of those tags shows the selection already made.
    """
    if not FOCUS_XPRESSO_EDITOR:
        return

    host, tag, master, anchors, nested = matched[0]
    if len(matched) > 1:
        others = ", ".join("'%s'" % m[0].GetName() for m in matched[1:])
        print("showing '%s' - also matched in %s" % (host.GetName(), others))

    # Make the XPresso tag the active one first, so the editor is pointed at
    # this graph before it is asked to do anything with it.
    doc = c4d.documents.GetActiveDocument()
    try:
        doc.SetActiveTag(tag)
        c4d.EventAdd()
    except Exception:
        pass

    if not graphview.OpenDialog(XPRESSO_EDITOR_ID, master):
        print("couldn't open the XPresso editor - nodes are still selected")
        return

    if not CENTRE_ON_MATCH:
        return

    # Centre on the bounding box of everything we're aiming at, so multiple
    # hits all end up on screen rather than just the first.
    points = [p for p in (node_centre(a) for a in anchors) if p]
    if not points:
        print("couldn't read node positions - nodes are still selected")
        return

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    target = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)

    if centre_view(master, target, CENTRE_ZOOM):
        graphview.RedrawMaster(master)
        c4d.EventAdd()
        if nested:
            print("centred on the group holding the match at %d%% - the match "
                  "itself is inside it" % round(CENTRE_ZOOM * 100))
        else:
            print("centred on (%.0f, %.0f) at %d%%"
                  % (target[0], target[1], round(CENTRE_ZOOM * 100)))


def main():
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        print("No active document")
        return

    target = doc.GetActiveObject()
    if not target:
        tags = doc.GetActiveTags()
        target = tags[0] if tags else None
    if not target:
        print("Nothing selected")
        return

    target_name = target.GetName()
    print("Target: %s" % target_name)

    tags = all_xpresso_tags(doc)
    if not tags:
        print("No XPresso tags in this scene")
        return

    total_hits = 0
    matched = []          # (host, tag, master, anchors, nested)

    for host, tag in tags:
        master = tag.GetNodeMaster()
        if not master:
            continue
        root = master.GetRoot()
        if not root:
            continue

        pairs = []
        collect_nodes(root.GetDown(), pairs)

        print("\nXPresso on '%s'  -  %d nodes" % (host.GetName(), len(pairs)))

        exact = []
        by_name = []
        for node, anchor in pairs:
            for linked in node_links(node, doc):
                if linked == target:
                    exact.append((node, anchor))
                    break
                if linked.GetName() == target_name:
                    by_name.append((node, anchor))
                    break

        hits = exact if exact else by_name
        if by_name and not exact:
            print("  (no exact match - falling back to name match)")

        # report + select
        for node, _ in pairs:
            node.DelBit(c4d.BIT_ACTIVE)

        for node, _ in hits:
            node.SetBit(c4d.BIT_ACTIVE)
            print("  selected: %s" % node.GetName())

        total_hits += len(hits)

        if hits:
            # Centre on each hit that sits on the root canvas; for anything
            # nested, aim at its top-level ancestor instead - the group you
            # have to open to reach it.
            anchors = []
            nested = False
            for node, anchor in hits:
                if anchor is not node:
                    nested = True
                if anchor not in anchors:
                    anchors.append(anchor)
            matched.append((host, tag, master, anchors, nested))
        else:
            # nothing matched - dump what IS in there so you can see why
            for node, _ in pairs:
                refs = [l.GetName() for l in node_links(node, doc)]
                print("  %-28s %s" % (node.GetName(), " -> " + ", ".join(refs) if refs else ""))

        graphview.RedrawMaster(master)

    print("\n%d node(s) selected" % total_hits)

    # Commit the selection before asking the editor to act on it.
    c4d.EventAdd()

    if matched:
        reveal(matched)


if __name__ == '__main__':
    main()
