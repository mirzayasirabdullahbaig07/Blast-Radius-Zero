"""Blast Radius Zero - Streamlit dashboard.

Run:  streamlit run app.py
Uses the existing backend modules in the app/ folder (agent, sandbox, probes, llm, config).
"""
import html
from pathlib import Path

import streamlit as st

from app import agent, config, probes, sandbox

st.set_page_config(page_title="Blast Radius Zero", page_icon="🛡️", layout="wide")

BASE = Path(__file__).resolve().parent
SAMPLE_PATH = BASE / "samples" / "sales.csv"
LOCAL = config.SANDBOX_MODE == "local"

EXAMPLES = [
    "Which region sells the most, and how does revenue change by month?",
    "Show revenue by product as a bar chart and name the top product.",
    "Are there any outlier days in revenue? Plot them.",
]
KIND_ICON = {"plan": "🧭", "llm": "🧠", "sandbox": "📦", "verify": "✅", "retry": "🔁", "error": "⛔"}

# ----------------------------------------------------------------------------- styling
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Inter', system-ui, sans-serif; }
.stApp { background: #f3f5f9; color: #14202e; }
#MainMenu, footer, header[data-testid="stHeader"] { visibility: hidden; height: 0; }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1280px; }
section[data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #e2e7ee; }
h1, h2, h3, h4, p, label, span, li, div { color: inherit; }

.hero { background: linear-gradient(120deg, #0b1f3a 0%, #123a6b 60%, #0a6cff 140%);
  border-radius: 16px; padding: 1.8rem 2rem; margin-bottom: 1.2rem; }
.hero h1 { color: #fff !important; font-size: 2.1rem; font-weight: 800; margin: 0 0 .35rem; letter-spacing: -.02em; }
.hero p { color: #c9d9ee !important; margin: 0; font-size: 1.02rem; max-width: 62ch; line-height: 1.55; }
.hero .tags { margin-top: 1rem; display: flex; gap: .5rem; flex-wrap: wrap; }
.tag { background: rgba(255,255,255,.12); color: #fff !important; border: 1px solid rgba(255,255,255,.25);
  border-radius: 99px; padding: .22rem .75rem; font-size: .8rem; font-weight: 500; }

.card { background: #fff; border: 1px solid #e2e7ee; border-radius: 12px; padding: 1.1rem 1.25rem; margin-bottom: .9rem; }
.answer { background: #ecf8f3; border: 1px solid #b6e3d2; border-left: 5px solid #0b8a65; border-radius: 10px;
  padding: 1rem 1.2rem; font-size: 1.05rem; line-height: 1.6; color: #0d3b2c !important; }
.answer.fail { background: #fdeeed; border-color: #f0bbb7; border-left-color: #c8332b; color: #6d1b16 !important; }
.answer-title { font-weight: 700; font-size: .85rem; margin-bottom: .35rem; color: #0b6a4e; }
.answer.fail .answer-title { color: #a32922; }

.row { display: flex; align-items: center; gap: .55rem; padding: .28rem 0; font-size: .9rem; }
.dot { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.dot.ok { background: #0b8a65; } .dot.bad { background: #c8332b; } .dot.warn { background: #d98b00; }
.kv { display: flex; justify-content: space-between; font-size: .86rem; padding: .22rem 0; border-bottom: 1px dashed #e2e7ee; }
.kv span:last-child { font-weight: 600; }

.step { display: flex; gap: .7rem; padding: .55rem 0; border-bottom: 1px solid #edf0f5; }
.step small { color: #5b6b7b !important; display: block; font-size: .8rem; }
.step .t { color: #5b6b7b !important; font-size: .75rem; min-width: 56px; }

.probe-ok { background:#ecf8f3; border:1px solid #b6e3d2; border-radius:8px; padding:.6rem .85rem; color:#0d3b2c !important; font-size:.9rem; }
.probe-bad { background:#fdeeed; border:1px solid #f0bbb7; border-radius:8px; padding:.6rem .85rem; color:#6d1b16 !important; font-size:.9rem; }

div[data-testid="stMetric"] { background:#fff; border:1px solid #e2e7ee; border-radius:12px; padding: .8rem 1rem; }
div[data-testid="stMetricLabel"] p { color:#5b6b7b !important; font-size:.8rem; }
div[data-testid="stMetricValue"] { color:#14202e !important; font-weight:700; }
div.stButton > button { border-radius: 8px; font-weight: 600; border: 1px solid #c9d2de; background:#fff; color:#14202e; }
div.stButton > button:hover { border-color:#0a6cff; color:#0a6cff; }
div.stButton > button[kind="primary"] { background:#0a6cff; border-color:#0a6cff; color:#fff; }
div.stButton > button[kind="primary"]:hover { background:#0857cc; color:#fff; }
textarea { background:#fff !important; color:#14202e !important; }
button[data-baseweb="tab"] { font-weight: 600; }

/* ---- readable text everywhere (works even if the system theme is dark) ---- */
.stApp [data-testid="stMarkdownContainer"] p, .stApp [data-testid="stMarkdownContainer"] li,
.stApp [data-testid="stWidgetLabel"] p, .stApp label p, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 { color: #14202e; }
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p { color: #5b6b7b !important; }
button[data-baseweb="tab"] p { color: #3b4a5a; font-weight: 600; }
button[data-baseweb="tab"][aria-selected="true"] p { color: #0a6cff; }
[data-testid="stExpander"] { background: #fff; border: 1px solid #e2e7ee !important; border-radius: 10px; }
[data-testid="stExpander"] summary p, [data-testid="stExpander"] summary span { color: #14202e !important; }
[data-testid="stVerticalBlockBorderWrapper"] { background: #fff; border-radius: 12px; }
div[data-testid="stDownloadButton"] button { border-radius: 8px; font-weight: 600; border: 1px solid #c9d2de; background: #fff; }
div[data-testid="stDownloadButton"] button p { color: #14202e !important; }
div[data-testid="stDownloadButton"] button:hover { border-color: #0a6cff; }

/* ---- file uploader: visible text + clear blue button ---- */
[data-testid="stFileUploaderDropzone"] { background: #f1f6fd !important; border: 1.5px dashed #8fb0dc !important; border-radius: 12px; }
[data-testid="stFileUploaderDropzone"] div, [data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzone"] p { color: #14202e !important; }
[data-testid="stFileUploaderDropzone"] svg { color: #0a6cff !important; fill: #0a6cff !important; }
[data-testid="stFileUploaderDropzone"] button { background: #0a6cff !important; border: 1px solid #0a6cff !important; border-radius: 8px; }
[data-testid="stFileUploaderDropzone"] button, [data-testid="stFileUploaderDropzone"] button * { color: #ffffff !important; font-weight: 600; }
[data-testid="stFileUploaderDropzone"] button:hover { background: #0857cc !important; }
[data-testid="stFileUploaderFile"] *, [data-testid="stFileUploaderFileName"] { color: #14202e !important; }
[data-testid="stFileUploaderFile"] svg { color: #5b6b7b !important; fill: #5b6b7b !important; }

/* ---- onboarding cards ---- */
.start { display: grid; grid-template-columns: repeat(3, 1fr); gap: .9rem; margin-top: 1rem; }
.start .card b { color: #0a6cff; }
.start .card p { color: #5b6b7b !important; margin: .25rem 0 0; font-size: .92rem; }
.hist { font-size: .85rem; padding: .3rem 0; border-bottom: 1px solid #edf0f5; color: #14202e; }

/* ---- custom blocks: always dark readable text, whatever the theme ---- */
.row, .kv, .hist, .step, .card { color: #14202e; }
.row b, .kv span, .step b { color: #14202e; }
.row, .row b { font-size: .92rem; }

/* primary button label must be white */
div.stButton > button[kind="primary"] p, div.stButton > button[kind="primary"] span, div.stButton > button[kind="primary"] div { color: #ffffff !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------- helpers
def esc(x):
    return html.escape(str(x))


def row(ok, label, value=""):
    cls = "ok" if ok is True else ("warn" if ok is None else "bad")
    st.markdown(f'<div class="row"><span class="dot {cls}"></span><b>{esc(label)}</b>&nbsp;{esc(value)}</div>',
                unsafe_allow_html=True)


def build_report(r):
    lines = ["# Blast Radius Zero - run report", "", f"**Question:** {r.get('question', '')}",
             f"**Result:** {'Verified' if r['success'] else 'Failed'}  ",
             f"**Attempts:** {len(r['attempts'])}  |  **Time:** {r['total_ms'] / 1000:.1f}s  |  **Model:** {r['model']}",
             "", "## Answer", r["explanation"], "", "## Program output", "```", r["stdout"] or "(none)", "```", ""]
    for a in r["attempts"]:
        lines += [f"## Attempt {a['n']} ({'ok' if a.get('ok') else 'failed'})", "```python", a.get("code", ""), "```", ""]
    lines += ["## Containment used"] + [f"- {k}: {v}" for k, v in r["containment"].items()]
    return "\n".join(lines)


def set_question(text):
    st.session_state["question"] = text


def load_sample():
    st.session_state["use_sample"] = True


ss = st.session_state
ss.setdefault("question", "")
ss.setdefault("use_sample", False)
ss.setdefault("result", None)
ss.setdefault("probe_results", {})
ss.setdefault("history", [])
ss.setdefault("runs", 0)
MAX_RUNS = 15

# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 🛡️ Blast Radius Zero")
    st.caption("Sandboxed AI data analyst · Vultr")

    st.markdown("**Environment**")
    status = sandbox.docker_status()
    if LOCAL:
        row(None, "Mode", "restricted (no Docker)")
    else:
        row(status["docker"], "Docker", "running" if status["docker"] else "not found")
        row(status["image_built"], "Sandbox image", "ready" if status["image_built"] else "not built")
    row(bool(config.VULTR_API_KEY), "Vultr Inference key", "set" if config.VULTR_API_KEY else "missing")
    row(True, "Model", config.VULTR_MODEL)

    st.divider()
    st.markdown("**Dataset**")
    uploaded = st.file_uploader("Upload a CSV (max 5 MB)", type=["csv"], label_visibility="collapsed")
    st.button("Load sample dataset", on_click=load_sample, width="stretch")

    data, fname = None, None
    if uploaded is not None:
        data, fname = uploaded.getvalue(), uploaded.name
    elif ss["use_sample"] and SAMPLE_PATH.exists():
        data, fname = SAMPLE_PATH.read_bytes(), "sales.csv (sample)"

    if data is not None and len(data) > config.MAX_UPLOAD_BYTES:
        st.error("File is larger than 5 MB.")
        data = None
    if data is not None:
        st.success(f"{fname} · {len(data) / 1024:.1f} KB")
        _lines = data.decode("utf-8", errors="replace").splitlines()
        _cols = [c.strip() for c in _lines[0].split(",")] if _lines else []
        st.markdown(f'<div class="kv"><span>Rows</span><span>{max(len(_lines) - 1, 0)}</span></div>'
                    f'<div class="kv"><span>Columns</span><span>{len(_cols)}</span></div>', unsafe_allow_html=True)
        st.caption(", ".join(_cols[:8]) + (" …" if len(_cols) > 8 else ""))
        with st.expander("Raw preview (first lines)"):
            st.code("\n".join(_lines[:8]), language="text")
    else:
        st.caption("No file loaded. You can also ask a pure-code question.")

    st.divider()
    st.markdown("**Recent runs**")
    hist_box = st.container()
    st.divider()
    with st.expander("Sandbox limits"):
        for k, v in sandbox.limits().items():
            st.markdown(f'<div class="kv"><span>{esc(k.replace("_", " "))}</span><span>{esc(v)}</span></div>',
                        unsafe_allow_html=True)

# ----------------------------------------------------------------------------- hero
st.markdown(
    f"""
<div class="hero">
  <h1>Blast Radius Zero</h1>
  <p>Ask a question about your data. An AI on Vultr writes the code, a locked-down sandbox runs it,
  and you get verified, real output. Whatever the code does, it cannot leave the box.</p>
  <div class="tags">
    <span class="tag">Vultr Serverless Inference</span>
    <span class="tag">{'Restricted mode · policy + limits' if LOCAL else 'Docker isolation'}</span>
    <span class="tag">No network · No secrets · Time and memory caps</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tab_run, tab_lab, tab_how = st.tabs(["Analyze", "Containment lab", "How it works"])

# ----------------------------------------------------------------------------- analyze tab
with tab_run:
    st.markdown("##### Ask a question")
    st.text_area("Your question", key="question", height=100, label_visibility="collapsed",
                 placeholder="Which region sells the most, and how does revenue change by month?")
    c1, c2, c3 = st.columns(3)
    for col, text in zip((c1, c2, c3), EXAMPLES):
        col.button(text, on_click=set_question, args=(text,), width="stretch", key="ex_" + text[:12])

    go = st.button("Run analysis in sandbox", type="primary", width="stretch")

    if go:
        q = ss["question"].strip()
        if not q:
            st.warning("Type a question first, or pick an example above.")
        elif not config.VULTR_API_KEY:
            st.error("Vultr key is missing. Put VULTR_INFERENCE_API_KEY in the .env file, save, and restart the app.")
        elif ss["runs"] >= MAX_RUNS:
            st.warning("Demo limit reached for this session (15 runs). Refresh the page to start again.")
        elif not LOCAL and not (status["docker"] and status["image_built"]):
            st.error("Docker sandbox is not ready. Start Docker and build the image, or set SANDBOX_MODE=local for a test run.")
        else:
            ss["runs"] += 1
            with st.spinner("Writing code, running it in a fresh sandbox, verifying the output…"):
                try:
                    ss["result"] = agent.analyze(q, data, fname)
                    ss["history"].insert(0, {"q": q, "ok": ss["result"]["success"], "s": ss["result"]["total_ms"] / 1000})
                    ss["history"] = ss["history"][:6]
                except Exception as e:  # network, key, model errors
                    ss["result"] = None
                    st.error(f"Run failed: {e}")

    r = ss["result"]
    if r:
        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Result", "Verified" if r["success"] else "Failed")
        m2.metric("Attempts", f"{len(r['attempts'])} / {config.MAX_ATTEMPTS}")
        m3.metric("Total time", f"{r['total_ms'] / 1000:.1f} s")
        m4.metric("Isolation", "Restricted" if LOCAL else "Docker sandbox")

        cls = "answer" if r["success"] else "answer fail"
        title = "Answer (based on real executed output)" if r["success"] else "No verified result"
        st.markdown(f'<div class="{cls}"><div class="answer-title">{title}</div>{esc(r["explanation"])}</div>',
                    unsafe_allow_html=True)

        if r["images"]:
            import base64
            st.markdown("##### Charts produced by the sandbox")
            cols = st.columns(min(len(r["images"]), 2))
            for i, img in enumerate(r["images"]):
                png = base64.b64decode(img["b64"])
                cols[i % len(cols)].image(png, caption=img["name"], width="stretch")
                cols[i % len(cols)].download_button("Download chart", png, file_name=img["name"],
                                                    mime="image/png", key=f"dl_{r['run_id']}_{i}")

        d1, d2, _sp = st.columns([1, 1, 3])
        d1.download_button("Download report (.md)", build_report(r), file_name="blast-radius-report.md",
                           mime="text/markdown", key="dl_report_" + r["run_id"])
        if d2.button("Clear result"):
            ss["result"] = None
            st.rerun()

        t_out, t_code, t_log, t_cont = st.tabs(["Program output", "Code", "Run log", "Containment report"])
        with t_out:
            st.code(r["stdout"] or "(no output)", language="text")
        with t_code:
            for a in r["attempts"]:
                label = f"Attempt {a['n']} · {'succeeded' if a.get('ok') else 'failed'}"
                with st.expander(label, expanded=(a["n"] == len(r["attempts"]))):
                    st.code(a.get("code") or a.get("error", ""), language="python")
                    s = a.get("sandbox")
                    if s:
                        st.caption(f"exit code {s['exit_code']} · {s['duration_ms']} ms · hash {s['code_sha256']} "
                                   f"· container destroyed: {s['container_destroyed']} · workdir wiped: {s['workdir_wiped']}")
                        if s["stderr"]:
                            st.code(s["stderr"], language="text")
        with t_log:
            for t in r["timeline"]:
                st.markdown(
                    f'<div class="step"><span class="t">{t["t_ms"] / 1000:.1f}s</span>'
                    f'<div>{KIND_ICON.get(t["kind"], "•")} <b>{esc(t["title"])}</b>'
                    f'<small>{esc(t["detail"])}</small></div></div>',
                    unsafe_allow_html=True,
                )
            st.caption(f"Model used: {r['model']}")
        with t_cont:
            for k, v in r["containment"].items():
                st.markdown(f'<div class="kv"><span>{esc(k.replace("_", " "))}</span><span>{esc(v)}</span></div>',
                            unsafe_allow_html=True)
    else:
        st.markdown(
            """
<div class="start">
  <div class="card"><b>1. Load data</b><p>Use the sidebar: upload your CSV, or press Load sample dataset.</p></div>
  <div class="card"><b>2. Ask</b><p>Type a question in plain language, or tap one of the examples above.</p></div>
  <div class="card"><b>3. Run</b><p>The AI writes code, the sandbox runs it, and you get a verified answer with charts.</p></div>
</div>""",
            unsafe_allow_html=True,
        )

# ----------------------------------------------------------------------------- lab tab
with tab_lab:
    st.markdown("##### Containment lab")
    st.caption("Six hostile programs try to escape. They run through the same sandbox as your analysis. Every one must be blocked.")

    if LOCAL:
        st.info("Restricted mode: attacks are stopped by the code-policy check and OS resource limits. "
                "Docker mode (on a Vultr VM) adds full container isolation: no network, read-only filesystem, destroyed after every run.")

    lab = probes.public_list()
    done = ss["probe_results"]
    contained = sum(1 for v in done.values() if v["contained"])
    k1, k2 = st.columns(2)
    k1.metric("Attacks blocked", f"{contained} / {len(lab)}")
    k2.metric("Attacks run", len(done))

    if st.button("Run all attacks", type="primary"):
        bar = st.progress(0.0, text="Launching attacks…")
        for i, p in enumerate(lab):
            bar.progress(i / len(lab), text=f"Attacking: {p['title']}")
            ss["probe_results"][p["id"]] = probes.run_probe(p["id"])
        bar.empty()
        st.rerun()

    for p in lab:
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"**{p['title']}**")
            left.caption(p["attack"])
            if right.button("Launch", key="probe_" + p["id"], width="stretch"):
                with st.spinner("Attacking…"):
                    ss["probe_results"][p["id"]] = probes.run_probe(p["id"])
                st.rerun()
            with st.expander("Show attack code"):
                st.code(p["code"], language="python")
            res = ss["probe_results"].get(p["id"])
            if res:
                why = ("blocked by the code policy before running" if res.get("policy_blocked") else
                       "killed by the timeout" if res["timed_out"] else
                       "killed by the memory cap" if res["oom_killed"] else f"exit code {res['exit_code']}")
                last = esc(res["stdout"].strip().splitlines()[-1]) if res["stdout"].strip() else "(no output)"
                css = "probe-ok" if res["contained"] else "probe-bad"
                verdict = "Contained" if res["contained"] else "BREACH"
                st.markdown(
                    f'<div class="{css}"><b>{verdict}</b> · {why} · container destroyed: {res["container_destroyed"]} '
                    f'· {res["duration_ms"]} ms<br><code>{last}</code></div>',
                    unsafe_allow_html=True,
                )

# ----------------------------------------------------------------------------- how it works tab
with tab_how:
    st.markdown("##### How a request flows")
    s1, s2, s3, s4 = st.columns(4)
    for col, (n, t, d) in zip(
        (s1, s2, s3, s4),
        [
            ("1", "Ask", "You upload a CSV and ask a question in plain language."),
            ("2", "Write", "Vultr Serverless Inference writes Python code for it."),
            ("3", "Run", "The code runs in a throw-away container. Errors go back to the model for a retry."),
            ("4", "Verify", "You get real output, charts and a plain-language answer."),
        ],
    ):
        col.markdown(f'<div class="card"><b>{n}. {t}</b><br><span style="color:#5b6b7b">{d}</span></div>',
                     unsafe_allow_html=True)

    st.markdown("##### Containment guarantees")
    st.markdown(
        """
| Risk | Control |
|---|---|
| Code touches the host or the app | Runs in a separate container as a non-root user, all capabilities dropped |
| Code leaks data or calls home | No network inside the sandbox |
| Code steals API keys | The container receives zero environment variables; keys stay on the host |
| Code damages the system | Read-only filesystem, small temporary space that cannot execute files |
| Code hogs the machine | Memory cap, CPU cap, process cap and a wall-clock timeout on every run |
| Leftovers between runs | Container and temp folder are destroyed after every run |
"""
    )
    st.caption("Restricted mode is used where Docker is unavailable: it adds a static code policy, memory/CPU/time limits and an empty environment, "
               "but it is best-effort. The full containment above applies in Docker mode on a Vultr VM.")

with hist_box:
    if ss["history"]:
        for h in ss["history"]:
            icon = "✅" if h["ok"] else "⛔"
            st.markdown(f'<div class="hist">{icon} {esc(h["q"][:46])}{"…" if len(h["q"]) > 46 else ""} · {h["s"]:.0f}s</div>',
                        unsafe_allow_html=True)
    else:
        st.caption("Your runs will appear here.")