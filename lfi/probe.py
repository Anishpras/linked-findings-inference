#!/usr/bin/env python3
"""Isolation probe for check 9. Launched through exactly the same launcher as the attacker; it
reports what such a process can see. Never used for scoring."""
import hashlib
import json
import os
import sys

data = sys.stdin.buffer.read()
report = {
    "cwd_listing": sorted(os.listdir(".")),
    "env_keys": sorted(os.environ),
    "flags_isolated": sys.flags.isolated,
    "flags_ignore_environment": sys.flags.ignore_environment,
    "flags_no_user_site": sys.flags.no_user_site,
    "argv_basename": os.path.basename(sys.argv[0]),
    "argv_len": len(sys.argv),
    "stdin_sha256": hashlib.sha256(data).hexdigest(),
    "cwd": os.getcwd(),
    "script_dir": os.path.dirname(os.path.abspath(sys.argv[0])),
    "sys_path": sys.path,
}
sys.stdout.write(json.dumps(report, sort_keys=True) + "\n")
