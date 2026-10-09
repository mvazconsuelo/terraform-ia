"""A read-only view of the Terraform repository, and the discovery of what a change affects.

The vocabulary used here:

  * a ROOT is a folder where Terraform is run (it has its own state): `infra/web`, `infra-example/dev/web-demo`...
  * a MODULE is a folder that roots (or other modules) call: `modules/vpc`...
  * a change AFFECTS a root when it edits the root, a module the root uses, or a shared file the root reads.

`Repo` answers these questions from the code itself, so nothing has to be registered by hand.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Set

import yaml

from .read_tf_files import Block, parse

# Folders that never hold the Terraform we care about.
EXCLUDED_DIRS = {".terraform", ".git", ".venv", "node_modules", "__pycache__", "tools"}

# A changed file with one of these endings can never change a plan (documentation).
_IGNORED_SUFFIXES = (".md",)

# A change to one of these files affects EVERY root (the Terraform version is shared).
_GLOBAL_FILES = {".terraform-version"}

# A file that Terraform code reads from outside its own folder. Matches both forms:
#   yamldecode(file("${path.module}/../../common.yaml"))   -> group 1 = ../../common.yaml
#   file("../shared/policy.json")                          -> group 2 = ../shared/policy.json
_FILE_REF = re.compile(r'path\.module\}/([^"\)]+)|(?:file|templatefile)\(\s*"(\.{1,2}/[^"]+)"')

# A provider block or a backend block at the start of a line (a sign that a folder is a root).
_PROVIDER = re.compile(r'^\s*provider\s+"', re.MULTILINE)
_BACKEND = re.compile(r'^\s*backend\s+"', re.MULTILINE)

# The `terraform:` settings of common.yaml and their defaults. Every key is optional.
CONFIG_DEFAULTS: Dict[str, Any] = {
    "roots": None,        # globs of the root folders; None = infer them from the code
    "modules": ["modules"],   # folders that hold shared modules
    "environments": {},   # environment name -> {branch, roots}: the branch that deploys it and its roots (paths or globs)
}


def slug(path: str) -> str:
    """A file-name-safe version of a root path: `infra/web` -> `infra-web`."""
    return re.sub(r"[^A-Za-z0-9]+", "-", path).strip("-") or "root"


def glob_match(pattern: str, path: str) -> bool:
    """Shell-like pattern match where `*` stays inside one folder name and `**` crosses folders.

    infra/*    matches infra/web         but not infra/web/stack
    infra/**   matches infra/web/stack"""
    regex = re.escape(pattern.strip("/"))
    regex = regex.replace(r"\*\*", "\0")        # park ** so the next replace does not touch it
    regex = regex.replace(r"\*", "[^/]*")       # * = any characters except a slash
    regex = regex.replace("\0", ".*")           # ** = anything, slashes included
    return re.fullmatch(regex, path.strip("/")) is not None


def load_config(root: str) -> Dict[str, Any]:
    """The `terraform:` block of common.yaml, with defaults for whatever is missing."""
    config: Dict[str, Any] = {}
    for key, default in CONFIG_DEFAULTS.items():
        # Copy lists and dicts so changing one Repo's config never changes the defaults.
        config[key] = list(default) if isinstance(default, list) else dict(default) if isinstance(default, dict) else default

    path = os.path.join(root, "common.yaml")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            block = (yaml.safe_load(handle) or {}).get("terraform") or {}
        for key in CONFIG_DEFAULTS:
            if block.get(key) is not None:
                config[key] = block[key]
    return config


def _dir(path: str) -> str:
    """Folder of a path; `.` stands for the repository root."""
    return os.path.dirname(path) or "."


class Repo:
    """A read-only view of the repository: its .tf files and blocks, plus discovery of root configurations, modules
    and what a change affects. Everything is computed on first use and then cached."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.cfg = load_config(self.root)
        self.protected_environments: List[str] = []   # environments where destroying stateful resources is CRITICAL (set from PLAN-001)
        self.protect_all = False                      # a review of a pull request into the production branch protects every root
        self._blocks: Dict[str, List[Block]] = {}     # cache: file -> its parsed blocks
        self._text: Dict[str, str] = {}               # cache: file -> its contents
        self.tf_files = self._discover()              # every .tf file, relative to the repository root
        self._calls: Optional[Dict[str, Set[str]]] = None
        self._roots: Optional[List[str]] = None
        self._modules: Optional[List[str]] = None

    # ------------------------------------------------------------------------------------------------------------
    # Reading files
    # ------------------------------------------------------------------------------------------------------------
    def _discover(self) -> List[str]:
        """Every .tf file below the root, skipping tool and cache folders."""
        found = []
        for folder, subfolders, filenames in os.walk(self.root):
            subfolders[:] = sorted(name for name in subfolders if name not in EXCLUDED_DIRS)   # do not descend into excluded folders
            for filename in sorted(filenames):
                if filename.endswith(".tf"):
                    found.append(os.path.relpath(os.path.join(folder, filename), self.root))
        return found

    def text(self, path: str) -> str:
        """Contents of a file (cached)."""
        if path not in self._text:
            with open(os.path.join(self.root, path), encoding="utf-8", errors="replace") as handle:
                self._text[path] = handle.read()
        return self._text[path]

    def blocks(self, path: str) -> List[Block]:
        """Parsed blocks of one .tf file (cached)."""
        if path not in self._blocks:
            self._blocks[path] = parse(self.text(path), path)
        return self._blocks[path]

    def all_blocks(self, kind: Optional[str] = None) -> List[Block]:
        """Blocks of every .tf file, optionally only one kind ("resource", "module", "variable"...)."""
        found = []
        for path in self.tf_files:
            for block in self.blocks(path):
                if kind is None or block.kind == kind:
                    found.append(block)
        return found

    def files_in(self, folder: str) -> List[str]:
        """The .tf files directly in a folder (not in its subfolders)."""
        return [path for path in self.tf_files if _dir(path) == folder]

    def exists(self, path: str) -> bool:
        """Whether a path exists in the repository."""
        return os.path.exists(os.path.join(self.root, path))

    def listdir(self, folder: str) -> List[str]:
        """Sorted names in a folder; empty when it does not exist."""
        full_path = os.path.join(self.root, folder)
        return sorted(os.listdir(full_path)) if os.path.isdir(full_path) else []

    def line_count(self, path: str) -> Optional[int]:
        """Number of lines of a file, or None when it cannot be read."""
        try:
            return self.text(path).count("\n") + 1
        except OSError:
            return None

    # ------------------------------------------------------------------------------------------------------------
    # The module-call graph, roots and modules
    # ------------------------------------------------------------------------------------------------------------
    def dirs(self) -> List[str]:
        """Every folder that directly contains .tf files."""
        return sorted({_dir(path) for path in self.tf_files})

    def local_calls(self) -> Dict[str, Set[str]]:
        """The module-call graph: folder -> the folders it calls as modules.

        Only local calls count, i.e. a `source` that is a relative path (`./x`, `../../modules/vpc`). Registry or git
        sources are not folders of this repository, so they are not part of the graph."""
        if self._calls is None:
            known_folders = set(self.dirs())
            calls: Dict[str, Set[str]] = {folder: set() for folder in known_folders}
            for path in self.tf_files:
                for block in self.blocks(path):
                    if block.kind != "module":
                        continue
                    source = block.attrs.get("source", "").strip().strip('"')
                    if not source.startswith(("./", "../")):
                        continue
                    # `source` is relative to the file that declares the module call.
                    target = os.path.normpath(os.path.join(_dir(path), source)).replace(os.sep, "/")
                    if target in known_folders:
                        calls[_dir(path)].add(target)
            self._calls = calls
        return self._calls

    def _called_folders(self) -> Set[str]:
        """Every folder that some other folder calls as a module."""
        called: Set[str] = set()
        for targets in self.local_calls().values():
            called |= targets
        return called

    def _under_module_base(self, folder: str) -> bool:
        """Whether a folder is inside one of the configured modules folders (`terraform.modules`)."""
        for base in self.cfg["modules"]:
            base = base.strip("/")
            if folder == base or folder.startswith(base + "/"):
                return True
        return False

    def roots(self) -> List[str]:
        """The root configurations.

        If `terraform.roots` is set, the folders matching those patterns. Otherwise a folder is a root when
          - nobody calls it as a module,
          - it is not inside a modules folder, and
          - it has a provider or a backend, or resources or modules of its own."""
        if self._roots is None:
            patterns = self.cfg["roots"]
            if patterns:
                found = [folder for folder in self.dirs() if any(glob_match(pattern, folder) for pattern in patterns)]
            else:
                called = self._called_folders()
                found = []
                for folder in self.dirs():
                    if folder in called or self._under_module_base(folder):
                        continue
                    files = self.files_in(folder)
                    all_text = "\n".join(self.text(path) for path in files)
                    has_resources_or_modules = any(block.kind in ("module", "resource") for path in files for block in self.blocks(path))
                    if _PROVIDER.search(all_text) or _BACKEND.search(all_text) or has_resources_or_modules:
                        found.append(folder)
            self._roots = sorted(found)
        return self._roots

    def module_dirs(self) -> List[str]:
        """The shared modules: folders inside a modules folder, plus any folder that is called as a module. A root is never
        a module."""
        if self._modules is None:
            in_modules_folder = {folder for folder in self.dirs() if self._under_module_base(folder)}
            modules = in_modules_folder | self._called_folders()
            self._modules = sorted(modules - set(self.roots()))
        return self._modules

    def is_module_dir(self, folder: str) -> bool:
        """Whether a folder is a shared module."""
        return folder in set(self.module_dirs())

    def module_relpath(self, folder: str) -> str:
        """The path of a module below its modules folder: `modules/eks/cluster` -> `eks/cluster`."""
        for base in self.cfg["modules"]:
            base = base.strip("/")
            if folder.startswith(base + "/"):
                return folder[len(base) + 1:]
        return folder

    # ------------------------------------------------------------------------------------------------------------
    # Environments (terraform.environments): each one has a branch and the roots that belong to it
    # ------------------------------------------------------------------------------------------------------------
    def environment_of(self, root: str) -> Optional[str]:
        """The name of the environment a root belongs to; None if it belongs to none."""
        for name, environment in (self.cfg["environments"] or {}).items():
            if any(glob_match(pattern, root) for pattern in (environment or {}).get("roots") or []):
                return str(name)
        return None

    def branch_of_environment(self, name: str) -> Optional[str]:
        """The branch that deploys an environment."""
        branch = ((self.cfg["environments"] or {}).get(name) or {}).get("branch")
        return str(branch) if branch else None

    def roots_of_branch(self, branch: str) -> Optional[List[str]]:
        """The root patterns a branch may plan, review and apply (those of the environments that name it); None if no environment does."""
        environments = [env for env in (self.cfg["environments"] or {}).values() if (env or {}).get("branch") == branch]
        if not environments:
            return None
        return [pattern for env in environments for pattern in env.get("roots") or []]

    def is_protected(self, root: str) -> bool:
        """Whether destroying stateful resources in this root is CRITICAL: it belongs to a protected environment (PLAN-001), or the
        review is of a pull request into the production branch, where every root is protected."""
        environment = self.environment_of(root)
        return self.protect_all or (environment is not None and environment in self.protected_environments)

    # ------------------------------------------------------------------------------------------------------------
    # What a change affects
    # ------------------------------------------------------------------------------------------------------------
    def closure(self, folder: str) -> Set[str]:
        """The folder itself plus every module it uses, directly or through other modules.

        For a root this is "everything whose code ends up in this root's plan"."""
        reached = {folder}
        to_visit = [folder]
        calls = self.local_calls()
        while to_visit:
            for called in calls.get(to_visit.pop(), ()):
                if called not in reached:
                    reached.add(called)
                    to_visit.append(called)
        return reached

    def shared_files(self, folder: str) -> Set[str]:
        """Files outside a folder that its code reads, such as `yamldecode(file("${path.module}/../../common.yaml"))`.

        Files inside the folder itself are not "shared": they are already part of it."""
        shared: Set[str] = set()
        for path in self.files_in(folder):
            for reference in _FILE_REF.finditer(self.text(path)):
                relative = reference.group(1) or reference.group(2)
                target = os.path.normpath(os.path.join(folder, relative)).replace(os.sep, "/")
                outside_repository = target.startswith("..")
                if not outside_repository and _dir(target) != folder:
                    shared.add(target)
        return shared

    def affected(self, changed_paths: List[str]) -> List[Dict[str, Any]]:
        """The roots a change touches, each as {"root": folder, "reasons": [why...]}.

        A root is affected when a changed file is
          - the Terraform version file (affects every root),
          - a shared file the root (or a module it uses) reads,
          - inside the root's own folder, or
          - inside a module the root uses.
        Roots nothing touched are not returned, so nothing is run for them."""
        changed = [path for path in changed_paths if not path.endswith(_IGNORED_SUFFIXES)]
        affected = []
        for root in self.roots():
            used_folders = self.closure(root)
            shared = {path for folder in used_folders for path in self.shared_files(folder)}

            reasons = set()
            for path in changed:
                folder = _dir(path)
                inside_root = folder == root or (root != "." and folder.startswith(root + "/"))
                if os.path.basename(path) in _GLOBAL_FILES:
                    reasons.add("{} changed (shared by every configuration)".format(path))
                elif path in shared:
                    reasons.add("shared file {} changed".format(path))
                elif inside_root:
                    reasons.add("{} changed".format(path))
                elif folder in used_folders:
                    reasons.add("module {} changed ({})".format(folder, os.path.basename(path)))
            if reasons:
                affected.append({"root": root, "reasons": sorted(reasons)})
        return affected

    def _owning_module(self, path: str, modules: Set[str]) -> Optional[str]:
        """The module a file belongs to: the closest folder above it that is a module, or None."""
        folder = _dir(path)
        while True:
            if folder in modules:
                return folder
            if folder in (".", ""):
                return None
            folder = _dir(folder)

    def affected_modules(self, changed_paths: List[str]) -> List[str]:
        """The modules a change touches: edited themselves, using an edited module (directly or through others), reading
        an edited shared file, or all of them when the Terraform version changed."""
        modules = set(self.module_dirs())
        changed = [path for path in changed_paths if not path.endswith(_IGNORED_SUFFIXES)]
        if any(os.path.basename(path) in _GLOBAL_FILES for path in changed):
            return sorted(modules)

        # The modules whose own files were edited.
        edited_modules = set()
        for path in changed:
            owner = self._owning_module(path, modules)
            if owner:
                edited_modules.add(owner)

        edited_files = set(changed)
        affected = []
        for module in modules:
            used_folders = self.closure(module)
            uses_edited_module = bool(used_folders & edited_modules)
            reads_edited_file = any(path in edited_files for folder in used_folders for path in self.shared_files(folder))
            if uses_edited_module or reads_edited_file:
                affected.append(module)
        return sorted(affected)
