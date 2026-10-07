"""Reading the repository: the shallow HCL/Terraform scanner, the file view the checks work on, and git changes.

The HCL scanner is intentionally not a full parser. It understands comments, strings and heredocs well enough to locate
`resource`, `data`, `variable`, `output` and `module` blocks (formatted with `terraform fmt`, i.e. starting in column 0) and
to return their bodies. Anything needing real semantics belongs to terraform / TFLint.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

import yaml

# ----------------------------------------------------------------------------------------------------------------
# HCL scanner
# ----------------------------------------------------------------------------------------------------------------
BLOCK_RE = re.compile(
    r'^(resource|data|variable|output|module)[ \t]+((?:"[^"\n]*"[ \t]*)+)\{', re.MULTILINE
)
_STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"')
HEREDOC_RE = re.compile(r"<<-?([A-Za-z_][A-Za-z0-9_]*)\n")


@dataclass
class Block:
    kind: str
    labels: List[str]
    body: str
    file: str
    line: int
    attrs: Dict[str, str] = field(default_factory=dict)

    @property
    def type(self) -> str:
        return self.labels[0] if self.labels else ""

    @property
    def name(self) -> str:
        return self.labels[-1] if self.labels else ""

    @property
    def address(self) -> str:
        if self.kind == "resource":
            return "{}.{}".format(self.labels[0], self.labels[1])
        return "{}.{}".format(self.kind, self.name)


def _mask(text: str):
    """Return (no_comments, no_strings) variants with identical length/newlines."""
    n = len(text)
    nc = list(text)
    ns = list(text)
    i = 0

    def blank(buf, a, b):
        for k in range(a, b):
            if buf[k] != "\n":
                buf[k] = " "

    while i < n:
        c = text[i]
        if c == "#" or text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j == -1 else j
            blank(nc, i, j)
            blank(ns, i, j)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank(nc, i, j)
            blank(ns, i, j)
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            blank(ns, i + 1, j)
            i = j + 1
        elif text.startswith("<<", i) and HEREDOC_RE.match(text, i):
            m = HEREDOC_RE.match(text, i)
            end = re.compile(r"^[ \t]*%s[ \t]*$" % re.escape(m.group(1)), re.MULTILINE).search(text, m.end())
            j = end.end() if end else n
            blank(nc, m.end(), j)
            blank(ns, m.end(), j)
            i = j
        else:
            i += 1
    return "".join(nc), "".join(ns)


def parse(text: str, file: str) -> List[Block]:
    no_comments, no_strings = _mask(text)
    blocks: List[Block] = []
    for m in BLOCK_RE.finditer(no_comments):
        open_pos = m.end() - 1
        depth = 0
        end = None
        for k in range(open_pos, len(no_strings)):
            ch = no_strings[k]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = k
                    break
        if end is None:
            continue
        labels = re.findall(r'"([^"\n]*)"', m.group(2))
        body = no_comments[open_pos + 1 : end]
        blocks.append(
            Block(
                kind=m.group(1),
                labels=labels,
                body=body,
                file=file,
                line=text.count("\n", 0, m.start()) + 1,
                attrs=_attrs(body),
            )
        )
    return blocks


def _attrs(body: str) -> Dict[str, str]:
    """Top-level `key = value` attributes (values may span lines when bracketed)."""
    attrs: Dict[str, str] = {}
    depth = 0
    cur_key = None
    cur_val: List[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if depth == 0:
            m = re.match(r"^([A-Za-z_][\w-]*)\s*=\s*(.*)$", stripped)
            if m:
                if cur_key is not None:
                    attrs[cur_key] = "\n".join(cur_val).strip()
                cur_key, cur_val = m.group(1), [m.group(2)]
            elif cur_key is not None and not stripped:
                continue
            elif cur_key is not None:
                attrs[cur_key] = "\n".join(cur_val).strip()
                cur_key, cur_val = None, []
        else:
            if cur_key is not None:
                cur_val.append(stripped)
        bare = _STRING_RE.sub('""', line)
        depth += sum(bare.count(c) for c in "{[(") - sum(bare.count(c) for c in "}])")
        depth = max(depth, 0)
    if cur_key is not None:
        attrs[cur_key] = "\n".join(cur_val).strip()
    return attrs


# ----------------------------------------------------------------------------------------------------------------
# Repository view
# ----------------------------------------------------------------------------------------------------------------
EXCLUDED_DIRS = {".terraform", ".git", ".venv", "node_modules", "__pycache__", "tools"}

# Changes that cannot alter a plan: documentation and module tests.
_IGNORED_SUFFIXES = (".md", ".tftest.hcl")
# A change to one of these affects every root configuration (the Terraform version is shared).
_GLOBAL_FILES = {".terraform-version"}

_FILE_REF = re.compile(r'path\.module\}/([^"\)]+)|(?:file|templatefile)\(\s*"(\.{1,2}/[^"]+)"')
_PROVIDER = re.compile(r'^\s*provider\s+"', re.MULTILINE)
_BACKEND = re.compile(r'^\s*backend\s+"', re.MULTILINE)

CONFIG_DEFAULTS: Dict[str, Any] = {"roots": None, "modules": ["modules"], "protected": [], "deploy": {}, "conventions": {}}


def slug(path: str) -> str:
    """A filesystem- and artifact-safe name for a root path: infra/web -> infra-web."""
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-") or "root"


def glob_match(pattern: str, path: str) -> bool:
    """Shell-like glob where `*` stays inside one path segment and `**` crosses segments."""
    rx = re.escape(pattern.strip("/")).replace(r"\*\*", "\0").replace(r"\*", "[^/]*").replace("\0", ".*")
    return re.fullmatch(rx, path.strip("/")) is not None


def load_config(root: str) -> Dict[str, Any]:
    """The consumer's `terraform:` block of common.yaml. The names of the folders are the consumer's decision."""
    cfg = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v) for k, v in CONFIG_DEFAULTS.items()}
    path = os.path.join(root, "common.yaml")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            block = (yaml.safe_load(fh) or {}).get("terraform") or {}
        for k in CONFIG_DEFAULTS:
            if block.get(k) is not None:
                cfg[k] = block[k]
    return cfg


def _dir(path: str) -> str:
    return os.path.dirname(path) or "."


class Repo:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.cfg = load_config(self.root)
        self._blocks: Dict[str, List[Block]] = {}
        self._text: Dict[str, str] = {}
        self.tf_files = self._discover()
        self._calls: Optional[Dict[str, Set[str]]] = None
        self._roots: Optional[List[str]] = None
        self._modules: Optional[List[str]] = None

    def _discover(self) -> List[str]:
        found = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED_DIRS)
            for f in sorted(filenames):
                if f.endswith(".tf"):
                    found.append(os.path.relpath(os.path.join(dirpath, f), self.root))
        return found

    def text(self, rel: str) -> str:
        if rel not in self._text:
            with open(os.path.join(self.root, rel), encoding="utf-8", errors="replace") as fh:
                self._text[rel] = fh.read()
        return self._text[rel]

    def blocks(self, rel: str) -> List[Block]:
        if rel not in self._blocks:
            self._blocks[rel] = parse(self.text(rel), rel)
        return self._blocks[rel]

    def all_blocks(self, kind: Optional[str] = None) -> List[Block]:
        out = []
        for rel in self.tf_files:
            out.extend(b for b in self.blocks(rel) if kind is None or b.kind == kind)
        return out

    def files_in(self, directory: str) -> List[str]:
        return [f for f in self.tf_files if _dir(f) == directory]

    def exists(self, rel: str) -> bool:
        return os.path.exists(os.path.join(self.root, rel))

    def listdir(self, rel: str) -> List[str]:
        p = os.path.join(self.root, rel)
        return sorted(os.listdir(p)) if os.path.isdir(p) else []

    def line_count(self, rel: str) -> Optional[int]:
        try:
            return self.text(rel).count("\n") + 1
        except OSError:
            return None

    # ------------------------------------------------------------------------------------------------------------
    # Discovery: which folders are Terraform root configurations, which are shared modules, and what a change touches
    # ------------------------------------------------------------------------------------------------------------
    def dirs(self) -> List[str]:
        """Every folder that directly contains .tf files."""
        return sorted({_dir(f) for f in self.tf_files})

    def local_calls(self) -> Dict[str, Set[str]]:
        """folder -> the folders it calls as modules through a local `source` ("./x", "../x")."""
        if self._calls is None:
            known = set(self.dirs())
            calls: Dict[str, Set[str]] = {d: set() for d in known}
            for f in self.tf_files:
                for b in self.blocks(f):
                    if b.kind != "module":
                        continue
                    src = b.attrs.get("source", "").strip().strip('"')
                    if src.startswith(("./", "../")):
                        target = os.path.normpath(os.path.join(_dir(f), src)).replace(os.sep, "/")
                        if target in known:
                            calls[_dir(f)].add(target)
            self._calls = calls
        return self._calls

    def _under_module_base(self, directory: str) -> bool:
        return any(directory == b.strip("/") or directory.startswith(b.strip("/") + "/") for b in self.cfg["modules"])

    def roots(self) -> List[str]:
        """Independent Terraform configurations. Configured globs win; otherwise a folder is a root when nobody calls it as a
        module, it is not under a modules base folder, and it declares a provider or a backend, or has resources or modules of its own."""
        if self._roots is None:
            configured = self.cfg["roots"]
            dirs = self.dirs()
            if configured:
                found = [d for d in dirs if any(glob_match(g, d) for g in configured)]
            else:
                called = {t for ts in self.local_calls().values() for t in ts}
                found = []
                for d in dirs:
                    if d in called or self._under_module_base(d):
                        continue
                    files = self.files_in(d)
                    text = "\n".join(self.text(f) for f in files)
                    composes = any(b.kind in ("module", "resource") for f in files for b in self.blocks(f))
                    if _PROVIDER.search(text) or _BACKEND.search(text) or composes:
                        found.append(d)
            self._roots = sorted(found)
        return self._roots

    def module_dirs(self) -> List[str]:
        """Shared modules: folders under a modules base, plus anything a configuration calls through a local source."""
        if self._modules is None:
            roots = set(self.roots())
            called = {t for ts in self.local_calls().values() for t in ts}
            mods = {d for d in self.dirs() if self._under_module_base(d)} | called
            self._modules = sorted(mods - roots)
        return self._modules

    def is_module_dir(self, directory: str) -> bool:
        return directory in set(self.module_dirs())

    def module_relpath(self, directory: str) -> str:
        """Path of a module below its modules base folder (modules/eks/cluster -> eks/cluster)."""
        for b in self.cfg["modules"]:
            b = b.strip("/")
            if directory.startswith(b + "/"):
                return directory[len(b) + 1:]
        return directory

    def closure(self, root: str) -> Set[str]:
        """The root folder plus every module folder it uses, transitively."""
        seen, todo = {root}, [root]
        calls = self.local_calls()
        while todo:
            for t in calls.get(todo.pop(), ()):
                if t not in seen:
                    seen.add(t)
                    todo.append(t)
        return seen

    def shared_files(self, directory: str) -> Set[str]:
        """Files outside the folder that its code reads (file(), templatefile(), yamldecode(file(...)) with ../ paths)."""
        out: Set[str] = set()
        for f in self.files_in(directory):
            for m in _FILE_REF.finditer(self.text(f)):
                rel = m.group(1) or m.group(2)
                path = os.path.normpath(os.path.join(directory, rel)).replace(os.sep, "/")
                if not path.startswith("..") and _dir(path) != directory:
                    out.add(path)
        return out

    def is_protected(self, root: str) -> bool:
        return any(glob_match(g, root) for g in self.cfg["protected"])

    def affected(self, changed_paths: List[str]) -> List[Dict[str, Any]]:
        """Root configurations touched by a change: edited themselves, edited in a module they use (transitively), or
        edited in a shared file they read. Roots nothing touched are not returned, so nothing is run for them."""
        changed = [p for p in changed_paths if not p.endswith(_IGNORED_SUFFIXES) and "/tests/" not in "/" + p]
        out = []
        for r in self.roots():
            deps = self.closure(r)
            shared = {p for d in deps for p in self.shared_files(d)}
            reasons = set()
            for p in changed:
                d = _dir(p)
                if os.path.basename(p) in _GLOBAL_FILES:
                    reasons.add("{} changed (shared by every configuration)".format(p))
                elif p in shared:
                    reasons.add("shared file {} changed".format(p))
                elif d == r or (r != "." and d.startswith(r + "/")):
                    reasons.add("{} changed".format(p))
                elif d in deps:
                    reasons.add("module {} changed ({})".format(d, os.path.basename(p)))
            if reasons:
                out.append({"root": r, "reasons": sorted(reasons)})
        return out


def git_changed_files(root: str, base: str) -> List[Dict[str, str]]:
    """Files changed between `base` and HEAD, as {status, path}."""
    out = subprocess.run(
        ["git", "-C", root, "diff", "--name-status", "--no-renames", "{}...HEAD".format(base)],
        capture_output=True, text=True, check=True,
    ).stdout
    changed = []
    for line in out.splitlines():
        status, _, path = line.partition("\t")
        changed.append({"status": {"A": "added", "M": "modified", "D": "deleted"}.get(status[:1], status), "path": path})
    return changed
