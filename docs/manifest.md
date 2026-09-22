# Manifest schema, publication, and recovery

Version 1 is a JSON object with exactly four top-level keys:

```json
{
  "version": 1,
  "algorithm": "sha256",
  "roots": ["app"],
  "entries": [
    {"root": "app", "path": "", "type": "directory", "mode": 493},
    {"root": "app", "path": "settings.json", "type": "file", "mode": 420,
     "size": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}
  ]
}
```

Modes are integers (`493` = octal `0755`, `420` = `0644`). Symlinks replace file
size/hash fields with a string `target`. Every root has one entry with empty path.
Every non-root entry has a recorded directory parent. Duplicate JSON keys,
duplicate paths, traversal paths, unexpected fields, invalid types/digests,
unsupported versions, and incomplete JSON are errors. The checker validates the
entire manifest before inventorying the explicitly supplied roots.

A valid schema does not prove a reference is authentic or complete. Deliberately
editing a valid manifest changes the expected state. Store and review references
according to your own change-control process. Hashes, filenames, and symlink target
text may reveal information; the tool creates manifest files with mode `0600`.

## Publication

The manifest must be outside every selected root, including paths reached through
parent symlink aliases or filesystem-equivalent case/Unicode spellings. Existing
root entries and candidate ancestor directories are compared by device/inode, so
a spelling alias cannot hide reference self-inclusion. A manifest symlink or non-regular file is refused. The
parent directory must already exist. There is no implicit exclusion that could
hide scanned configuration or make a reference silently exempt itself.

Snapshot creation builds and validates the complete inventory, writes a temporary
file in the manifest's directory, flushes and `fsync`s it, and publishes atomically.
Without `--overwrite`, an atomic hard-link creation refuses an existing destination;
concurrent creators have one winner. With `--overwrite`, `os.replace` atomically
replaces the reference. The containing directory is then `fsync`ed. Ordinary
failure cleanup removes the unpublished staging name. Scanned files are never
modified by publication.

These operations require trusted local filesystem semantics and hard-link support
for default no-overwrite publication. Network filesystems and multiple hosts are
unsupported. `fsync` is requested; this is not a hardware/power-loss certification.
Concurrent explicit overwrites can replace each other, so serialize intentional
reference updates operationally.

A process may die after publication but before printing its receipt. A directory
flush or stdout error may also occur after the complete reference became visible.
A nonzero result does not prove publication did not happen: inspect the manifest
before retrying. SIGKILL can leave `.config-baseline-*.tmp` staging files next to
the manifest. Stop snapshot writers and inspect those files before deleting them;
they are never interpreted as references automatically.

## Comparison output

JSON checks return `status`, `manifest`, `summary`, and `findings`. Summary keys
are `added`, `removed`, and `changed`. Findings identify `root`, relative `path`,
`state`, changed `fields`, and metadata `before`/`after` (`null` on the missing
side). The tool reports type, permissions, size/hash, and link-text differences;
it does not output file contents or remediation commands.
