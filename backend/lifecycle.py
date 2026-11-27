"""Inspect and stop only the local VisionLab backend process."""
import sys
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[1]


def owned_servers() -> list[psutil.Process]:
    """Find backend processes by project directory and exact module arguments."""
    matches = []
    for process in psutil.process_iter(['cmdline', 'cwd', 'uids']):
        try:
            args = process.info['cmdline'] or []
            if (process.info['cwd'] == str(ROOT) and len(args) >= 4
                    and args[1:4] == ['-m', 'uvicorn', 'backend.app:app']
                    and process.info['uids'].real == psutil.Process().uids().real):
                matches.append(process)
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            continue
    return matches


def main() -> int:
    """Run the status or graceful-stop command."""
    servers = owned_servers()
    if sys.argv[1:] == ['status']:
        print('VisionLab: ' + (', '.join(str(p.pid) for p in servers) or 'OFF'))
        return 0
    if sys.argv[1:] != ['stop']:
        return 2
    for process in servers:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(servers, timeout=20)
    if alive:
        print('Backend still stopping; check its terminal.', file=sys.stderr)
        return 1
    print('VisionLab stopped.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
