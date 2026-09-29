#!/usr/bin/env python3
"""
duviz.py — a tiny disk-usage visualizer (like `dust` or `ncdu`, but yours).

WHAT IT DOES
------------
Given a directory, it shows you which subfolders/files are eating your
disk space, with a bar chart so the biggest offenders are visually obvious
at a glance — instead of scrolling through a wall of numbers.

Example output:

  $ python3 duviz.py ~/Downloads

  Disk usage for: /home/alif/Downloads (total: 4.2 GB)

  2.1 GB  [████████████████░░░░░░░░░░░░░░]  50.1%  arch-linux.iso
  1.3 GB  [██████████░░░░░░░░░░░░░░░░░░░░]  31.0%  old-projects/
  512 MB  [████░░░░░░░░░░░░░░░░░░░░░░░░░░]  12.2%  screenshots/
   98 MB  [█░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   2.3%  notes.pdf
  ... 14 more items (total: 190 MB, 4.4%)

HOW IT WORKS (high level)
--------------------------
1. For every item directly inside the target folder, figure out its total
   size. For a file, that's just its size on disk. For a folder, it's the
   sum of every file inside it, recursively.
2. Sort those items biggest-first.
3. Print the top N (default 15) with a proportional bar, and fold
   everything else into a single "... N more" summary line so tiny files
   don't spam your terminal.
4. Optionally (--depth > 1), do the same thing again *inside* the biggest
   folders, indented one level deeper — like `dust`'s tree view.

USAGE
-----
  python3 duviz.py                     # scan the current directory
  python3 duviz.py ~/Downloads         # scan a specific directory
  python3 duviz.py . --top 10          # show only the top 10 items per level
  python3 duviz.py . --depth 3         # recurse 3 levels deep instead of 1
  python3 duviz.py . --min-size 50M    # hide anything smaller than 50 MB
"""

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# COLOR / DISPLAY CONSTANTS
# ---------------------------------------------------------------------------

# Raw ANSI escape codes — no extra library needed (like `colorama`), since
# every modern Linux terminal (including CachyOS's) understands these directly.
RESET = "\033[0m"
COLOR_HIGH = "\033[91m"   # red    — this item eats a big share of its level
COLOR_MED = "\033[93m"    # yellow — moderate share
COLOR_LOW = "\033[92m"    # green  — small share
COLOR_DIR = "\033[94m"    # blue   — used for the trailing "/" on directories
COLOR_DIM = "\033[90m"    # gray   — the "... N more items" summary line


def size_color(fraction: float) -> str:
    """Pick a color based on how much of the current level this item takes up."""
    if fraction >= 0.40:
        return COLOR_HIGH
    elif fraction >= 0.15:
        return COLOR_MED
    return COLOR_LOW


def truncate_name(name: str, max_len: int) -> str:
    """Cut a filename down to max_len characters, adding '…' if it was cut.

    This is what stops a long PDF filename from wrapping onto a second
    terminal line and breaking the tidy column alignment.
    """
    if len(name) <= max_len:
        return name
    return name[: max_len - 1] + "…"


# ---------------------------------------------------------------------------
# SIZE CALCULATION
# ---------------------------------------------------------------------------

def dir_size(path: Path, size_cache: dict) -> int:
    """
    Recursively compute the total size (in bytes) of everything under `path`.

    Uses a plain dict (`size_cache`) to memoize results, so if the same
    folder gets asked about twice (e.g. once for its own bar, once as part
    of a parent's total) we don't re-walk the filesystem twice.

    Symlinks are skipped rather than followed — this avoids infinite loops
    (a symlink pointing at an ancestor folder) and avoids double-counting
    space that isn't really "inside" this folder.
    """
    if path in size_cache:
        return size_cache[path]

    total = 0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        total += dir_size(Path(entry.path), size_cache)
                    else:
                        total += entry.stat(follow_symlinks=False).st_size
                except (PermissionError, FileNotFoundError, OSError):
                    # Skip anything we can't read instead of crashing the
                    # whole scan over one bad file/folder.
                    continue
    except (PermissionError, FileNotFoundError, OSError):
        pass

    size_cache[path] = total
    return total


def entry_size(path: Path, size_cache: dict) -> int:
    """Size of a single file, or total recursive size if it's a directory."""
    try:
        if path.is_symlink():
            return 0
        if path.is_dir():
            return dir_size(path, size_cache)
        return path.stat().st_size
    except (PermissionError, FileNotFoundError, OSError):
        return 0


# ---------------------------------------------------------------------------
# FORMATTING HELPERS
# ---------------------------------------------------------------------------

def format_size(num_bytes: float) -> str:
    """Turn a byte count into a human-readable string, e.g. '512 MB'."""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if num_bytes < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(num_bytes)} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"  # unreachable in practice, keeps linters happy


def parse_size(size_str: str) -> int:
    """Parse a human size like '50M' or '1.5G' into a raw byte count.

    Used for --min-size. Accepts K, M, G, T (case-insensitive), defaults
    to bytes if no suffix is given.
    """
    size_str = size_str.strip().upper()
    multipliers = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    if size_str and size_str[-1] in multipliers:
        return int(float(size_str[:-1]) * multipliers[size_str[-1]])
    return int(size_str)


def draw_bar(fraction: float, width: int = 30, use_color: bool = True) -> str:
    """Build a text progress bar like '[████████░░░░░░]' for a 0.0-1.0 fraction.

    The filled portion is colored by size_color() when use_color is True;
    the empty portion always stays plain so the bar's shape reads clearly.
    """
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    filled_part = "█" * filled
    empty_part = "░" * (width - filled)
    if use_color:
        color = size_color(fraction)
        return f"[{color}{filled_part}{RESET}{empty_part}]"
    return f"[{filled_part}{empty_part}]"


# ---------------------------------------------------------------------------
# CORE DISPLAY LOGIC
# ---------------------------------------------------------------------------

def list_children(path: Path, size_cache: dict, min_size: int) -> list[tuple[Path, int]]:
    """
    Return [(child_path, size), ...] for everything directly inside `path`,
    sorted biggest first, skipping anything under `min_size` bytes.
    """
    children = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                try:
                    child_path = Path(entry.path)
                    size = entry_size(child_path, size_cache)
                    if size >= min_size:
                        children.append((child_path, size))
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, FileNotFoundError, OSError) as e:
        print(f"Warning: couldn't read {path}: {e}", file=sys.stderr)

    children.sort(key=lambda item: item[1], reverse=True)
    return children


def print_level(path: Path, size_cache: dict, top: int, min_size: int,
                 depth: int, max_depth: int, indent: str = "",
                 use_color: bool = True, name_width: int = 45) -> None:
    """
    Print one "level" of the tree: the top N children of `path`, each with
    a bar proportional to the total size of this level. If max_depth allows,
    recurse one level deeper into the biggest directories.

    name_width caps how long a filename can print before being truncated
    with '…' — this is what keeps long filenames (long PDF titles, etc.)
    from wrapping onto a second line and breaking column alignment.
    """
    children = list_children(path, size_cache, min_size)
    if not children:
        return

    level_total = sum(size for _, size in children)
    shown = children[:top]
    rest = children[top:]

    for child_path, size in shown:
        fraction = (size / level_total) if level_total else 0
        pct = fraction * 100
        is_dir = child_path.is_dir()
        raw_name = child_path.name + ("/" if is_dir else "")
        name = truncate_name(raw_name, name_width)

        if use_color and is_dir:
            name = f"{COLOR_DIR}{name}{RESET}"

        bar = draw_bar(fraction, use_color=use_color)
        print(f"{indent}{format_size(size):>9}  {bar}  {pct:5.1f}%  {name}")

        # Recurse into subdirectories if we haven't hit the depth limit yet.
        if is_dir and depth < max_depth:
            print_level(child_path, size_cache, top, min_size,
                        depth + 1, max_depth, indent + "    ",
                        use_color=use_color, name_width=name_width)

    if rest:
        rest_total = sum(size for _, size in rest)
        rest_pct = (rest_total / level_total * 100) if level_total else 0
        summary = (f"... {len(rest)} more items "
                   f"(total: {format_size(rest_total)}, {rest_pct:.1f}%)")
        if use_color:
            summary = f"{COLOR_DIM}{summary}{RESET}"
        print(f"{indent}{'':>9}  {summary}")


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="A tiny disk-usage visualizer (like dust/ncdu, but yours)."
    )
    parser.add_argument("path", nargs="?", default=".",
                         help="Directory to scan (default: current directory)")
    parser.add_argument("--top", type=int, default=15,
                         help="How many items to show per level (default: 15)")
    parser.add_argument("--depth", type=int, default=1,
                         help="How many levels deep to recurse (default: 1)")
    parser.add_argument("--min-size", type=str, default="0",
                         help="Hide items smaller than this, e.g. '50M' (default: 0)")
    parser.add_argument("--name-width", type=int, default=45,
                         help="Truncate filenames longer than this, adding '…' (default: 45)")
    parser.add_argument("--no-color", action="store_true",
                         help="Disable colored output")
    args = parser.parse_args()

    # Auto-disable color if we're not printing to a real terminal (e.g. the
    # output is being piped into a file or another program) — ANSI codes
    # would otherwise show up as garbled text like '\x1b[91m' in a file.
    use_color = (not args.no_color) and sys.stdout.isatty()

    target = Path(args.path).expanduser().resolve()
    if not target.exists():
        print(f"Error: {target} does not exist.")
        sys.exit(1)
    if not target.is_dir():
        print(f"Error: {target} is not a directory.")
        sys.exit(1)

    try:
        min_size = parse_size(args.min_size)
    except ValueError:
        print(f"Error: couldn't parse --min-size value '{args.min_size}'")
        sys.exit(1)

    # size_cache is shared across the whole run so directories that get
    # visited more than once (e.g. summed for a parent, then displayed
    # themselves) aren't re-scanned from scratch each time.
    size_cache: dict = {}

    total = dir_size(target, size_cache)
    print(f"\nDisk usage for: {target} (total: {format_size(total)})\n")

    print_level(target, size_cache, top=args.top, min_size=min_size,
                depth=1, max_depth=args.depth,
                use_color=use_color, name_width=args.name_width)
    print()


if __name__ == "__main__":
    main()
