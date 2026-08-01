"""
Select an object (or tag) in the Object Manager, run this script.
It searches every XPresso tag in the scene, finds the nodes that reference
that object, and selects them in the XPresso editor.

Cinema 4D 2026 / Python API
"""

import c4d
from c4d.modules import graphview


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

        if not hits:
            # nothing matched - dump what IS in there so you can see why
            for node in nodes:
                refs = [l.GetName() for l in node_links(node, doc)]
                print("  %-28s %s" % (node.GetName(), " -> " + ", ".join(refs) if refs else ""))

        graphview.RedrawMaster(master)

    print("\n%d node(s) selected" % total_hits)
    c4d.EventAdd()


if __name__ == '__main__':
    main()
