"""Run one Python script inside a live 3ds Max and capture the viewport.

    python run_script.py --script roman_column.py --port auto
    python run_script.py --script roman_column.py --port 52796 --shot out.png

Exit code is 0 only when the host reports success *and* (if requested) the
screenshot file exists — a tool call that merely returns prose is not proof.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import locale
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp_client import DccMcp  # noqa: E402

MAX_IMAGE = "3dsmax.exe"


def _run_text(args: list[str], timeout: float) -> str:
    """Run a console tool and decode its output.

    Windows console tools localise their output, so `netstat` can emit GBK on a
    Chinese system. Decoding with text=True dies in the reader thread and leaves
    stdout=None, so read bytes and try the plausible encodings.
    """
    proc = subprocess.run(args, capture_output=True, timeout=timeout)
    raw = proc.stdout or b""
    for enc in ("utf-8", locale.getpreferredencoding(False), "gbk", "cp936"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")



def find_port(image: str = MAX_IMAGE) -> int:
    """Find the MCP port by intersecting the host's PIDs with listening TCP ports."""
    pids = set()
    try:
        out = _run_text(["tasklist", "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"], 20)
        for row in csv.reader(io.StringIO(out)):
            if len(row) >= 2 and row[1].strip().isdigit():
                pids.add(row[1].strip())
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"tasklist failed: {exc}")

    if not pids:
        raise SystemExit(f"{image} is not running — start the host first.")

    out = _run_text(["netstat", "-ano"], 30)
    ports = []
    for line in out.splitlines():
        if "LISTENING" not in line:
            continue
        parts = line.split()
        if len(parts) < 5 or parts[-1] not in pids:
            continue
        m = re.search(r"127\.0\.0\.1:(\d+)$", parts[1])
        if m:
            ports.append(int(m.group(1)))

    if not ports:
        raise SystemExit("No loopback port owned by the host — is the MCP server up yet?")

    # The MCP endpoint answers a POST; the plain ports (web UI, telemetry) usually do not.
    for port in sorted(ports):
        try:
            client = DccMcp(f"http://127.0.0.1:{port}/mcp", timeout=8)
            client.initialize()
            return port
        except Exception:  # noqa: BLE001
            continue
    raise SystemExit(f"Host ports {ports} did not accept an MCP handshake.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="Python file to execute inside the host")
    ap.add_argument("--port", default="auto", help="MCP port, or 'auto'")
    ap.add_argument("--shot", help="Write a viewport PNG here after the script runs")
    ap.add_argument("--frame", action="store_true", default=True,
                    help="select all + zoom extents before the screenshot (default: on)")
    ap.add_argument("--no-frame", dest="frame", action="store_false")
    ap.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args()

    script = Path(args.script).resolve()
    code = script.read_text(encoding="utf-8")

    if args.frame:
        code += """
# --- framing: make the whole result visible before capture ---
try:
    import pymxs
    _rt = pymxs.runtime
    _rt.select(_rt.objects)
    _rt.execute("max zoomext sel all")
    _rt.clearSelection()
    _rt.execute("completeRedraw()")
    print("FRAMED objects=%d" % _rt.objects.count)
except Exception as _e:
    print("FRAME ERROR: %r" % (_e,))
"""

    port = find_port() if args.port == "auto" else int(args.port)
    url = f"http://127.0.0.1:{port}/mcp"
    print(f"host: {url}")

    t0 = time.time()
    client = DccMcp(url, timeout=args.timeout)
    client.initialize()
    client.load_skill("3dsmax-scripting")
    result = client.call(
        "3dsmax_scripting__execute_python",
        {"code": code, "confirm_execution": True},
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    ok = bool(result.get("success"))
    print(f"executed in {time.time() - t0:.1f}s")

    if args.shot:
        shot = Path(args.shot).resolve()
        shot.parent.mkdir(parents=True, exist_ok=True)
        client.load_skill("3dsmax-viewport")
        cap = client.call("3dsmax_viewport__capture_viewport", {"file_path": str(shot)})
        print(json.dumps(cap, ensure_ascii=False, indent=2))
        if not shot.exists() or shot.stat().st_size == 0:
            print("FAIL: screenshot was not written", file=sys.stderr)
            return 2
        print(f"screenshot: {shot} ({shot.stat().st_size} bytes)")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
