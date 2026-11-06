#!/usr/bin/env python3
"""Compose portable AGENTS.md and project-local Agent Skills from a pinned source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

try:
    import yaml
except ImportError as error:  # pragma: no cover - exercised in a clean install
    raise SystemExit(
        "PyYAML is required; install it with `python3 -m pip install -r "
        "requirements-toolkit.txt`."
    ) from error


STATE_PATH = ".agent-toolkit-state.json"
MANIFEST_PATH = "agent-toolkit.yml"
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
SKILL_CONFIG_DEFAULTS = {
    "git-branch": {"base_branch": "main"},
    "git-commit": {"format": "emoji-description"},
    "git-pr": {"base_branch": "main"},
}
SKILL_CONFIG_VALUES = {
    ("git-commit", "format"): {"emoji-description", "emoji-type-description"},
}


class ToolkitError(Exception):
    """An invalid manifest or unsafe synchronization state."""


class UniqueKeyLoader(yaml.SafeLoader):
    """YAML loader that rejects duplicate mapping keys instead of hiding them."""


def _construct_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ToolkitError("duplicate YAML key: {!r}".format(key))
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_yaml(path):
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError, ToolkitError) as error:
        raise ToolkitError("cannot read {}: {}".format(path, error)) from error
    if not isinstance(value, dict):
        raise ToolkitError("{} must contain a YAML mapping".format(path))
    return value


def safe_relative_path(value, description):
    if not isinstance(value, str) or not value:
        raise ToolkitError("{} must be a non-empty relative path".format(description))
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ToolkitError("{} escapes its allowed directory: {!r}".format(description, value))
    return path


def confined_path(root, value, description, allow_dot=False):
    if allow_dot and value == ".":
        return root
    relative = safe_relative_path(value, description)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ToolkitError("{} must not traverse a symlink: {}".format(description, current))
    resolved_root = root.resolve()
    resolved = current.resolve(strict=False)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ToolkitError("{} escapes its allowed directory: {!r}".format(description, value))
    return current


def validate_repository_url(repository):
    if not isinstance(repository, str) or not repository:
        raise ToolkitError("source.repository must be a non-empty URL")
    if "\n" in repository or "\r" in repository:
        raise ToolkitError("source.repository contains an invalid newline")
    parsed = urlsplit(repository)
    if parsed.scheme in ("https", "ssh", "file"):
        if parsed.scheme != "file" and not parsed.netloc:
            raise ToolkitError("source.repository must include a host")
        if parsed.password or (parsed.username and not (parsed.scheme == "ssh" and parsed.username == "git")):
            raise ToolkitError("source.repository must not embed credentials")
        return
    # SCP-style Git SSH URLs (git@host:owner/repository.git) are supported.
    if re.fullmatch(r"[^/@:]+@[^/:]+:.+", repository):
        return
    raise ToolkitError("source.repository must be an HTTPS, SSH, or file Git URL")


def git_output(arguments, cwd=None):
    try:
        return subprocess.check_output(
            ["git"] + list(arguments), cwd=str(cwd) if cwd else None,
            stderr=subprocess.PIPE, text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        raise ToolkitError("git command failed: {}".format(detail.strip())) from error


def validate_toolkit_checkout(path, revision):
    if not path.is_dir():
        raise ToolkitError("toolkit checkout does not exist: {}".format(path))
    actual = git_output(["rev-parse", "--verify", "HEAD"], cwd=path)
    if actual != revision:
        raise ToolkitError(
            "toolkit revision mismatch: manifest pins {}, checkout is {}".format(
                revision, actual
            )
        )
    if git_output(["status", "--porcelain", "--untracked-files=all"], cwd=path):
        raise ToolkitError("toolkit checkout has local changes; use a clean pinned revision")
    return path.resolve()


def resolve_toolkit(source, supplied_directory):
    repository = source.get("repository")
    validate_repository_url(repository)
    revision = source.get("revision")
    if not isinstance(revision, str) or not COMMIT_RE.fullmatch(revision):
        raise ToolkitError("source.revision must be a full 40-character commit SHA")
    if supplied_directory:
        return validate_toolkit_checkout(Path(supplied_directory).resolve(), revision), None

    script_checkout = Path(__file__).resolve().parent.parent
    try:
        current_revision = git_output(["rev-parse", "--verify", "HEAD"], cwd=script_checkout)
    except ToolkitError:
        current_revision = None
    if current_revision == revision:
        return validate_toolkit_checkout(script_checkout, revision), None

    temporary_directory = tempfile.TemporaryDirectory(prefix="agent-toolkit-")
    checkout = Path(temporary_directory.name) / "toolkit"
    try:
        subprocess.run(
            ["git", "clone", "--quiet", "--no-checkout", repository, str(checkout)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            ["git", "-C", str(checkout), "checkout", "--quiet", "--detach", revision],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        temporary_directory.cleanup()
        detail = getattr(error, "stderr", "") or str(error)
        raise ToolkitError("cannot obtain pinned toolkit revision: {}".format(detail.strip())) from error
    return checkout.resolve(), temporary_directory


def parse_skill(skill_file):
    try:
        content = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ToolkitError("cannot read skill {}: {}".format(skill_file, error)) from error
    if not content.startswith("---\n"):
        raise ToolkitError("{} is missing YAML frontmatter".format(skill_file))
    end = content.find("\n---\n", 4)
    if end < 0:
        raise ToolkitError("{} has unterminated YAML frontmatter".format(skill_file))
    try:
        metadata = yaml.load(content[4:end], Loader=UniqueKeyLoader)
    except (yaml.YAMLError, ToolkitError) as error:
        raise ToolkitError("invalid frontmatter in {}: {}".format(skill_file, error)) from error
    if not isinstance(metadata, dict):
        raise ToolkitError("{} frontmatter must be a YAML mapping".format(skill_file))
    name = metadata.get("name")
    description = metadata.get("description")
    if not isinstance(name, str) or not SKILL_NAME_RE.fullmatch(name):
        raise ToolkitError("{} has an invalid skill name".format(skill_file))
    if not isinstance(description, str) or not description.strip():
        raise ToolkitError("{} must declare a non-empty description".format(skill_file))
    validate_skill_references(skill_file.parent, content)
    return name


def validate_skill_references(skill_root, content):
    for match in MARKDOWN_LINK_RE.finditer(content):
        target = match.group(1).strip().split(" ", 1)[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:", "data:")):
            continue
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        relative = safe_relative_path(target_path, "skill resource reference")
        candidate = skill_root.joinpath(*relative.parts)
        if candidate.is_symlink():
            raise ToolkitError("skill resource reference traverses a symlink: {}".format(target))
        if not candidate.is_file() and not candidate.is_dir():
            raise ToolkitError("missing skill resource reference: {}".format(target))


def validate_instruction_references(repository_root, content):
    for match in MARKDOWN_LINK_RE.finditer(content):
        target = match.group(1).strip().split(" ", 1)[0].strip("<>")
        if not target or target.startswith(("#", "http://", "https://", "mailto:", "data:")):
            continue
        target_path = target.split("#", 1)[0].split("?", 1)[0]
        if not target_path:
            continue
        relative = PurePosixPath(target_path)
        if relative.is_absolute():
            raise ToolkitError("instruction reference must be repository-relative: {}".format(target))
        candidate = repository_root.joinpath(*relative.parts)
        if candidate.is_symlink():
            raise ToolkitError("instruction reference traverses a symlink: {}".format(target))
        resolved_root = repository_root.resolve()
        resolved = candidate.resolve(strict=False)
        if resolved != resolved_root and resolved_root not in resolved.parents:
            raise ToolkitError("instruction reference escapes the consumer: {}".format(target))
        if not candidate.is_file() and not candidate.is_dir():
            raise ToolkitError("missing instruction reference: {}".format(target))


def validate_skill_config(skill_config):
    for name, settings in skill_config.items():
        if not SKILL_NAME_RE.fullmatch(name):
            raise ToolkitError("invalid skill_config name: {!r}".format(name))
        defaults = SKILL_CONFIG_DEFAULTS.get(name)
        if defaults is None:
            raise ToolkitError("skill_config has no documented settings for {!r}".format(name))
        allowed_keys = set(defaults) | {"reason"}
        if not isinstance(settings, dict) or set(settings) - allowed_keys:
            raise ToolkitError(
                "skill_config.{} supports only {} and reason".format(
                    name, ", ".join(sorted(defaults))
                )
            )
        configured_values = set(settings) - {"reason"}
        if not configured_values:
            raise ToolkitError("skill_config.{} must set a documented value".format(name))
        deviations = []
        for key in configured_values:
            value = settings[key]
            if not isinstance(value, str) or not value.strip():
                raise ToolkitError(
                    "skill_config.{}.{} must be a non-empty string".format(name, key)
                )
            choices = SKILL_CONFIG_VALUES.get((name, key))
            if choices and value not in choices:
                raise ToolkitError(
                    "skill_config.{}.{} must be one of {}".format(
                        name, key, ", ".join(sorted(choices))
                    )
                )
            if value != defaults[key]:
                deviations.append(key)
        reason = settings.get("reason")
        if deviations and (not isinstance(reason, str) or not reason.strip()):
            raise ToolkitError(
                "non-default skill_config.{} values require a non-empty reason".format(name)
            )
        if reason is not None and (not isinstance(reason, str) or not reason.strip()):
            raise ToolkitError("skill_config.{}.reason must be non-empty when set".format(name))


def discover_skills(root):
    discovered = {}
    for skill_file in sorted(root.glob("*/SKILL.md")):
        directory = skill_file.parent
        if directory.is_symlink() or skill_file.is_symlink():
            raise ToolkitError("skill source must not be a symlink: {}".format(directory))
        name = parse_skill(skill_file)
        if name in discovered:
            raise ToolkitError(
                "duplicate skill name {!r}: {} and {}".format(name, discovered[name], directory)
            )
        discovered[name] = directory
    return discovered


def load_manifest(repository_root):
    manifest_path = repository_root / MANIFEST_PATH
    manifest = load_yaml(manifest_path)
    allowed_keys = {
        "source", "local_instructions", "local_skills", "common_skills",
        "overrides", "skill_config",
    }
    unknown = set(manifest) - allowed_keys
    if unknown:
        raise ToolkitError("unknown manifest key(s): {}".format(", ".join(sorted(unknown))))
    source = manifest.get("source")
    if not isinstance(source, dict) or set(source) - {"repository", "revision", "skill_root"}:
        raise ToolkitError("source must declare repository, revision, and optional skill_root")
    local_instructions_value = manifest.get("local_instructions")
    local_skills_value = manifest.get("local_skills")
    common_skills = manifest.get("common_skills")
    override_specs = manifest.get("overrides", {})
    skill_config = manifest.get("skill_config", {})
    if not isinstance(common_skills, list) or any(not isinstance(item, str) for item in common_skills):
        raise ToolkitError("common_skills must be a list of skill names")
    if len(common_skills) != len(set(common_skills)):
        raise ToolkitError("common_skills contains duplicate names")
    for name in common_skills:
        if not SKILL_NAME_RE.fullmatch(name):
            raise ToolkitError("invalid common skill name: {!r}".format(name))
    if not isinstance(override_specs, dict):
        raise ToolkitError("overrides must map common skill names to local replacement details")
    if set(override_specs) - set(common_skills):
        raise ToolkitError("overrides may only replace skills listed in common_skills")
    if not isinstance(skill_config, dict):
        raise ToolkitError("skill_config must map skill names to documented local settings")
    if set(skill_config) - set(common_skills):
        raise ToolkitError("skill_config may only configure selected common skills")
    overlapping_settings = set(skill_config).intersection(override_specs)
    if overlapping_settings:
        raise ToolkitError(
            "a fully overridden skill cannot also have skill_config: {}".format(
                ", ".join(sorted(overlapping_settings))
            )
        )

    local_instructions = confined_path(
        repository_root, local_instructions_value, "local_instructions"
    )
    local_skills = confined_path(repository_root, local_skills_value, "local_skills")
    if not local_instructions.is_file():
        raise ToolkitError("local instructions file does not exist: {}".format(local_instructions))
    if not local_skills.is_dir():
        raise ToolkitError("local skills directory does not exist: {}".format(local_skills))

    overrides = {}
    local_skills_root = local_skills.resolve()
    for name, specification in override_specs.items():
        if not SKILL_NAME_RE.fullmatch(name):
            raise ToolkitError("invalid override skill name: {!r}".format(name))
        if not isinstance(specification, dict) or set(specification) != {"path", "reason"}:
            raise ToolkitError(
                "override {!r} must declare exactly path and reason".format(name)
            )
        reason = specification.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ToolkitError("override {!r} requires a non-empty reason".format(name))
        override_path = confined_path(
            repository_root,
            specification.get("path"),
            "overrides.{}.path".format(name),
        )
        try:
            override_path.resolve().relative_to(local_skills_root)
        except ValueError as error:
            raise ToolkitError(
                "override {!r} must be inside local_skills".format(name)
            ) from error
        overrides[name] = override_path

    validate_skill_config(skill_config)

    skill_root_value = source.get("skill_root", ".")
    skill_root = confined_path(
        Path("/"), skill_root_value, "source.skill_root", allow_dot=True
    )
    # Validate the syntax here; resolve against the actual source after checkout.
    return manifest, source, local_instructions, local_skills, common_skills, overrides, skill_root_value


def read_skill_tree(skill_directory, destination_prefix):
    files = {}
    for current_root, directories, filenames in os.walk(skill_directory, followlinks=False):
        current = Path(current_root)
        for directory in list(directories):
            candidate = current / directory
            if candidate.is_symlink():
                raise ToolkitError("skill resources must not contain symlinks: {}".format(candidate))
        for filename in filenames:
            source_file = current / filename
            if source_file.is_symlink() or not source_file.is_file():
                raise ToolkitError("skill resources must be regular files: {}".format(source_file))
            relative = source_file.relative_to(skill_directory).as_posix()
            target = PurePosixPath(destination_prefix, relative).as_posix()
            files[target] = source_file.read_bytes()
    return files


def compose_files(repository_root, toolkit_root, loaded_manifest):
    _, source, local_instructions, local_skills, common_skills, overrides, skill_root_value = loaded_manifest
    toolkit_skill_root = confined_path(
        toolkit_root, skill_root_value, "source.skill_root", allow_dot=True
    )
    common = discover_skills(toolkit_skill_root)
    local = discover_skills(local_skills)
    missing = set(common_skills) - set(common)
    if missing:
        raise ToolkitError("unknown common skill(s): {}".format(", ".join(sorted(missing))))
    unresolved = set(common).intersection(local) - set(overrides)
    if unresolved:
        raise ToolkitError(
            "unresolved duplicate skill name(s): {}".format(", ".join(sorted(unresolved)))
        )
    unknown_overrides = set(overrides) - set(local)
    if unknown_overrides:
        raise ToolkitError(
            "override skill(s) are not present in local_skills: {}".format(
                ", ".join(sorted(unknown_overrides))
            )
        )
    for name, override_path in overrides.items():
        if override_path.resolve() != local[name].resolve():
            raise ToolkitError(
                "override {!r} path does not contain the skill with matching name".format(name)
            )
    effective = {}
    for name in common_skills:
        effective[name] = local[name] if name in overrides else common[name]
    for name, directory in local.items():
        effective.setdefault(name, directory)
    if len(effective) != len(set(effective)):
        raise ToolkitError("more than one effective skill has the same name")

    base_file = toolkit_root / "instructions" / "base.md"
    if not base_file.is_file():
        raise ToolkitError("toolkit is missing instructions/base.md")
    base = base_file.read_text(encoding="utf-8").rstrip()
    local_text = local_instructions.read_text(encoding="utf-8").rstrip()
    validate_instruction_references(repository_root, local_text)
    generated_instructions = (
        "<!-- Generated by scripts/sync_agents.py. Edit the pinned toolkit source or "
        "the manifest's local_instructions file. -->\n\n"
        + base
        + "\n\n---\n\n"
        + local_text
        + "\n"
    ).encode("utf-8")
    files = {"AGENTS.md": generated_instructions}
    for name, directory in sorted(effective.items()):
        files.update(read_skill_tree(directory, ".agents/skills/{}".format(name)))
    return files


def read_state(repository_root):
    state_path = repository_root / STATE_PATH
    if not state_path.exists():
        return None
    if state_path.is_symlink() or not state_path.is_file():
        raise ToolkitError("state file is not a regular file: {}".format(state_path))
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        raise ToolkitError("cannot read state file: {}".format(error)) from error
    if not isinstance(state, dict) or not isinstance(state.get("files"), dict):
        raise ToolkitError("state file has an invalid structure")
    for path, digest in state["files"].items():
        relative = safe_relative_path(path, "managed state path")
        if relative.as_posix() != "AGENTS.md" and not relative.as_posix().startswith(".agents/skills/"):
            raise ToolkitError("state file contains an unauthorized managed path: {}".format(path))
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ToolkitError("state file contains an invalid hash for {}".format(path))
    return state


def target_path(repository_root, relative_path):
    relative = safe_relative_path(relative_path, "generated path")
    if relative.as_posix() != "AGENTS.md" and not relative.as_posix().startswith(".agents/skills/"):
        raise ToolkitError("generated path is outside managed directories: {}".format(relative_path))
    current = repository_root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ToolkitError("generated path traverses a symlink: {}".format(current))
    resolved_root = repository_root.resolve()
    resolved = current.resolve(strict=False)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ToolkitError("generated path escapes repository: {}".format(relative_path))
    return current


def digest(content):
    return hashlib.sha256(content).hexdigest()


def validate_existing_state(repository_root, state):
    if state is None:
        return
    for relative, previous_hash in state["files"].items():
        path = target_path(repository_root, relative)
        if path.is_symlink() or not path.is_file():
            raise ToolkitError("managed file was removed or replaced: {}".format(relative))
        if digest(path.read_bytes()) != previous_hash:
            raise ToolkitError(
                "managed file was edited manually; restore it or save the change in its source: {}".format(
                    relative
                )
            )


def collect_unmanaged_files(directory, known_paths):
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise ToolkitError("managed skill path is not a directory: {}".format(directory))
    untracked = []
    for current_root, dirs, filenames in os.walk(directory, followlinks=False):
        current = Path(current_root)
        for dirname in dirs:
            if (current / dirname).is_symlink():
                raise ToolkitError("generated skill directory contains a symlink")
        for filename in filenames:
            path = current / filename
            relative = path.relative_to(directory.parent.parent.parent).as_posix()
            if path.is_symlink() or not path.is_file():
                raise ToolkitError("generated skill contains a non-regular file: {}".format(path))
            if relative not in known_paths:
                untracked.append(relative)
    return untracked


def plan_sync(repository_root, generated, state, adopt):
    previous = state["files"] if state else {}
    validate_existing_state(repository_root, state)
    expected_hashes = {path: digest(content) for path, content in generated.items()}
    old_paths = set(previous)
    new_paths = set(generated)

    for relative, content in generated.items():
        target = target_path(repository_root, relative)
        if target.exists() and relative not in previous:
            if target.is_dir():
                raise ToolkitError("generated file conflicts with a directory: {}".format(relative))
            if target.read_bytes() != content and not adopt:
                raise ToolkitError(
                    "unmanaged file conflicts with generated output; preserve it and use --adopt explicitly: {}".format(
                        relative
                    )
                )
        parent = target.parent
        while parent != repository_root and parent != parent.parent:
            if parent.exists() and not parent.is_dir():
                raise ToolkitError("generated parent path is not a directory: {}".format(parent))
            parent = parent.parent

    stale = old_paths - new_paths
    for relative in stale:
        target_path(repository_root, relative)

    old_skill_roots = {
        "/".join(path.split("/")[:3]) for path in old_paths if path.startswith(".agents/skills/")
    }
    new_skill_roots = {
        "/".join(path.split("/")[:3]) for path in new_paths if path.startswith(".agents/skills/")
    }
    for skill_root in old_skill_roots | new_skill_roots:
        root_path = target_path(repository_root, skill_root)
        old_tree_paths = {path for path in old_paths if path.startswith(skill_root + "/")}
        untracked = collect_unmanaged_files(root_path, old_tree_paths)
        collisions = [path for path in untracked if path in generated]
        if collisions and not adopt:
            raise ToolkitError("unmanaged file conflicts with a skill resource: {}".format(collisions[0]))

    return expected_hashes


def remove_empty_directories(directory, stop):
    current = directory
    while current != stop and current != current.parent:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def write_outputs(repository_root, generated, hashes, state, revision):
    previous_paths = set(state["files"]) if state else set()
    current_paths = set(generated)
    stale = sorted(previous_paths - current_paths, reverse=True)
    for relative in stale:
        path = target_path(repository_root, relative)
        if path.exists():
            path.unlink()
            if relative.startswith(".agents/skills/"):
                remove_empty_directories(path.parent, repository_root / ".agents" / "skills")

    for relative, content in sorted(generated.items()):
        target = target_path(repository_root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".agent-toolkit-", dir=str(target.parent))
        try:
            with os.fdopen(descriptor, "wb") as temporary_file:
                temporary_file.write(content)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, target)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    state_value = {"revision": revision, "files": hashes}
    state_path = repository_root / STATE_PATH
    descriptor, temporary_name = tempfile.mkstemp(prefix=".agent-toolkit-state-", dir=str(repository_root))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as state_file:
            json.dump(state_value, state_file, indent=2, sort_keys=True)
            state_file.write("\n")
            state_file.flush()
            os.fsync(state_file.fileno())
        os.replace(temporary_name, state_path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def check_outputs(repository_root, generated, hashes, state, revision):
    if state is None:
        raise ToolkitError("no generated-file state exists; run sync before --check")
    validate_existing_state(repository_root, state)
    if state.get("revision") != revision:
        raise ToolkitError("generated files use a different toolkit revision")
    if state["files"] != hashes:
        raise ToolkitError("generated-file manifest is out of date; run sync")
    differences = []
    for relative, content in generated.items():
        path = target_path(repository_root, relative)
        if not path.is_file() or path.read_bytes() != content:
            differences.append(relative)
    if set(state["files"]) != set(generated):
        differences.extend(sorted(set(state["files"]) - set(generated)))
    if differences:
        raise ToolkitError("generated files differ: {}".format(", ".join(sorted(set(differences)))))


def run(arguments):
    repository_root = Path(arguments.repo).resolve()
    if not repository_root.is_dir():
        raise ToolkitError("consumer repository does not exist: {}".format(repository_root))
    loaded_manifest = load_manifest(repository_root)
    _, source = loaded_manifest[:2]
    toolkit_root, temporary_directory = resolve_toolkit(source, arguments.toolkit_dir)
    try:
        generated = compose_files(repository_root, toolkit_root, loaded_manifest)
        state = read_state(repository_root)
        hashes = plan_sync(repository_root, generated, state, arguments.adopt)
        if arguments.check:
            check_outputs(repository_root, generated, hashes, state, source["revision"])
            print("agent-toolkit outputs are up to date")
            return 0
        write_outputs(repository_root, generated, hashes, state, source["revision"])
        print("synchronized {} managed files at {}".format(len(generated), source["revision"]))
        return 0
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".", help="consumer repository (default: current directory)")
    parser.add_argument("--toolkit-dir", help="local clean checkout of the pinned toolkit")
    parser.add_argument("--check", action="store_true", help="check generated files without modifying them")
    parser.add_argument(
        "--adopt",
        action="store_true",
        help="explicitly adopt/replace existing untracked generated targets on first sync",
    )
    arguments = parser.parse_args(argv)
    if arguments.check and arguments.adopt:
        parser.error("--check cannot be combined with --adopt")
    try:
        return run(arguments)
    except ToolkitError as error:
        print("sync_agents.py: error: {}".format(error), file=sys.stderr)
        return 2 if not arguments.check else 1


if __name__ == "__main__":
    sys.exit(main())
