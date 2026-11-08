"""Plan -> write code -> run in sandbox -> self-heal on errors -> explain real output."""
import re
import time
import uuid

from . import config, llm, sandbox

SYSTEM = """You are a careful data analyst. You write Python 3 that runs inside a locked-down sandbox.
Sandbox facts:
- No internet, no pip install, no other files. Available: pandas, numpy, matplotlib, scipy.
- If a dataset was provided it is at /sandbox/in/data.csv.
- Save every chart as PNG into /sandbox/out/ (example: plt.savefig('/sandbox/out/chart.png', dpi=130, bbox_inches='tight')). Use plt.close() afterwards.
- Print the key numbers with print(). The user only sees what you print and the PNG files.
- Keep the script short and deterministic. Never try to touch the network, the environment or the filesystem outside /sandbox.
Reply with ONE ```python code block and nothing else."""

EXPLAIN_SYSTEM = """You explain the result of an executed analysis to a non-technical person.
Rules: use ONLY numbers that appear in the program output, never invent values, max 140 words, plain language.
If charts were produced, mention what they show. If the run failed, say so honestly and what was tried."""

PROFILE_CODE = '''
import pandas as pd
df, err = None, None
for enc in ("utf-8", "latin-1"):
    try:
        df = pd.read_csv("/sandbox/in/data.csv", encoding=enc)
        break
    except Exception as e:
        err = e
if df is None:
    print("ERROR: could not parse CSV:", err)
    raise SystemExit(1)
print("shape:", df.shape)
print("columns and dtypes:")
print(df.dtypes.to_string())
print("first rows:")
print(df.head(5).to_string())
print("missing values:", int(df.isna().sum().sum()))
'''


RESTRICTED_RULES = """
Extra rules (restricted mode): allowed imports only pandas, numpy, matplotlib, scipy, math, statistics, datetime, collections, itertools, re, json.
Do NOT import os/sys/subprocess/socket, do not use open(), eval, exec, getattr or dunder attributes.
Read data ONLY with pd.read_csv('/sandbox/in/data.csv') (that exact literal string) and save charts ONLY with plt.savefig('/sandbox/out/<name>.png') (literal string path)."""


def extract_code(text):
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.S)
    return m.group(1).strip() if m else ""


def _tail(text, n=1500):
    return text[-n:] if len(text) > n else text


def analyze(question, csv_bytes=None, filename=None):
    run_id = uuid.uuid4().hex[:8]
    t0 = time.time()
    timeline, attempts = [], []

    def note(kind, title, detail=""):
        timeline.append({"t_ms": int((time.time() - t0) * 1000), "kind": kind, "title": title, "detail": detail})

    note("plan", "Request received", f"question: {question[:200]}")

    profile = None
    if csv_bytes:
        note("sandbox", "Profiling the CSV inside the sandbox", "the host never parses uploaded data")
        profile = sandbox.run_in_sandbox(PROFILE_CODE, csv_bytes)
        if profile["exit_code"] != 0:
            note("error", "CSV could not be read", _tail(profile["stdout"] + profile["stderr"]))
            return {"run_id": run_id, "success": False, "attempts": [], "timeline": timeline,
                    "explanation": "The CSV file could not be parsed in the sandbox: " + _tail(profile["stdout"] + profile["stderr"], 400),
                    "profile": None, "images": [], "stdout": "", "containment": profile["limits"],
                    "total_ms": int((time.time() - t0) * 1000), "model": "-"}

    user_msg = f"Question: {question}\n\n"
    user_msg += ("Dataset profile (produced inside the sandbox):\n" + profile["stdout"]) if profile else "No dataset was provided."
    system = SYSTEM + (RESTRICTED_RULES if config.SANDBOX_MODE == "local" else "")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user_msg}]

    final = None
    for n in range(1, config.MAX_ATTEMPTS + 1):
        note("llm", f"Attempt {n}: asking Vultr Serverless Inference to write code")
        raw = llm.chat(messages)
        code = extract_code(raw)
        if not code:
            attempts.append({"n": n, "code": "", "ok": False, "error": "model returned no code block"})
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": "Return exactly one ```python code block."}]
            continue
        note("sandbox", f"Attempt {n}: running code in a fresh container")
        res = sandbox.run_in_sandbox(code, csv_bytes)
        ok = res["exit_code"] == 0 and not res["timed_out"]
        attempts.append({"n": n, "code": code, "ok": ok, "sandbox": res})
        if ok:
            note("verify", f"Attempt {n}: real output returned",
                 f"{res['duration_ms']} ms, container destroyed={res['container_destroyed']}")
            final = res
            break
        reason = "timed out" if res["timed_out"] else ("was killed: out of memory" if res["oom_killed"] else ("was blocked by the sandbox policy" if res.get("policy_blocked") else "exited with an error"))
        note("retry", f"Attempt {n} failed ({reason})", _tail(res["stderr"], 400))
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": f"The program {reason}.\nstderr:\n{_tail(res['stderr'])}\nstdout:\n{_tail(res['stdout'], 600)}\nFix it and return the full corrected program."}]

    if final:
        note("llm", "Explaining the executed result")
        prompt = (f"Question: {question}\n\nProgram output (real, from the sandbox):\n{final['stdout'][:6000]}\n"
                  f"Charts produced: {', '.join(i['name'] for i in final['images']) or 'none'}")
        explanation = llm.chat([{"role": "system", "content": EXPLAIN_SYSTEM},
                                {"role": "user", "content": prompt}], max_tokens=500)
    else:
        last_err = ""
        if attempts:
            a = attempts[-1]
            last_err = _tail(a.get("sandbox", {}).get("stderr", a.get("error", "")), 400)
        explanation = "Every attempt failed inside the sandbox, so there is no verified result. Last error: " + last_err

    last = final or next((a["sandbox"] for a in reversed(attempts) if a.get("sandbox")), None)
    return {
        "run_id": run_id,
        "success": bool(final),
        "question": question,
        "filename": filename,
        "attempts": attempts,
        "timeline": timeline,
        "explanation": explanation,
        "images": final["images"] if final else [],
        "stdout": final["stdout"] if final else "",
        "profile": profile["stdout"] if profile else None,
        "containment": last["limits"] if last else sandbox.limits(),
        "total_ms": int((time.time() - t0) * 1000),
        "model": llm.resolve_model(),
    }
