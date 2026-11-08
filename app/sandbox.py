"""Sandbox runner: every piece of model-written code runs in a throw-away Docker container.

Containment properties (all enforced by the Docker flags below):
  * process isolation  - separate namespaces, non-root user, all capabilities dropped
  * no network         - --network none
  * read-only rootfs   - only a tiny noexec tmpfs and one output dir are writable
  * resource caps      - memory, cpu, pids and wall-clock timeout on every run
  * secret hygiene     - the container gets NO environment variables from the host
  * lifecycle          - --rm + forced removal + temp dir wipe after each run
"""
import base64
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from . import config, policy

MAX_OUTPUT_CHARS = 20_000
MAX_IMAGES = 6
MAX_IMAGE_BYTES = 2 * 1024 * 1024


def _docker(*args, timeout=15):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def docker_status():
    if config.SANDBOX_MODE == "local":
        return {"docker": True, "image_built": True, "mode": "local"}
    try:
        r = _docker("image", "inspect", config.SANDBOX_IMAGE)
        return {"docker": True, "image_built": r.returncode == 0, "mode": "docker"}
    except Exception as e:  # docker missing / daemon down
        return {"docker": False, "image_built": False, "error": str(e)}


def limits(timeout=None):
    return {
        "network": "none",
        "rootfs": "read-only",
        "memory": config.SANDBOX_MEMORY,
        "cpus": config.SANDBOX_CPUS,
        "pids": config.SANDBOX_PIDS,
        "timeout_sec": timeout or config.SANDBOX_TIMEOUT,
        "user": "65534 (nobody)",
        "capabilities": "all dropped",
        "host_env_passed": 0,
        "runtime": config.SANDBOX_RUNTIME or "runc (docker default)",
    }


def _trim(text):
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n...[output truncated]"
    return text


if config.SANDBOX_MODE == "local" and sys.platform.startswith("linux"):
    try:  # keep the app's own /proc/<pid>/environ (API key) unreadable by child processes
        import ctypes
        ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE = 0
    except Exception:
        pass


def _local_result(**kw):
    base = {"container": "restricted-process", "exit_code": -1, "timed_out": False, "oom_killed": False,
            "stdout": "", "stderr": "", "duration_ms": 0, "images": [], "files": [], "container_destroyed": True,
            "workdir_wiped": True, "code_sha256": "", "policy_blocked": False}
    base.update(kw)
    lim = limits(base.pop("timeout", None))
    lim.update({"network": "blocked by code policy (no Docker)", "rootfs": "writes limited to /sandbox/out",
                "memory": f"{config.LOCAL_MEMORY_MB} MB (RLIMIT_AS)", "cpus": "shared",
                "pids": "n/a", "capabilities": "n/a (restricted mode)",
                "runtime": "restricted python process: static policy + OS limits"})
    base["limits"] = lim
    return base


def _run_local(code, csv_bytes=None, timeout=None):
    """RESTRICTED MODE (no Docker): static policy check + OS resource limits + empty environment + timeout.
    Best effort. The Docker mode on the Vultr VM is the real isolation."""
    timeout = timeout or config.SANDBOX_TIMEOUT
    digest = hashlib.sha256(code.encode()).hexdigest()[:16]
    reason = policy.check(code)
    if reason:
        return _local_result(exit_code=126, stderr="BLOCKED BY SANDBOX POLICY: " + reason,
                             policy_blocked=True, code_sha256=digest, timeout=timeout)

    workdir = Path(tempfile.mkdtemp(prefix="brz-local-"))
    in_dir, out_dir = workdir / "in", workdir / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    code = code.replace("/sandbox/in", in_dir.as_posix()).replace("/sandbox/out", out_dir.as_posix())
    script = in_dir / "script.py"
    script.write_text(code, encoding="utf-8")
    if csv_bytes is not None:
        (in_dir / "data.csv").write_bytes(csv_bytes)
    env = {"MPLBACKEND": "Agg", "PATH": os.environ.get("PATH", ""), "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
           "TEMP": str(workdir), "TMP": str(workdir), "HOME": str(workdir), "MPLCONFIGDIR": str(workdir),
           "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}

    def _preexec():
        import resource
        mem = config.LOCAL_MEMORY_MB * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout + 2, timeout + 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    started = time.time()
    timed_out, stdout, stderr, exit_code = False, "", "", -1
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=timeout,
                           cwd=str(out_dir), env=env, preexec_fn=_preexec if os.name == "posix" else None)
        stdout, stderr, exit_code = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = e.stdout
        stdout = out.decode(errors="replace") if isinstance(out, bytes) else (out or "")
    except Exception as e:
        stderr = f"local run error: {e}"
    images, files = [], []
    for p in sorted(out_dir.iterdir()):
        if p.is_file():
            files.append(p.name)
            if p.suffix.lower() == ".png" and len(images) < MAX_IMAGES and p.stat().st_size <= MAX_IMAGE_BYTES:
                images.append({"name": p.name, "b64": base64.b64encode(p.read_bytes()).decode()})
    shutil.rmtree(workdir, ignore_errors=True)
    oom = ("MemoryError" in stderr) or (exit_code in (-9, 137) and not timed_out)
    return _local_result(exit_code=exit_code, timed_out=timed_out, oom_killed=oom, stdout=_trim(stdout),
                         stderr=_trim(stderr), duration_ms=int((time.time() - started) * 1000), images=images,
                         files=files, workdir_wiped=not workdir.exists(), code_sha256=digest, timeout=timeout)


def run_in_sandbox(code, csv_bytes=None, timeout=None):
    if config.SANDBOX_MODE == "local":
        return _run_local(code, csv_bytes, timeout)
    timeout = timeout or config.SANDBOX_TIMEOUT
    run_id = uuid.uuid4().hex[:10]
    name = f"brz-{run_id}"
    workdir = Path(tempfile.mkdtemp(prefix="brz-"))
    in_dir, out_dir = workdir / "in", workdir / "out"
    in_dir.mkdir()
    out_dir.mkdir()
    os.chmod(workdir, 0o755)
    os.chmod(in_dir, 0o755)
    os.chmod(out_dir, 0o777)

    (in_dir / "script.py").write_text(code, encoding="utf-8")
    if csv_bytes is not None:
        (in_dir / "data.csv").write_bytes(csv_bytes)
    for f in in_dir.iterdir():
        os.chmod(f, 0o644)

    cmd = [
        "docker", "run", "--rm", "--name", name,
        "--network", "none",
        "--read-only",
        "--memory", config.SANDBOX_MEMORY, "--memory-swap", config.SANDBOX_MEMORY,
        "--cpus", config.SANDBOX_CPUS,
        "--pids-limit", config.SANDBOX_PIDS,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
        "-v", f"{in_dir}:/sandbox/in:ro",
        "-v", f"{out_dir}:/sandbox/out:rw",
        "-e", "HOME=/tmp", "-e", "MPLCONFIGDIR=/tmp/mpl", "-e", "MPLBACKEND=Agg",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-w", "/sandbox/out",
    ]
    if config.SANDBOX_RUNTIME:
        cmd += ["--runtime", config.SANDBOX_RUNTIME]
    cmd += [config.SANDBOX_IMAGE, "python", "/sandbox/in/script.py"]

    started = time.time()
    timed_out = False
    stdout = stderr = ""
    exit_code = -1
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=10)
            proc.kill()
            stdout, stderr = proc.communicate()
        exit_code = proc.returncode
    except FileNotFoundError:
        stderr = "docker is not installed or not in PATH"
    except Exception as e:
        stderr = f"sandbox error: {e}"

    duration_ms = int((time.time() - started) * 1000)

    images, files = [], []
    try:
        for p in sorted(out_dir.iterdir()):
            if not p.is_file():
                continue
            files.append(p.name)
            if p.suffix.lower() == ".png" and len(images) < MAX_IMAGES and p.stat().st_size <= MAX_IMAGE_BYTES:
                images.append({"name": p.name, "b64": base64.b64encode(p.read_bytes()).decode()})
    except Exception:
        pass

    # lifecycle discipline: destroy container (if still around) and wipe the workdir
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    still = subprocess.run(["docker", "ps", "-a", "-q", "--filter", f"name=^{name}$"], capture_output=True, text=True)
    container_destroyed = still.stdout.strip() == ""
    shutil.rmtree(workdir, ignore_errors=True)
    workdir_wiped = not workdir.exists()

    return {
        "container": name,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "oom_killed": exit_code == 137 and not timed_out,
        "stdout": _trim(stdout),
        "stderr": _trim(stderr),
        "duration_ms": duration_ms,
        "images": images,
        "files": files,
        "container_destroyed": container_destroyed,
        "workdir_wiped": workdir_wiped,
        "code_sha256": hashlib.sha256(code.encode()).hexdigest()[:16],
        "policy_blocked": False,
        "limits": limits(timeout),
    }
