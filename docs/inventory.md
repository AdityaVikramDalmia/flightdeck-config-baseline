# Inventory, limits, and relocation

Every invocation supplies one or more `--root NAME=PATH` values. Names are 1–64
ASCII characters, begin with a letter, and then contain letters, digits, `_`, or
`-`. Names must be unique. Selected filesystem paths cannot overlap. Existing root aliases are compared by filesystem identity as well as spelling, including case/Unicode aliases on filesystems that equate them and multiple hard links to the same selected root entry. Selecting an
entire filesystem root is refused; choose a bounded file or subdirectory instead.

The tool resolves ancestors of each explicit input path, then treats its final
component without following symlinks. Directory traversal uses open directory
file descriptors and `O_NOFOLLOW` when opening each child. Symlink entries are
recorded with `readlink`, including dangling links and loops. A symlink naming an
outside directory does not expand the inventory. Parent-path aliases resolve to
the explicit filesystem location selected by the caller; they are not additional
roots discovered by the tool.

| Entry type | Recorded attributes |
| --- | --- |
| Regular file | Relative path, permission mode, byte size, SHA-256 of contents |
| Directory | Relative path and permission mode, including empty directories |
| Symlink | Relative path, permission mode, exact link target text |

Modes include POSIX permission, set-ID, and sticky bits. Ownership, ACLs, extended
attributes, flags, timestamps, and hard-link relationships are not recorded.
Reading may update access times according to the filesystem. Hidden files are
included; there are no filename-based exclusions or special project defaults.
Changing a file's timestamp alone does not produce a finding.

Root-relative paths use `/` separators. The empty relative path denotes the root
entry itself. Filenames containing spaces, newlines, tabs, quotes, backslashes,
or non-ASCII bytes are retained through JSON escaping. Human output quotes paths
so control characters do not create misleading extra lines.

## Relocation

The manifest stores labels and relative paths, not absolute root locations.
Supply the same labels with new paths after an intentional relocation:

```bash
config-baseline check --manifest ./references/config.json \
  --root app='/new location/app-config' --root service=/new/location/service.conf
```

Every original label must be supplied exactly once. A missing root means its
recorded entries were removed. A missing/unreadable manifest is an error, not an
empty baseline. Symlink targets remain literal: an absolute link target changing
during relocation is a real recorded difference.

## Budgets and concurrent changes

Entry count includes each root, directory, file, and symlink. The byte budget
counts regular-file bytes across all roots. Hard-linked files reached inside a selected directory count separately
because each child pathname is inventoried independently. Two explicitly selected
root entries with the same device/inode are rejected as duplicate roots. Depth starts at 0
for each root; its immediate children have depth 1. The configurable depth ceiling
is 256. Directory enumeration stops when it exceeds the entry budget; a budget
failure never publishes a partial baseline or presents a successful comparison.

The tool detects many changes during reads using before/after inode, size, mode,
mtime, and ctime checks. These checks are not an atomic filesystem snapshot. Files
can change after they were read or change and revert between observations. Stop
writers while taking a reference or checking it when consistency matters. This
is a local filesystem tool, not a sandbox against concurrent hostile writers.
No execution, remote lookup, or content interpretation is performed.
