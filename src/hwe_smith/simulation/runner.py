"""Simulation runner: compile + run a cocotb testbench in an isolated workspace.

Wraps `make SIM=icarus` in a per-candidate copy of the repository so candidates
never contaminate each other or the pristine cache clone.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"  # compile/environment failure, not a functional bug signal


@dataclass
class SimResult:
    status: str           # PASS | FAIL | ERROR
    exit_code: int
    duration_s: float
    log: str
    log_path: str | None = None
    tests_passed: int = 0
    tests_failed: int = 0
    seed: int | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _parse_results_xml(xml: Path) -> tuple[int, int]:
    """Extract passed/failed test counts from cocotb results.xml."""
    import xml.etree.ElementTree as ET

    try:
        root = ET.parse(xml).getroot()
    except ET.ParseError:
        return 0, 0
    passed = failed = 0
    for tc in root.iter("testcase"):
        if tc.find("failure") is not None or tc.find("error") is not None:
            failed += 1
        elif tc.find("skipped") is None:
            passed += 1
    return passed, failed


class SimRunner:
    def __init__(self, repo_src: Path, work_root: Path, timeout_s: int = 60):
        self.repo_src = Path(repo_src)
        self.work_root = Path(work_root)
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.timeout_s = timeout_s
        self._counter = 0

    def make_workspace(self, tag: str) -> Path:
        """Fresh copy of the repo for one candidate; returns workspace path."""
        self._counter += 1
        ws = self.work_root / f"{tag}_{self._counter}"
        if ws.exists():
            shutil.rmtree(ws)
        # symlinks=True avoids symlink cycles in the repo's example/ tree;
        # examples are excluded as non-essential for simulation.
        shutil.copytree(
            self.repo_src, ws,
            ignore=shutil.ignore_patterns(".git", "example"),
            symlinks=True,
        )
        return ws

    def run_test(self, workspace: Path, tb_dir: str, log_dir: Path | None = None,
                 tag: str = "run", seed: int | None = None) -> SimResult:
        """Run one testbench (compile+sim) inside the workspace."""
        start = time.time()
        log_dir = Path(log_dir) if log_dir else workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{tag}.log"

        # force a clean rebuild: same-second edits can fool make's mtime check
        # and cause a stale binary to run against modified RTL
        sim_build = Path(workspace) / tb_dir / "sim_build"
        if sim_build.exists():
            shutil.rmtree(sim_build)

        env = dict(os.environ)
        if seed is not None:
            env["RANDOM_SEED"] = str(seed)
        # Prefer project venv if present (resolved from this file), else PATH.
        venv_bin = Path(__file__).resolve().parents[3] / ".venv" / "bin"
        path_parts = []
        if venv_bin.is_dir():
            path_parts.append(str(venv_bin))
        path_parts.append(env.get("PATH", ""))
        env["PATH"] = os.pathsep.join(path_parts)

        try:
            proc = subprocess.run(
                ["make", "SIM=icarus"],
                cwd=Path(workspace) / tb_dir,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=env,
                start_new_session=True,  # own process group so timeout kills vvp too
            )
            log = (proc.stdout or "") + (proc.stderr or "")
            exit_code = proc.returncode
        except subprocess.TimeoutExpired as e:
            # kill the child process group that make spawned (NOT our own);
            # find it via pgrep on the workspace path (TimeoutExpired has no pid)
            child_pgid = None
            try:
                out = subprocess.run(
                    ["pgrep", "-f", str(Path(workspace) / tb_dir / "sim_build")],
                    capture_output=True, text=True)
                pids = [int(x) for x in out.stdout.split() if x.strip().isdigit()]
            except Exception:
                pids = []
            for pid in pids:
                try:
                    pg = os.getpgid(pid)
                    if pg != os.getpgid(0):
                        os.killpg(pg, signal.SIGKILL)
                    else:
                        os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
            # belt and braces: kill any vvp running under this workspace
            subprocess.run(["pkill", "-9", "-f",
                            str(Path(workspace) / tb_dir / "sim_build")],
                           capture_output=True)
            log = f"TIMEOUT after {self.timeout_s}s\n{(e.stdout or '')!r}\n{(e.stderr or '')!r}"
            exit_code = -9
        except Exception as e:  # environment failure
            log = f"ENVIRONMENT ERROR: {e!r}"
            exit_code = -1

        dur = time.time() - start
        log_path.write_text(log)

        # cocotb writes results.xml next to the Makefile; PASS is signaled by
        # exit code 0 AND parsed TESTS summary consistency.
        results_xml = Path(workspace) / tb_dir / "results.xml"
        passed, failed = (0, 0)
        if results_xml.exists():
            passed, failed = _parse_results_xml(results_xml)

        if exit_code != 0 and "Error 1" in log and "assert" not in log.lower() \
                and failed == 0 and "FAIL=" in log and "FAIL=0" in log:
            # iverilog compile error but cocotb reported no failures: ERROR
            status = ERROR
        elif failed > 0 or exit_code != 0:
            status = FAIL
        elif passed == 0 and "PASS=0" in log:
            status = ERROR
        else:
            status = PASS

        return SimResult(status=status, exit_code=exit_code, duration_s=round(dur, 2),
                         log=log, log_path=str(log_path), tests_passed=passed,
                         tests_failed=failed, seed=seed)
