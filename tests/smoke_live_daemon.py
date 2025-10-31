from __future__ import annotations

import os

from queen.technicals.signals.tactical.live_daemon import DAEMON_STATE_FILE, run_daemon


def test():
    run_daemon(once=True)
    assert os.path.exists(DAEMON_STATE_FILE), "daemon checkpoint not written"
    print("✅ smoke_live_daemon: passed")


if __name__ == "__main__":
    test()
