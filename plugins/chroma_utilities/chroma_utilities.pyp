"""
Chroma Utilities

A background listener for Cinema 4D. It starts with C4D, watches the active
document for the whole session, and quietly names things for you:

  1. A generator created as the parent of an object takes that object's name,
     instead of staying called "Extrude" / "Cloner" / "Symmetry".
  2. A text object names itself after the first few words of its own text,
     and keeps up as the text changes.

Nothing to launch - drop the plugin in and it runs.

Cinema 4D 2026 / Python 3.11
Plugin ID: 1069542 (registered with Maxon)
"""

import c4d
import re
import traceback
from c4d.modules import graphview

PLUGIN_ID = 1069542
VERSION = "1.2.0"   # keep in step with the VERSION file next to this script

# --- settings -------------------------------------------------------------

AUTO_NAME_GENERATORS = True   # feature 1
AUTO_NAME_TEXT = True         # feature 2
AUTO_INCREMENT = True         # feature 3
MULTI_WIRE = True             # feature 4
MULTI_WIRE_CREATE_PORTS = True  # add the port if the node will accept it
                                # XPresso ports exist only once added, so
                                # without this the feature rarely fires

TEXT_WORD_COUNT = 4           # how many words of the text to use as the name
TEXT_MAX_CHARS = 32           # hard cap on the generated name

INCREMENT_SEPARATOR = "_"     # what sits between the stem and the number
INCREMENT_PADDING = 2         # minimum digits, so the second copy is _02

# Types that should keep their default name even when they gain a child.
# Add c4d.Onull here if you'd rather nulls stayed called "Null".
SKIP_GENERATOR_TYPES = set()

TIMER_MS = 300                # how often to look, in milliseconds
VERBOSE = False               # print every rename

# Parameter ids to try when reading a text object's contents. Spline Text uses
# PRIM_TEXT_TEXT; MoText is not exposed as a named constant in the 2026 Python
# SDK, so it is probed rather than assumed. If a MoText yields nothing, the
# plugin says so once and tells you how to find the right id.
TEXT_PARAM_CANDIDATES = (c4d.PRIM_TEXT_TEXT,)

TEXT_TYPES = (c4d.Osplinetext, c4d.Omgtext)

# "Light.1" -> stem "Light". C4D's own suffix for a duplicate.
_DUPLICATE_RE = re.compile(r'^(.*?)\.\d+$')

# "Camera 02" -> ("Camera", "02") · "cam 19-2" -> ("cam", "19-2") · "Light" -> no match
_TRAILING_NUM_RE = re.compile(r'^(.*?)[\s_\-]*(\d+(?:[\s\-]\d+)*)$')


class ChromaUtilities(c4d.plugins.MessageData):

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._busy = False            # re-entrancy guard: our own renames fire EVMSG_CHANGE
        self._doc = None              # active document we baselined against
        self._baseline = set()        # objects that existed when we first saw this document
        self._default_names = {}      # object type -> its default name, cached
        self._text_warned = set()     # types we've already complained about
        self._wiring = {}             # graph -> the connections we last saw

    # -- plugin entry points ------------------------------------------------

    def GetTimer(self):
        return TIMER_MS

    def CoreMessage(self, id, bc):
        if id != c4d.MSG_TIMER and id != c4d.EVMSG_CHANGE:
            return True
        if self._busy:
            return True
        try:
            self._busy = True
            self._tick()
        except Exception:
            traceback.print_exc()
        finally:
            self._busy = False
        return True

    # -- scene walking ------------------------------------------------------

    def _collect(self, doc):
        """Every object in the document, as (key, object) pairs."""
        found = []

        def walk(op):
            while op:
                found.append((self._key(op), op))
                walk(op.GetDown())
                op = op.GetNext()

        walk(doc.GetFirstObject())
        return found

    def _key(self, op):
        """
        Stable identity for an object. GetGUID() is derived from the object's
        marker and survives across calls; id() of the Python wrapper does not
        reliably, so it is only a last resort.
        """
        try:
            guid = op.GetGUID()
        except Exception:
            guid = 0
        return guid if guid else id(op)

    def _same_document(self, doc):
        """
        True if this is still the document we baselined against. Compares with
        == rather than 'is', because C4D hands back a fresh Python wrapper each
        time - and a wrapper for a closed document raises when touched.
        """
        if self._doc is None:
            return False
        try:
            return self._doc == doc
        except Exception:
            return False

    # -- name ownership -----------------------------------------------------
    #
    # We store the last name we assigned in the object's own container, under
    # our plugin id. If the current name still matches, the name is still ours
    # to update. If it doesn't, the user renamed it by hand and we leave it
    # alone from then on - an automatic renamer that overwrites a deliberate
    # choice is worse than no renamer at all.

    def _mark(self, op, name):
        bc = op.GetDataInstance()
        if bc is not None:
            bc.SetString(PLUGIN_ID, name)

    def _owns(self, op):
        bc = op.GetDataInstance()
        if bc is None:
            return False
        stored = bc.GetString(PLUGIN_ID)
        return bool(stored) and stored == op.GetName()

    def _default_name(self, op):
        """
        The name C4D gives a freshly created object of this type. Asking a
        throwaway instance keeps this correct in any interface language,
        which a hardcoded list of English names would not be.
        """
        t = op.GetType()
        if t not in self._default_names:
            name = None
            try:
                probe = c4d.BaseObject(t)
                if probe:
                    name = probe.GetName()
            except Exception:
                pass
            self._default_names[t] = name
        return self._default_names[t]

    def _is_untouched(self, op):
        """Still carrying its default name, give or take C4D's .1 / .2 suffix."""
        default = self._default_name(op)
        if not default:
            return False
        return re.sub(r'\.\d+$', '', op.GetName()) == default

    # -- feature 1: generator inherits its child's name ---------------------

    def _name_generator(self, op):
        if op.GetType() in SKIP_GENERATOR_TYPES:
            return False

        child = op.GetDown()
        if child is None:
            return False
        if not self._is_untouched(op):
            return False

        new_name = child.GetName()
        if not new_name or new_name == op.GetName():
            return False

        op.SetName(new_name)
        self._mark(op, new_name)
        if VERBOSE:
            print("[Chroma Utilities] %s -> '%s'" % (self._default_name(op), new_name))
        return True

    # -- feature 2: text object names itself after its text -----------------

    def _read_text(self, op):
        for pid in TEXT_PARAM_CANDIDATES:
            try:
                value = op[pid]
            except Exception:
                continue
            if isinstance(value, str) and value.strip():
                return value

        t = op.GetType()
        if t not in self._text_warned:
            self._text_warned.add(t)
            print("[Chroma Utilities] couldn't read the text of '%s' (type %d). "
                  "Run: [x for x in op.GetDataInstance()] to find the string "
                  "parameter id, then add it to TEXT_PARAM_CANDIDATES."
                  % (op.GetName(), t))
        return None

    def _name_from_text(self, text):
        words = text.split()
        if not words:
            return None
        name = " ".join(words[:TEXT_WORD_COUNT])
        if len(name) > TEXT_MAX_CHARS:
            name = name[:TEXT_MAX_CHARS].rstrip()
        return name or None

    def _name_text_object(self, op):
        if op.GetType() not in TEXT_TYPES:
            return False
        # Take over a freshly made text object, or keep updating one we named.
        if not (self._owns(op) or self._is_untouched(op)):
            return False

        text = self._read_text(op)
        if text is None:
            return False

        new_name = self._name_from_text(text)
        if not new_name or new_name == op.GetName():
            return False

        op.SetName(new_name)
        self._mark(op, new_name)
        if VERBOSE:
            print("[Chroma Utilities] text -> '%s'" % new_name)
        return True

    # -- feature 3: duplicates count up instead of gaining ".1" -------------
    #
    # C4D names a duplicate "Light.1". We turn that into "Light_02", and
    # normalise however the original was numbered onto the same underscore
    # form: "Camera 02" -> "Camera_03", "cam 19-2" -> "cam_20".

    def _next_name(self, name, taken):
        dup = _DUPLICATE_RE.match(name)
        if not dup:
            return None
        original = dup.group(1)

        trailing = _TRAILING_NUM_RE.match(original)
        if trailing:
            stem = trailing.group(1)
            # Only the first run of digits counts - "19-2" counts up as 19.
            first = re.match(r'\d+', trailing.group(2)).group(0)
            width = max(INCREMENT_PADDING, len(first))
            number = int(first) + 1
        else:
            stem = original
            width = INCREMENT_PADDING
            number = 2

        stem = stem.rstrip(" _-")
        if not stem:
            return None   # a name that is only digits - leave it alone

        candidate = "%s%s%s" % (stem, INCREMENT_SEPARATOR, str(number).zfill(width))
        while candidate in taken:
            number += 1
            candidate = "%s%s%s" % (stem, INCREMENT_SEPARATOR, str(number).zfill(width))
        return candidate

    def _number_of(self, name):
        """The first run of digits in a name's trailing number, if any."""
        trailing = _TRAILING_NUM_RE.match(_DUPLICATE_RE.sub(r'\1', name))
        if not trailing:
            return None
        return re.match(r'\d+', trailing.group(2)).group(0)

    def _renumber_children(self, parent, old_number, new_number, taken):
        """
        Direct children carrying the same number as the parent follow it up.
        Duplicating "Camera 02" with a "target 02" inside gives "Camera_03"
        and "target_03", not "Camera_03" containing "target 02".
        """
        if old_number is None or new_number is None:
            return

        child = parent.GetDown()
        while child:
            name = child.GetName()
            base = _DUPLICATE_RE.sub(r'\1', name)
            trailing = _TRAILING_NUM_RE.match(base)
            if trailing and re.match(r'\d+', trailing.group(2)).group(0) == old_number:
                stem = trailing.group(1).rstrip(" _-")
                if stem:
                    new_name = "%s%s%s" % (stem, INCREMENT_SEPARATOR, new_number)
                    if new_name != name:
                        child.SetName(new_name)
                        taken.add(new_name)
                        taken.discard(name)
            child = child.GetNext()

    def _increment(self, op, taken):
        name = op.GetName()
        new_name = self._next_name(name, taken)
        if new_name is None:
            return False

        old_number = self._number_of(name)
        op.SetName(new_name)
        taken.add(new_name)
        taken.discard(name)
        self._renumber_children(op, old_number, self._number_of(new_name), taken)

        if VERBOSE:
            print("[Chroma Utilities] '%s' -> '%s'" % (name, new_name))
        return True

    # -- feature 4: wire one selected XPresso node, wire them all -----------
    #
    # Select several nodes, drag a connection onto a port of one of them, and
    # the same connection is made on every other selected node. There's no
    # hook for a port drag, so this watches the graph's connections and reacts
    # when a new one appears on a node that's part of a multi-node selection.

    def _graph_nodes(self, master):
        """
        Every node in a graph as (path, node). The path is its position in the
        walk - "0.2.1" - which gives stable identity across ticks without
        relying on GetGUID(), which graph nodes may not carry.
        """
        root = master.GetRoot()
        if root is None:
            return []

        found = []

        def walk(node, prefix):
            i = 0
            while node:
                path = "%s.%d" % (prefix, i)
                found.append((path, node))
                walk(node.GetDown(), path)
                node = node.GetNext()
                i += 1

        walk(root.GetDown(), "")
        return found

    def _path_of(self, target, nodes):
        # == compares the underlying node; 'is' would not, because C4D hands
        # back a fresh Python wrapper on every call.
        for path, node in nodes:
            if node == target:
                return path
        return None

    def _connections(self, nodes):
        """
        Every connection in the graph, as a hashable tuple. Read from the
        output side, which avoids GetIncomingSource() and its odd signature.
        """
        conns = set()
        for path, node in nodes:
            for out in (node.GetOutPorts() or []):
                for dest in (out.GetDestination() or []):
                    dest_node = dest.GetNode()
                    if dest_node is None:
                        continue
                    dest_path = self._path_of(dest_node, nodes)
                    if dest_path is None:
                        continue
                    conns.add((path, out.GetMainID(), out.GetSubID(),
                               dest_path, dest.GetMainID(), dest.GetSubID()))
        return conns

    def _find_port(self, node, main_id, sub_id, incoming=True):
        ports = node.GetInPorts() if incoming else node.GetOutPorts()
        ports = ports or []
        for port in ports:
            if port.GetMainID() == main_id and port.GetSubID() == sub_id:
                return port
        # Fall back to the main id alone - a port with no meaningful sub id
        # reports it inconsistently across node types.
        for port in ports:
            if port.GetMainID() == main_id:
                return port
        return None

    def _add_port(self, node, main_id, sub_id):
        """
        XPresso ports only exist once they've been added - dragging a
        connection onto a node is what creates one. So mirroring a connection
        usually means creating the port on the other nodes first.

        The id is tried as a plain int and as a DescID, since parameter ports
        on an Object node are DescID-based and GetMainID/GetSubID flatten that.
        """
        candidates = [main_id]
        if sub_id is not None and sub_id >= 0:
            try:
                candidates.append(c4d.DescID(c4d.DescLevel(main_id),
                                             c4d.DescLevel(sub_id)))
            except Exception:
                pass
        try:
            candidates.append(c4d.DescID(c4d.DescLevel(main_id)))
        except Exception:
            pass

        for cid in candidates:
            try:
                if not node.AddPortIsOK(c4d.GV_PORT_INPUT, cid):
                    continue
            except Exception:
                pass   # AddPortIsOK may not accept a DescID - let AddPort decide
            try:
                port = node.AddPort(c4d.GV_PORT_INPUT, cid,
                                    c4d.GV_PORT_FLAG_IS_VISIBLE, True)
            except Exception:
                port = None
            if port is not None:
                return port
        return None

    def _node_label(self, node):
        """
        'Object' three times over tells you nothing. Where a node links to
        something, name it: "Object -> Cube_02".
        """
        name = node.GetName()
        doc = self._doc
        bc = None
        for attr in ("GetOpContainerInstance", "GetOperatorContainer", "GetDataInstance"):
            fn = getattr(node, attr, None)
            if fn:
                try:
                    bc = fn()
                    if bc is not None:
                        break
                except Exception:
                    pass
        if bc is None or doc is None:
            return "'%s'" % name

        try:
            for i in range(len(bc)):
                cid = bc.GetIndexId(i)
                if cid == c4d.NOTOK:
                    break
                try:
                    linked = bc.GetLink(cid, doc)
                except Exception:
                    continue
                if linked is not None:
                    return "'%s' -> %s" % (name, linked.GetName())
        except Exception:
            pass
        return "'%s'" % name

    def _type_name(self, value_type):
        return {
            c4d.ID_GV_VALUE_TYPE_REAL: "real",
            c4d.ID_GV_VALUE_TYPE_VECTOR: "vector",
        }.get(value_type, str(value_type))

    def _mirror_connection(self, conn, nodes, label):
        """Replicate one new connection onto every other selected node."""
        src_path, src_main, src_sub, dst_path, dst_main, dst_sub = conn

        by_path = dict(nodes)
        src_node = by_path.get(src_path)
        dst_node = by_path.get(dst_path)
        if src_node is None or dst_node is None:
            return 0
        if not dst_node.GetBit(c4d.BIT_ACTIVE):
            return 0   # the wired node isn't part of a selection

        targets = [n for _, n in nodes
                   if n.GetBit(c4d.BIT_ACTIVE) and not (n == dst_node)]
        if not targets:
            return 0

        src_port = self._find_port(src_node, src_main, src_sub, incoming=False)
        if src_port is None:
            return 0
        src_type = src_port.GetValueType()

        wired = 0
        for node in targets:
            port = self._find_port(node, dst_main, dst_sub, incoming=True)

            # The port usually doesn't exist yet - in XPresso a port appears
            # only when something is dragged onto it. Create it if the node
            # will take it; if it won't, that's a real "can't do this" and
            # gets reported.
            if port is None and MULTI_WIRE_CREATE_PORTS:
                port = self._add_port(node, dst_main, dst_sub)

            if port is None:
                print("[Chroma Utilities] %s: %s won't take port %d/%d, skipped"
                      % (label, self._node_label(node), dst_main, dst_sub))
                continue

            # Report a type mismatch rather than making a bad connection.
            if port.GetValueType() != src_type:
                print("[Chroma Utilities] %s: %s port is %s, source is %s - skipped"
                      % (label, self._node_label(node),
                         self._type_name(port.GetValueType()),
                         self._type_name(src_type)))
                continue

            # Replace whatever was feeding it.
            if port.IsIncomingConnected():
                port.Remove()

            if src_port.Connect(port):
                wired += 1
                if VERBOSE:
                    print("[Chroma Utilities] %s: wired %s"
                          % (label, self._node_label(node)))
            else:
                print("[Chroma Utilities] %s: connection to %s failed"
                      % (label, self._node_label(node)))

        if wired and VERBOSE:
            print("[Chroma Utilities] %s: mirrored to %d node(s)" % (label, wired))
        return wired

    def _multi_wire(self, doc):
        changed = False

        for host, tag in self._xpresso_tags(doc):
            master = tag.GetNodeMaster()
            if master is None:
                continue

            nodes = self._graph_nodes(master)
            if not nodes:
                continue

            label = "XPresso on '%s'" % host.GetName()
            key = label
            current = self._connections(nodes)
            previous = self._wiring.get(key)

            # First sight of this graph: record and touch nothing.
            if previous is None:
                self._wiring[key] = current
                continue

            wired = 0
            for conn in (current - previous):
                wired += self._mirror_connection(conn, nodes, label)

            # Re-read after acting, so our own connections aren't mistaken
            # for the user's on the next tick.
            self._wiring[key] = self._connections(nodes) if wired else current

            if wired:
                graphview.RedrawMaster(master)
                changed = True

        return changed

    def _xpresso_tags(self, doc):
        """Every XPresso tag in the scene, wherever the tag lives."""
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

    # -- the tick -----------------------------------------------------------

    def _tick(self):
        doc = c4d.documents.GetActiveDocument()
        if doc is None:
            return

        objects = self._collect(doc)

        # First sight of a document: record what's already in it and touch
        # nothing. Opening an old scene shouldn't trigger a mass rename.
        if not self._same_document(doc):
            self._doc = doc
            self._baseline = set(key for key, _ in objects)
            self._wiring = {}
            return

        if MULTI_WIRE and self._multi_wire(doc):
            c4d.EventAdd()

        changed = False
        taken = set(op.GetName() for _, op in objects)

        for key, op in objects:
            # Objects that predate us are off-limits, unless we own the name.
            established = key in self._baseline and not self._owns(op)
            if established:
                continue

            acted = False
            if AUTO_NAME_GENERATORS and self._name_generator(op):
                acted = True
            if AUTO_NAME_TEXT and self._name_text_object(op):
                acted = True

            # Only fall through to the increment if nothing more specific
            # claimed the name - a duplicated default-named Extrude is better
            # off taking its child's name than becoming "Extrude_02".
            if AUTO_INCREMENT and not acted and self._increment(op, taken):
                acted = True

            changed = changed or acted

        # The baseline deliberately does not grow. It records what was in the
        # document when we opened it, and nothing else - so an object created
        # during the session stays eligible until it has been named, which is
        # what makes "create an empty Extrude, drag a spline in later" work.

        if changed:
            c4d.EventAdd()


if __name__ == "__main__":
    ok = c4d.plugins.RegisterMessagePlugin(
        id=PLUGIN_ID,
        str="Chroma Utilities",
        info=0,
        dat=ChromaUtilities()
    )

    # Name the enabled features on load, so it's obvious at a glance whether
    # this build is the one you think it is.
    enabled = [name for name, on in (
        ("parent renamer", AUTO_NAME_GENERATORS),
        ("text renamer", AUTO_NAME_TEXT),
        ("auto-enumerator", AUTO_INCREMENT),
        ("multi-wire", MULTI_WIRE),
    ) if on]

    print("[Chroma Utilities] v%s %s%s" % (
        VERSION,
        "listening" if ok else "FAILED to register",
        (" - " + ", ".join(enabled)) if (ok and enabled) else
        (" - all features disabled" if ok else "")))
