"""
Select an object (or tag) in the Object Manager, run this script.
It searches every XPresso tag in the scene, finds the nodes that reference
that object, selects them in the XPresso editor, brings that editor forward
on the right graph, and centres the view on what it found.

Cinema 4D 2026 / Python API
"""

import c4d
from c4d.modules import graphview

# --- settings -------------------------------------------------------------

# Bring the XPresso editor forward on the graph that matched, and scroll the
# view to the node(s) found.
FOCUS_XPRESSO_EDITOR = True
CENTRE_ON_MATCH = True

# The framing command can miss and hit the 3D viewport instead (see note 3),
# so the viewport camera is snapshotted before it and put back if it moved.
# When the framing lands where it should, this is a no-op.
PROTECT_VIEWPORT = True

XPRESSO_EDITOR_ID = 1001148           # "XPresso Editor" in the plugin list
CMD_FRAME_SELECTED_ELEMENTS = 13038   # the editor's own framing command

# Two things about this, both established by testing against 2026 rather than
# assumed, because neither is documented:
#
# 1. OpenDialog is not optional. CallCommand dispatches to whichever manager
#    is currently active, and a script run from the Script Manager does not
#    make the XPresso editor active - so calling the framing command on its
#    own selects the node and then does nothing visible. Opening the dialog
#    on the master first is what puts the command in front of the right
#    editor.
#
# 2. The zoom level cannot be set, and this deliberately doesn't try. It is
#    not that the call is hard to find - it does not exist. GvNodeGUI is the
#    graph view's UI layer in the C++ SDK and it exposes GetZoom() with no
#    matching setter, so no plugin in any language can set the zoom. It is
#    also not bridged to Python at all: the graphview module exports eleven
#    names and GvNodeGUI (which has CenterNodes() and SetFocus()) is not one
#    of them. The editor's own View > Zoom entries carry no command ids, and
#    the only zoom commands that are reachable, 14063 and 14064, belong to
#    the 3D viewport - calling those zooms the wrong window. Zoom cannot be
#    driven indirectly either: 13038 only ever pans, and leaves zoom
#    untouched even with the whole graph selected.
#
#    That turns out to be the behaviour you want anyway. The editor's own 's'
#    shortcut zooms hard into a single node, which is usually far too close.
#    Because this never touches zoom, setting a comfortable level once by
#    hand means every run afterwards lands the match there.
#
# 3. The framing command can go to the wrong window, so the viewport is put
#    back afterwards. OpenDialog only makes the editor active when it
#    actually opens it - if the XPresso window is already open it returns
#    True and activates nothing. 13038 then falls through to whichever
#    manager IS active, and when that is the 3D viewport it frames the
#    selected object there and zooms the view you were working in. C4D
#    offers no way to ask which manager is active, so the miss can't be
#    predicted or prevented.
#
#    It can be undone, though, which is what PROTECT_VIEWPORT does: read the
#    active camera's matrix before calling, and put it back if it changed.
#    A hit costs nothing (the matrix is untouched and the restore is a
#    no-op); a miss is reverted before anyone sees it. The console says so
#    when it happens, since it means the graph didn't centre either.


def collect_nodes(node, out):
    """Recursively collect every GvNode, including those nested in XGroups."""
    while node:
        out.append(node)
        collect_nodes(node.GetDown(), out)
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


def viewport_camera(doc):
    """
    The camera the active viewport is looking through, and its matrix. A
    scene camera if one is active, otherwise the editor camera - framing
    moves whichever is in use.
    """
    if not PROTECT_VIEWPORT:
        return None
    try:
        bd = doc.GetActiveBaseDraw()
        if bd is None:
            return None
        cam = bd.GetSceneCamera(doc) or bd.GetEditorCamera()
        if cam is None:
            return None
        # The local matrix, not the global one. Writing a global matrix back
        # converts through the camera's parent and doesn't round-trip exactly,
        # so restoring by SetMg leaves a little drift on every run. The local
        # matrix is the camera's own state and goes back untouched.
        return (cam, cam.GetMl())
    except Exception:
        return None


def restore_viewport(state):
    """Put the viewport back if the framing command moved it. True if it did."""
    if state is None:
        return False
    cam, before = state
    try:
        if cam.GetMl() == before:
            return False
        cam.SetMl(before)
    except Exception:
        return False
    return True


def reveal(matched):
    """
    Bring the XPresso editor forward on the graph that matched and scroll the
    view to the selected nodes.

    Only one graph can be on screen at a time, so when several matched, the
    first is shown and the rest are named - their nodes stay selected, so
    switching to one of those tags shows the selection already made.
    """
    if not FOCUS_XPRESSO_EDITOR:
        return

    host, master = matched[0]
    if len(matched) > 1:
        others = ", ".join("'%s'" % h.GetName() for h, _ in matched[1:])
        print("showing '%s' - also matched in %s" % (host.GetName(), others))

    if not graphview.OpenDialog(XPRESSO_EDITOR_ID, master):
        print("couldn't open the XPresso editor - nodes are still selected")
        return

    if CENTRE_ON_MATCH:
        # Only lands because OpenDialog just made this editor the active
        # manager; see the note at the top of the file. Where it doesn't,
        # this frames the object in the 3D viewport instead - so the
        # viewport is put straight back.
        doc = c4d.documents.GetActiveDocument()
        state = viewport_camera(doc)

        c4d.CallCommand(CMD_FRAME_SELECTED_ELEMENTS)

        if restore_viewport(state):
            print("the XPresso editor wasn't the active manager, so that "
                  "framed the 3D viewport instead - put it back, but the "
                  "graph didn't centre. Click in the XPresso editor and run "
                  "again, or set CENTRE_ON_MATCH = False.")
            c4d.EventAdd()


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
    matched = []          # (host, master) for every graph that had a hit

    for host, tag in tags:
        master = tag.GetNodeMaster()
        if not master:
            continue
        root = master.GetRoot()
        if not root:
            continue

        nodes = []
        collect_nodes(root.GetDown(), nodes)

        print("\nXPresso on '%s'  -  %d nodes" % (host.GetName(), len(nodes)))

        exact = []
        by_name = []
        for node in nodes:
            for linked in node_links(node, doc):
                if linked == target:
                    exact.append(node)
                    break
                if linked.GetName() == target_name:
                    by_name.append(node)
                    break

        hits = exact if exact else by_name
        if by_name and not exact:
            print("  (no exact match - falling back to name match)")

        # report + select
        for node in nodes:
            node.DelBit(c4d.BIT_ACTIVE)

        for node in hits:
            node.SetBit(c4d.BIT_ACTIVE)
            print("  selected: %s" % node.GetName())

        total_hits += len(hits)
        if hits:
            matched.append((host, master))

        if not hits:
            # nothing matched - dump what IS in there so you can see why
            for node in nodes:
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
