"""
Reverse lookup: select node(s) in the XPresso editor, run this script.
It finds whatever those nodes reference - object, tag, material - and
selects it in the Object Manager / Material Manager, expanding the
hierarchy so it's actually visible.

Cinema 4D 2026 / Python API
"""

import c4d


def collect_nodes(node, out):
    """Recursively collect every GvNode, including those nested in XGroups."""
    while node:
        out.append(node)
        collect_nodes(node.GetDown(), out)
        node = node.GetNext()


def get_op_container(node):
    """The node's data container - where its links live."""
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

    try:
        for item in bc:
            ids.append(item[0])
    except Exception:
        pass
    return ids


def node_links(node, doc):
    """Every element this node links to."""
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


def reveal_in_om(op):
    """Unfold every ancestor so the object is visible in the Object Manager."""
    parent = op.GetUp()
    while parent:
        for bit in (c4d.NBIT_OM1_FOLD, c4d.NBIT_OM2_FOLD,
                    c4d.NBIT_OM3_FOLD, c4d.NBIT_OM4_FOLD):
            try:
                parent.ChangeNBit(bit, c4d.NBITCONTROL_SET)
            except Exception:
                pass
        parent = parent.GetUp()


def describe(element):
    """Readable path for an element, so the console tells you where it went."""
    name = element.GetName()
    if isinstance(element, c4d.BaseTag):
        host = element.GetObject()
        return "tag '%s' on object '%s'" % (name, host.GetName() if host else "?")
    if isinstance(element, c4d.BaseMaterial):
        return "material '%s'" % name
    if isinstance(element, c4d.BaseObject):
        path = [name]
        parent = element.GetUp()
        while parent:
            path.insert(0, parent.GetName())
            parent = parent.GetUp()
        return "object '%s'" % " / ".join(path)
    return "%s '%s'" % (type(element).__name__, name)


def main():
    doc = c4d.documents.GetActiveDocument()
    if not doc:
        print("No active document")
        return

    # gather every selected node across every XPresso graph in the scene
    selected_nodes = []
    for host, tag in all_xpresso_tags(doc):
        master = tag.GetNodeMaster()
        if not master:
            continue
        root = master.GetRoot()
        if not root:
            continue

        nodes = []
        collect_nodes(root.GetDown(), nodes)
        for node in nodes:
            if node.GetBit(c4d.BIT_ACTIVE):
                selected_nodes.append((host, node))

    if not selected_nodes:
        print("No XPresso nodes selected - click a node in the XPresso editor first")
        return

    print("%d node(s) selected:" % len(selected_nodes))

    # collect referenced elements, de-duplicated, order preserved
    targets = []
    for host, node in selected_nodes:
        links = node_links(node, doc)
        print("  %s  (on '%s')  -> %s" % (
            node.GetName(),
            host.GetName(),
            ", ".join(describe(l) for l in links) if links else "no reference"))
        for linked in links:
            if not any(linked == t for t in targets):
                targets.append(linked)

    if not targets:
        print("\nNothing referenced by those nodes")
        return

    objects = [t for t in targets if isinstance(t, c4d.BaseObject)]
    tags = [t for t in targets if isinstance(t, c4d.BaseTag)]
    materials = [t for t in targets if isinstance(t, c4d.BaseMaterial)]

    print("")

    # objects - plus the host object of any referenced tag, so it's on screen
    first = True
    for op in objects:
        reveal_in_om(op)
        doc.SetActiveObject(op, c4d.SELECTION_NEW if first else c4d.SELECTION_ADD)
        first = False
        print("selected %s" % describe(op))

    for tg in tags:
        host = tg.GetObject()
        if host:
            reveal_in_om(host)
            doc.SetActiveObject(host, c4d.SELECTION_NEW if first else c4d.SELECTION_ADD)
            first = False
        doc.SetActiveTag(tg, c4d.SELECTION_NEW if tg is tags[0] else c4d.SELECTION_ADD)
        print("selected %s" % describe(tg))

    for mat in materials:
        doc.SetActiveMaterial(mat, c4d.SELECTION_NEW if mat is materials[0] else c4d.SELECTION_ADD)
        print("selected %s" % describe(mat))

    c4d.EventAdd()


if __name__ == '__main__':
    main()
