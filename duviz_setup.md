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

SETIING IT TO $PATH
-----
chmod +x ~/dotfiles/files/duviz.py       # or wherever the real file lives, adjust path
ln -s ~/dotfiles/files/duviz.py ~/.local/bin/duviz

"""
