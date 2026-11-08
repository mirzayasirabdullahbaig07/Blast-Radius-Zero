"""Static safety policy for RESTRICTED MODE (used when Docker is not available, e.g. Streamlit Cloud).

Best-effort only. It is NOT a replacement for the Docker sandbox: it rejects obviously dangerous model code
before it runs (imports, file access, network, env, dunder tricks). Docker mode on the Vultr VM is the real isolation.
"""
import ast

ALLOWED_IMPORTS = {
    "pandas", "numpy", "matplotlib", "scipy", "math", "statistics", "datetime", "collections", "itertools",
    "re", "json", "textwrap", "functools", "decimal", "fractions", "random", "string", "calendar", "warnings",
}
BLOCKED_NAMES = {"eval", "exec", "compile", "__import__", "open", "input", "globals", "locals", "vars",
                 "getattr", "setattr", "delattr", "breakpoint", "exit", "quit", "help"}
BLOCKED_ATTRS = {
    "system", "popen", "spawn", "fork", "environ", "getenv", "os", "sys", "subprocess", "modules", "builtins",
    "importlib", "read_pickle", "to_pickle", "read_html", "read_sql", "read_clipboard", "read_excel", "read_json",
    "read_parquet", "read_feather", "read_table", "read_fwf", "load", "loadtxt", "genfromtxt", "fromfile",
    "tofile", "save", "savez", "savetxt", "to_csv", "to_excel", "to_json", "to_html", "to_parquet", "to_sql",
    "to_clipboard", "imread", "imsave", "urlopen", "urlretrieve",
}
BAD_PATH_PARTS = ("/proc", "/etc", "/home", "/root", "/var", "/usr", "/sys", "../", "/..", "~/")
BAD_WORDS = (".env", "api_key", "apikey", "secret", "token")


def check(code):
    """Return None if the code passes, else a short reason string."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # let Python report the syntax error normally
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"import of '{a.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"import from '{node.module}' is not allowed"
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            return f"use of '{node.id}' is not allowed"
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") or node.attr in BLOCKED_ATTRS:
                return f"access to '.{node.attr}' is not allowed"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value.lower()
            if any(p in s for p in BAD_PATH_PARTS) or any(w in s for w in BAD_WORDS):
                return "suspicious path or secret-looking string"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            first = node.args[0] if node.args else None
            lit = first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
            if node.func.attr == "read_csv" and lit != "/sandbox/in/data.csv":
                return "read_csv may only read /sandbox/in/data.csv"
            if node.func.attr == "savefig" and not (lit and lit.startswith("/sandbox/out/")):
                return "savefig may only write inside /sandbox/out/"
    return None
