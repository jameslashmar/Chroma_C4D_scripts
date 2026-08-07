"""
Select an object (or tag) in the Object Manager, run this script.
It searches every XPresso tag in the scene, finds the nodes that reference
that object, selects them in the XPresso editor, brings that editor forward
on the right graph, and centres the view on what it found.

Cinema 4D 2026 / Python API. Windows only for the centring step - see note 2.
"""

import c4d
from c4d.modules import graphview

try:
    import ctypes
except Exception:
    ctypes = None

try:
    import threading
except Exception:
    threading = None

# --- settings -------------------------------------------------------------

# Bring the XPresso editor forward on the graph that matched, and scroll the
# view to the node(s) found.
FOCUS_XPRESSO_EDITOR = True
CENTRE_ON_MATCH = True

# Which of the editor's built-in view keys to send.
#   "S" - frame the selection. Centres on the match, but zooms in hard; on a
#         single node that is usually closer than you want.
#   "H" - frame the whole graph. Doesn't centre on the match, but the match is
#         selected and highlighted, so it's easy to spot in context.
CENTRE_KEY = "S"

# Milliseconds to wait before sending the key, so C4D has drained its event
# queue and the editor has actually taken keyboard focus. Delivery is already
# deferred past the end of this script by the Windows input queue - this just
# widens the gap. Raise it if the key seems to land too early; 0 sends inline.
KEY_DELAY_MS = 120

XPRESSO_EDITOR_ID = 1001148           # "XPresso Editor" in the plugin list

VK_CODES = {"S": 0x53, "H": 0x48}

# 1. There is no command that centres an XPresso graph. Not hidden, not
#    undocumented - it does not exist.
#
#    Established by enumerating all 3,390 command plugins in a live 2026
#    install (probe_xpresso_commands.py). The whole classic XPresso family is
#    four entries - 1001138 "XPresso Pool", 1001145 "XPresso Manager",
#    1001148 (the editor, blank name) and 1001149 "XPresso" - and not one of
#    them frames anything. There are exactly three Zoom In/Out pairs in the
#    entire list: 14063/14064 (3D viewport), 1016010/1016011, and
#    465002325/465002326. That last block also owns "Arrange Selected Nodes"
#    and "Show All Ports", so it belongs to the *new* node editor (scene and
#    material nodes), not to XPresso. There is no fourth block.
#
#    The editor's View menu entries are internal dialog ids, not command
#    plugins. That is also why they can't be bound in Customise Commands.
#
#    Do not use 13038 "Frame Selected Elements" for this. It is a 3D VIEWPORT
#    command - per Ferdinand at Maxon it "is grouped together with a whole
#    architecture of viewport commands which first check if they can get hold
#    of the active viewport" (developers.maxon.net/topic/13176). It frames the
#    viewport whichever manager has focus, so it can never centre a graph, and
#    any theory about manager focus built on top of it is chasing the wrong
#    thing.
#
# 2. What does work is the editor's own hardcoded keys. Pressing S in the
#    XPresso editor frames the selection and H frames the whole graph. They're
#    built into the dialog rather than registered as commands, which is
#    exactly why nothing in the command list could reach them.
#
#    So the script sends a synthetic keystroke (Windows keybd_event via
#    ctypes) instead of calling a command. That makes the centring step
#    Windows-only; on other platforms it is skipped and reported.
#
# 3. The keystroke has to arrive *after* this script returns, because
#    keyboard focus is queued. CallCommand(XPRESSO_EDITOR_ID) asks for the
#    editor to become active, but the activation is processed on the next
#    message loop - anything sent on the following line reaches whatever had
#    focus before, usually the Object Manager or the viewport.
#
#    That deferral is free here. keybd_event posts to the *Windows* input
#    queue, and C4D only drains that on its next message pump - which is after
#    this script has returned and the queued focus change has been handled.
#    KEY_DELAY_MS just widens the gap via a timer thread. Safe off the main
#    thread because keybd_event is a pure Win32 call touching no c4d API.
#
#    A C4D-side deferral is not an option anyway: RegisterMessagePlugin fails
#    from the Script Manager with "cannot find pyp file", so there is no
#    MessageData listener for SpecialEventAdd to wake. Plugin registration
#    needs a real .pyp file.
#
# 4. S and H are the 3D viewport's framing keys too, so if the editor doesn't
#    take keyboard focus the keystroke frames the viewport instead and zooms
#    the view you were working in.
#
#    This is NOT guarded against, and can't easily be. Detecting it means
#    reading the camera after the key has been processed, which happens on a
#    later message loop with no callback available to run there - and doing it
#    from the timer thread would mean calling the c4d API off the main thread.
#    An earlier version of this script snapshotted and restored the camera
#    around a synchronous CallCommand; that guard cannot be carried over to an
#    asynchronous keystroke.
#
#    So if it misses, your viewport zooms and you undo it by hand. The way to
#    avoid the miss is to give the editor focus yourself: keep the XPresso
#    window open and run this from a keyboard shortcut.
#
# 5. Zoom level still can't be set directly, and this doesn't try. GvNodeGUI
#    is the graph view's UI layer in the C++ SDK and exposes GetZoom() with no
#    matching setter, and it isn't bridged to Python anyway. If S lands you
#    closer than you like, switch CENTRE_KEY to "H".


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


# --- keystroke ------------------------------------------------------------

def send_key(ch):
    """
    Tap a key at the OS level, so it lands in whatever has keyboard focus.
    The editor's framing keys aren't commands, so this is the only way to
    reach them. Returns False if the platform can't do it.
    """
    if ctypes is None or not hasattr(ctypes, "windll"):
        return False
    vk = VK_CODES.get(ch.upper())
    if vk is None:
        return False
    try:
        user32 = ctypes.windll.user32
        scan = user32.MapVirtualKeyW(vk, 0)
        user32.keybd_event(vk, scan, 0, 0)          # down
        user32.keybd_event(vk, scan, 2, 0)          # up (KEYEVENTF_KEYUP)
    except Exception as exc:
        print("couldn't send the '%s' key: %s" % (ch, exc))
        return False
    return True


# --- deferred delivery ----------------------------------------------------

def send_key_later(ch, ms):
    """
    Send the key from a timer thread, so it lands well after this script has
    returned and C4D has processed the queued focus change.

    A plugin-based deferral is not available here: RegisterMessagePlugin
    fails from the Script Manager with "cannot find pyp file", so
    SpecialEventAdd has nothing to wake. It is not needed either - keybd_event
    posts to the *Windows* input queue, which C4D drains on its next message
    pump, so delivery is already deferred past the end of this script. The
    timer only widens that gap to make the ordering comfortable.

    Safe off the main thread because keybd_event is a pure Win32 call and
    touches no c4d API. Nothing in this function may call into c4d.
    """
    if ms <= 0:
        return send_key(ch)
    if threading is None:
        return send_key(ch)
    try:
        t = threading.Timer(ms / 1000.0, lambda: send_key(ch))
        t.daemon = True
        t.start()
    except Exception:
        return send_key(ch)
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

    host, tag, master = matched[0]
    if len(matched) > 1:
        others = ", ".join("'%s'" % h.GetName() for h, _, _ in matched[1:])
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

    # Ask for keyboard focus. Queued, not immediate - which is why the
    # keystroke below is deferred rather than sent on the next line.
    c4d.CallCommand(XPRESSO_EDITOR_ID)

    if send_key_later(CENTRE_KEY, KEY_DELAY_MS):
        print("centring: '%s' queued for the editor (+%dms)."
              % (CENTRE_KEY, KEY_DELAY_MS))
    else:
        print("centring needs Windows - nodes are still selected, press '%s' "
              "in the editor yourself." % CENTRE_KEY)


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
    matched = []          # (host, tag, master) for every graph that had a hit

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
            matched.append((host, tag, master))

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
