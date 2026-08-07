"""
Find the XPresso editor's own command ids.

Every run appends a snapshot of which commands are currently ENABLED to one
log file. Nothing is remembered between runs - the file is the only state, so
it cannot get out of sync.

  RUN 1  Click the Object Manager. Run from Extensions > User Scripts.
  RUN 2  Click inside the XPresso editor, then fire the KEYBOARD SHORTCUT.
         It must be the shortcut - going back to the Script Manager to press
         Execute hands focus to the Script Manager instead.

Then hand the log file to Claude. Commands enabled in run 2 but not run 1
belong to the XPresso editor.

Log file: C:/Users/james/AppData/Local/Temp/chroma_xpresso_probe.txt

Cinema 4D 2026 / Python API
"""

import c4d

LOG = "C:/Users/james/AppData/Local/Temp/chroma_xpresso_probe.txt"


def is_enabled(cid):
    fn = getattr(c4d, "IsCommandEnabled", None)
    if fn is None:
        fn = getattr(c4d.gui, "IsCommandEnabled", None)
    if fn is None:
        return None
    try:
        return bool(fn(cid))
    except Exception:
        return None


def run_number():
    """How many snapshots the log already holds."""
    try:
        with open(LOG, "r", encoding="utf-8") as fh:
            return fh.read().count("=== RUN ") + 1
    except Exception:
        return 1


def main():
    print("=" * 60)
    print("XPRESSO COMMAND PROBE  (probe_xpresso_commands.py)")
    print("=" * 60)

    try:
        plugins = c4d.plugins.FilterPluginList(c4d.PLUGINTYPE_COMMAND, True)
    except Exception as exc:
        print("couldn't enumerate command plugins: %s" % exc)
        return

    rows = []
    total = 0
    for p in plugins:
        try:
            cid = p.GetID()
            name = p.GetName()
        except Exception:
            continue
        total += 1
        if is_enabled(cid):
            rows.append((cid, name))

    rows.sort()
    n = run_number()

    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("=== RUN %d ===  %d commands, %d enabled\n"
                     % (n, total, len(rows)))
            for cid, name in rows:
                fh.write("%s\t%s\n" % (cid, name))
            fh.write("\n")
    except Exception as exc:
        # Console fallback if the file can't be written - paste this instead.
        print("couldn't write %s (%s) - dumping to console" % (LOG, exc))
        for cid, name in rows:
            print("%s\t%s" % (cid, name))
        return

    print("RUN %d written: %d commands, %d enabled." % (n, total, len(rows)))
    print("log: %s" % LOG)
    if n == 1:
        print("\nNow click INSIDE the XPresso editor and fire the SHORTCUT.")
    else:
        print("\nThat's %d snapshots. Hand the log file to Claude." % n)

    # Anything obviously framing-related, visible right now, as a sanity read.
    hits = [(c, nm) for c, nm in rows
            if any(t in nm.lower() for t in
                   ("frame", "zoom", "fit", "centre", "center", "optimi"))]
    print("\nframing/zoom-ish commands enabled on THIS run (%d):" % len(hits))
    for cid, name in hits:
        print("  %-8s %s" % (cid, name))


if __name__ == '__main__':
    main()
