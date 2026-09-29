# duviz — a tiny disk-usage visualizer

## What this is for

A `dust`/`ncdu`-style tool: point it at a folder and it shows which
subfolders and files are eating your disk space, with a proportional bar
chart so the biggest offenders are obvious at a glance instead of
scrolling through a wall of numbers.

```
Disk usage for: /home/alif/Downloads (total: 8.4 GB)

  5.2 GB  [██████████████████░░░░░░░░░░]  61.2%  kali-linux-2026.2-live-amd64.iso/
  3.2 GB  [███████████░░░░░░░░░░░░░░░░░]  38.0%  WIn7-disk001.vmdk
 45.3 MB  [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   0.5%  Wood_Dataset.zip
  ...
```

## How it works

### Computing folder sizes

There's no shortcut for "how big is this folder" — the OS doesn't store a
running total anywhere. `duviz` computes it itself, recursively:

1. `dir_size()` walks a folder with `os.scandir()`.
2. For each entry: a file adds its byte size directly; a folder calls
   `dir_size()` on itself again (recursion) and adds *that* result.
3. Symlinks are skipped — following them could infinite-loop (a symlink
   pointing back up the tree) or double-count space that isn't really
   "inside" this folder.
4. Every folder's computed size is cached in a dict for the run, so the
   same folder is never walked twice.

### Displaying a level

`print_level()` takes one folder's direct children, sorts them
biggest-first, and shows the top N (`--top`, default 15) with a bar whose
length is proportional to *that item's share of the current level* —
not some arbitrary fixed scale. Anything past the top N gets folded into
a single `... N more items` line so small files don't flood your terminal.

If `--depth` allows, it recurses one level deeper *only* into the folders
it already decided to show — the same progressive-drill-down behavior as
`dust`.

### Visual details

- **Truncation** — filenames longer than `--name-width` (default 45) get
  cut with a trailing `…` instead of wrapping onto a second line and
  breaking column alignment.
- **Color** — the filled portion of each bar is colored by how much of
  its level it takes up: 🟥 red ≥ 40%, 🟨 yellow ≥ 15%, 🟩 green below
  that. Directories are also colored blue in the name column. Color
  auto-disables when output isn't a real terminal (e.g. piped to a file),
  since raw ANSI codes would otherwise show up as garbled text.

## Usage

```bash
python3 duviz.py                     # scan the current directory
python3 duviz.py ~/Downloads         # scan a specific directory
python3 duviz.py . --top 10          # show only the top 10 items per level
python3 duviz.py . --depth 3         # recurse 3 levels deep instead of 1
python3 duviz.py . --min-size 50M    # hide anything smaller than 50 MB
python3 duviz.py . --name-width 30   # truncate names more aggressively
python3 duviz.py . --no-color        # disable color manually
```

## Running `duviz` from anywhere

Unlike `dotman`, `duviz` doesn't need to locate a "home base" repo — the
folder it scans is just whatever path you pass it (or the current
directory by default). That means it's safe to symlink as-is into a
folder that's already on your `$PATH`:

```bash
chmod +x ~/wherever/duviz.py
ln -s ~/wherever/duviz.py ~/.local/bin/duviz
```

Now, from any directory:

```bash
duviz ~/Downloads --depth 2
```

This works because of two things together: `chmod +x` makes the file
directly executable, and its first line
(`#!/usr/bin/env python3`, the "shebang") tells the OS which interpreter
to run it with — that combination is what lets you drop the `python3`
prefix and call it as a bare command.

## Practical notes

- Scanning `/` will hit permission errors on some system folders (other
  users' homes, restricted system dirs). `duviz` catches these and skips
  them with a stderr warning rather than crashing, so you still get a
  usable report.
- `--min-size` accepts a plain byte count or a suffix: `K`, `M`, `G`, `T`
  (e.g. `500K`, `2.5G`).
