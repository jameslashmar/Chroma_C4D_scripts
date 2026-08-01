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

PLUGIN_ID = 1069542

# --- settings -------------------------------------------------------------

AUTO_NAME_GENERATORS = True   # feature 1
AUTO_NAME_TEXT = True         # feature 2

TEXT_WORD_COUNT = 3           # how many words of the text to use as the name
TEXT_MAX_CHARS = 32           # hard cap on the generated name

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


class ChromaUtilities(c4d.plugins.MessageData):

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._busy = False            # re-entrancy guard: our own renames fire EVMSG_CHANGE
        self._doc = None              # active document we baselined against
        self._baseline = set()        # objects that existed when we first saw this document
        self._default_names = {}      # object type -> its default name, cached
        self._text_warned = set()     # types we've already complained about

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
            return

        changed = False

        for key, op in objects:
            # Objects that predate us are off-limits, unless we own the name.
            established = key in self._baseline and not self._owns(op)
            if established:
                continue

            if AUTO_NAME_GENERATORS and self._name_generator(op):
                changed = True
            if AUTO_NAME_TEXT and self._name_text_object(op):
                changed = True

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
    print("[Chroma Utilities] %s" % ("listening" if ok else "FAILED to register"))
