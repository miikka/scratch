#!/usr/bin/env python3
"""Generate a DotSlash file from a GitHub release.

Usage:
    create_dotslash.py <repo> <tag> <name> [options]

Example:
    create_dotslash.py Pagefind/pagefind v1.5.2 pagefind

The script lists release assets via `gh`, filters those whose names start
with `<name>-`, maps Rust-style target triples to DotSlash platform keys,
and downloads one Unix + one Windows archive into a tempdir to locate the
binary inside. The SHA-256 digests reported by the GitHub API are used
directly, so the script does not re-hash anything.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

PLATFORM_PATTERNS = [
    (re.compile(r"aarch64-apple-darwin"), "macos-aarch64"),
    (re.compile(r"x86_64-apple-darwin"), "macos-x86_64"),
    (re.compile(r"aarch64-unknown-linux"), "linux-aarch64"),
    (re.compile(r"x86_64-unknown-linux"), "linux-x86_64"),
    (re.compile(r"aarch64-pc-windows"), "windows-aarch64"),
    (re.compile(r"x86_64-pc-windows"), "windows-x86_64"),
]

FORMAT_EXTENSIONS = [
    (".tar.gz", "tar.gz"),
    (".tgz", "tar.gz"),
    (".tar.xz", "tar.xz"),
    (".tar.bz2", "tar.bz2"),
    (".tar.zst", "tar.zst"),
    (".tar", "tar"),
    (".zip", "zip"),
]


def detect_platform(name: str) -> str | None:
    for pattern, platform in PLATFORM_PATTERNS:
        if pattern.search(name):
            return platform
    return None


def detect_format(name: str) -> str | None:
    for ext, fmt in FORMAT_EXTENSIONS:
        if name.endswith(ext):
            return fmt
    return None


def parse_digest(digest: str) -> tuple[str, str]:
    if ":" not in digest:
        raise ValueError(f"unexpected digest format: {digest!r}")
    algo, hex_value = digest.split(":", 1)
    if algo not in ("sha256", "blake3"):
        raise ValueError(f"unsupported hash algorithm: {algo!r}")
    return algo, hex_value


def fetch_release(repo: str, tag: str) -> dict:
    result = subprocess.run(
        [
            "gh", "release", "view", tag,
            "--repo", repo,
            "--json", "assets,tagName",
        ],
        check=True, capture_output=True, text=True,
    )
    return json.loads(result.stdout)


def download_asset(repo: str, tag: str, asset_name: str, dest_dir: Path) -> Path:
    subprocess.run(
        [
            "gh", "release", "download", tag,
            "--repo", repo,
            "--pattern", asset_name,
            "--dir", str(dest_dir),
            "--clobber",
        ],
        check=True,
    )
    return dest_dir / asset_name


def extract(archive: Path, dest: Path) -> None:
    fmt = detect_format(archive.name)
    if fmt is None:
        raise ValueError(f"unknown archive format: {archive.name}")
    if fmt.startswith("tar"):
        with tarfile.open(archive) as tf:
            try:
                tf.extractall(dest, filter="data")
            except TypeError:
                tf.extractall(dest)
    elif fmt == "zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    else:
        raise ValueError(f"format {fmt!r} cannot be auto-extracted; pass --path")


def find_binary(root: Path, binary_name: str, is_windows: bool) -> str:
    target = binary_name + ".exe" if is_windows else binary_name
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name == target:
            return path.relative_to(root).as_posix()
    raise RuntimeError(
        f"could not find {target!r} inside extracted archive at {root}"
    )


def resolve_paths(
    repo: str,
    tag: str,
    binary_name: str,
    platforms: dict[str, dict],
    override_unix: str | None,
    override_windows: str | None,
) -> tuple[str | None, str | None]:
    unix_path = override_unix
    windows_path = override_windows
    if unix_path is not None and windows_path is not None:
        return unix_path, windows_path

    unix_asset = next(
        (a for p, a in platforms.items() if not p.startswith("windows")), None
    )
    windows_asset = next(
        (a for p, a in platforms.items() if p.startswith("windows")), None
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        if unix_path is None and unix_asset is not None:
            archive = download_asset(repo, tag, unix_asset["name"], tmp_path)
            extract_dir = tmp_path / "unix"
            extract_dir.mkdir()
            extract(archive, extract_dir)
            unix_path = find_binary(extract_dir, binary_name, is_windows=False)
        if windows_path is None and windows_asset is not None:
            archive = download_asset(repo, tag, windows_asset["name"], tmp_path)
            extract_dir = tmp_path / "windows"
            extract_dir.mkdir()
            extract(archive, extract_dir)
            windows_path = find_binary(extract_dir, binary_name, is_windows=True)

    if unix_path is None and windows_path is not None:
        unix_path = (
            windows_path[:-4] if windows_path.endswith(".exe") else windows_path
        )
    if windows_path is None and unix_path is not None:
        windows_path = unix_path + ".exe"
    return unix_path, windows_path


def main() -> int:
    p = argparse.ArgumentParser(
        description="Generate a DotSlash file from a GitHub release."
    )
    p.add_argument("repo", help="GitHub repo, e.g. owner/name")
    p.add_argument("tag", help="release tag, e.g. v1.5.2")
    p.add_argument(
        "name",
        help="binary name; also used to filter assets (matches '<name>-...')",
    )
    p.add_argument(
        "--path",
        help="binary path inside the Unix archive (auto-detected if omitted)",
    )
    p.add_argument(
        "--windows-path",
        help="binary path inside the Windows archive (auto-detected if omitted)",
    )
    p.add_argument("-o", "--output", help="output file (default: ./<name>)")
    args = p.parse_args()

    release = fetch_release(args.repo, args.tag)
    asset_prefix = f"{args.name}-"

    platforms: dict[str, dict] = {}
    for asset in release["assets"]:
        if not asset["name"].startswith(asset_prefix):
            continue
        if detect_format(asset["name"]) is None:
            continue
        platform = detect_platform(asset["name"])
        if platform is None:
            continue
        if platform in platforms:
            print(
                f"warning: multiple assets for {platform}; keeping "
                f"{platforms[platform]['name']!r}, ignoring {asset['name']!r}",
                file=sys.stderr,
            )
            continue
        platforms[platform] = asset

    if not platforms:
        print(
            f"no archive assets starting with {asset_prefix!r} found in "
            f"{args.repo}@{args.tag}",
            file=sys.stderr,
        )
        return 1

    unix_path, windows_path = resolve_paths(
        args.repo, args.tag, args.name, platforms, args.path, args.windows_path
    )

    output_doc: dict = {"name": args.name, "platforms": {}}
    for platform in sorted(platforms):
        asset = platforms[platform]
        algo, hex_value = parse_digest(asset["digest"])
        output_doc["platforms"][platform] = {
            "size": asset["size"],
            "hash": algo,
            "digest": hex_value,
            "format": detect_format(asset["name"]),
            "path": windows_path if platform.startswith("windows") else unix_path,
            "providers": [{"url": asset["url"]}],
        }

    output_path = Path(args.output or args.name)
    body = "#!/usr/bin/env dotslash\n" + json.dumps(output_doc, indent=2) + "\n"
    output_path.write_text(body)
    output_path.chmod(0o755)
    print(f"wrote {output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
