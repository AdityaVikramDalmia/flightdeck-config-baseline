# Config Baseline

Record a content-and-permission inventory of explicitly selected configuration files and
directories, then report what was added, removed, or changed since that reference: for scripts and
reviewers who need to know whether configuration still matches what they last reviewed.

> **Status:** public Apache-2.0 reference implementation, deprecated for new Claude Code
> integrations as of 2026-09-22. Not a claim that Claude Code replaces every capability; no
> ongoing feature work or support is promised.

## What it does

- `config-baseline snapshot` records each selected root under a label you choose: every file,
  directory, and symlink with its relative path and permission mode, plus byte size and SHA-256
  for files and the link text for symlinks. The manifest is strict, versioned JSON.
- `config-baseline check` inventories the same roots again and reports additions, removals, and
  changes, as text or JSON.
- Selected files are read as bytes; they are never executed. The tool never edits scanned files,
  removes findings, or chooses remediation.

## Why it exists

Configuration can change without notice: edited content, a changed permission bit, a new hidden
file, or a deleted entry. Config Baseline turns those changes into an explicit diff against a
reference you chose. Removals count as differences, and an incomplete scan is an error: it never
returns an empty successful diff.

## Install

Version 0.1.0rc1. Requires Python 3.9+ on POSIX systems with descriptor-relative filesystem
operations. Windows is unsupported. No third-party packages, Git, network calls, or background
service are required.

```bash
git clone https://github.com/AdityaVikramDalmia/flightdeck-config-baseline.git
cd flightdeck-config-baseline
make test
make install PREFIX="$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"
```

The installed command is one self-contained file. `./bin/config-baseline` also works directly.

## Quick use

```bash
# Put the manifest outside the selected roots. Its parent must already exist.
mkdir -p ./references
config-baseline snapshot --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf

config-baseline check --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf

config-baseline check --json --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf
```

`bash examples/demo.sh` creates and checks isolated fixtures.

Root names are stable labels you choose; paths must be explicit on every command.
A root can be a regular file, directory, or symlink. Directories include all their
entries, including hidden files and empty directories. Symlinks record only their
link text and mode; their targets are never traversed or hashed. Unsupported types
such as FIFOs/devices/sockets and unreadable entries cause an error.

An existing reference is preserved unless you intentionally add `--overwrite`:

```bash
config-baseline snapshot --overwrite --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf
```

Inspect changes before replacing a reference. A missing selected root during `check`
is reported as removal; it is an error during `snapshot`.

Exit **0**: snapshot published or comparison unchanged. Exit **3**: differences
found, including removals. Exit **2**: invalid input, unreadable/unsupported data,
invalid manifest, exceeded budget, or another incomplete operation. JSON errors
have `status: "error"`; an incomplete scan never returns an empty successful diff.

See [the documentation index](docs/README.md), [inventory semantics](docs/inventory.md),
[manifest and publication contract](docs/manifest.md), and [provenance](PROVENANCE.md).

## Limits

- A matching inventory means only that the recorded attributes match your reference. It is not a
  malware scan or a safety certification, and a valid manifest does not prove the reference is
  authentic ([manifest contract](docs/manifest.md)).
- Default scan budgets are **10,000 entries**, **100 MiB of regular-file contents**,
  and **32 directory levels**. They are adjustable with `--max-entries`,
  `--max-bytes`, and `--max-depth`. Manifests have a fixed 16 MiB size limit.
- Ownership, ACLs, extended attributes, timestamps, and hard-link relationships are not recorded.
  Reads are not an atomic filesystem snapshot; stop writers when consistency matters
  ([inventory semantics](docs/inventory.md)). Network filesystems and multiple hosts are
  unsupported ([publication contract](docs/manifest.md)).

## Test

```bash
make test
```

macOS and an unprivileged Alpine Linux container have been verified.

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). This is a public
reference implementation, deprecated for new Claude Code integrations as of 2026-09-22. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
