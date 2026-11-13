"""Isolated launcher for the attacker (PROTOCOL.md section 2, check 9).

Each call:
  * copies the script into its own fresh temporary directory;
  * creates a second, fresh, empty temporary directory as the working directory;
  * runs `<this interpreter> -I <copied script>` there with env={} and the input on stdin only;
  * returns stdout bytes (raises on a non-zero exit).

This is process-level isolation, not an OS sandbox: a deliberately malicious script could still
open absolute paths. validate.check_attacker_static therefore also checks the attacker's source.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile


def run_isolated(script_path, stdin_bytes, timeout=900):
    with tempfile.TemporaryDirectory(prefix="lfi-script-") as script_dir, \
            tempfile.TemporaryDirectory(prefix="lfi-cwd-") as workdir:
        target = os.path.join(script_dir, os.path.basename(str(script_path)))
        shutil.copyfile(str(script_path), target)
        proc = subprocess.run([sys.executable, "-I", target], input=stdin_bytes,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=workdir, env={}, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("isolated script %s failed: %s"
                           % (os.path.basename(str(script_path)), proc.stderr.decode("utf-8", "replace")))
    return proc.stdout
