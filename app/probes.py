"""Containment Lab: hostile programs that try to break out. Each must be BLOCKED.
They run through the exact same sandbox as normal analysis - this is the 'containment moment' for the demo."""
from . import sandbox

_BLOCKED = lambda r: "BLOCKED" in r["stdout"] and "BREACH" not in r["stdout"]

PROBES = {
    "network": {
        "title": "Phone home over the internet",
        "attack": "Opens a TCP connection to 1.1.1.1:53 to exfiltrate data.",
        "code": '''
import socket
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3)
    print("BREACH: network is reachable")
except Exception as e:
    print("BLOCKED: no network route (" + type(e).__name__ + ")")
''',
        "verdict": _BLOCKED,
    },
    "filesystem": {
        "title": "Write to the system, look for the Docker socket",
        "attack": "Tries to create files in /etc and /usr and checks for /var/run/docker.sock.",
        "code": '''
import os
breaches = []
for p in ("/etc/pwned", "/usr/pwned", "/pwned"):
    try:
        open(p, "w").write("x")
        breaches.append("wrote " + p)
    except Exception:
        pass
if os.path.exists("/var/run/docker.sock"):
    breaches.append("docker.sock visible")
print("BREACH: " + ", ".join(breaches) if breaches else "BLOCKED: read-only filesystem, no docker socket")
''',
        "verdict": _BLOCKED,
    },
    "secrets": {
        "title": "Steal API keys from the environment",
        "attack": "Scans every environment variable for keys, tokens and passwords.",
        "code": '''
import os
words = ("KEY", "TOKEN", "SECRET", "PASSWORD", "VULTR", "OPENAI", "ANTHROPIC")
bad = [k for k in os.environ if any(w in k.upper() for w in words)]
print("BREACH: secrets visible " + str(bad) if bad else "BLOCKED: no secrets in the sandbox (" + str(len(os.environ)) + " harmless vars)")
''',
        "verdict": _BLOCKED,
    },
    "memory": {
        "title": "Memory bomb",
        "attack": "Allocates memory in 50 MB chunks until the machine would run out.",
        "code": '''
chunks = []
for i in range(1, 60):
    chunks.append(b"x" * (50 * 1024 * 1024))
    print("allocated", i * 50, "MB", flush=True)
print("BREACH: allocated 3 GB")
''',
        "verdict": lambda r: r["exit_code"] != 0 and "BREACH" not in r["stdout"],
    },
    "forkbomb": {
        "title": "Fork bomb",
        "attack": "Spawns processes in a loop to exhaust the host.",
        "code": '''
import os, time
kids = 0
try:
    for _ in range(1000):
        pid = os.fork()
        if pid == 0:
            time.sleep(4)
            os._exit(0)
        kids += 1
    print("BREACH: spawned", kids, "processes")
except OSError as e:
    print("BLOCKED: process limit hit after", kids, "processes (" + str(e.strerror) + ")")
''',
        "verdict": _BLOCKED,
    },
    "timeout": {
        "title": "Infinite loop",
        "attack": "Burns CPU forever to hold the machine hostage.",
        "code": '''
print("starting infinite loop", flush=True)
while True:
    pass
''',
        "verdict": lambda r: r["timed_out"],
    },
}


def public_list():
    return [{"id": k, "title": v["title"], "attack": v["attack"], "code": v["code"].strip()} for k, v in PROBES.items()]


def run_probe(pid):
    p = PROBES[pid]
    res = sandbox.run_in_sandbox(p["code"], None, timeout=5)
    return {
        "id": pid, "title": p["title"], "attack": p["attack"],
        "contained": bool(res.get("policy_blocked") or p["verdict"](res)),
        "policy_blocked": bool(res.get("policy_blocked")), "reason": res["stderr"][-200:] if res.get("policy_blocked") else "",
        "stdout": res["stdout"][-600:], "exit_code": res["exit_code"],
        "timed_out": res["timed_out"], "oom_killed": res["oom_killed"],
        "container_destroyed": res["container_destroyed"], "workdir_wiped": res["workdir_wiped"],
        "duration_ms": res["duration_ms"],
    }
