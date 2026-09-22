# Config Baseline

> **Deprecated for new Claude Code integrations — 2026-09-22.** Retained as an
> Apache-2.0 reference project. Public launch remains deferred and the repository
> remains private. This is a maintainer status decision, not a claim that Claude
> Code replaces every capability. No ongoing feature work or support is promised.

Record a content-and-permission inventory of explicitly selected configuration
files/directories, then report what was added, removed, or changed. Selected files
are read as bytes; they are never executed. A matching inventory means only that
the recorded attributes match your reference. It is not a malware scan or a safety
certification.

**Private release candidate: 0.1.0rc1.** Requires Python 3.9+ on POSIX systems with
descriptor-relative filesystem operations. macOS and an unprivileged Alpine Linux container have been verified. Windows is unsupported. No third-party packages, Git,
network calls, or background service are required.

## Install and use

From this checkout:

```bash
make test
make install PREFIX="$HOME/.local"
export PATH="$HOME/.local/bin:$PATH"

# Put the manifest outside the selected roots. Its parent must already exist.
mkdir -p ./references
config-baseline snapshot --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf

config-baseline check --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf

config-baseline check --json --manifest ./references/config.json \
  --root app=./app-config --root service=./service.conf
```

The installed command is one self-contained file. `./bin/config-baseline` also
works directly. `bash examples/demo.sh` creates and checks isolated fixtures.

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

Inspect changes before replacing a reference. The tool never edits scanned files,
removes findings, or chooses remediation. A missing selected root during `check`
is reported as removal; it is an error during `snapshot`.

Exit **0**: snapshot published or comparison unchanged. Exit **3**: differences
found, including removals. Exit **2**: invalid input, unreadable/unsupported data,
invalid manifest, exceeded budget, or another incomplete operation. JSON errors
have `status: "error"`; an incomplete scan never returns an empty successful diff.

Default scan budgets are **10,000 entries**, **100 MiB of regular-file contents**,
and **32 directory levels**. They are adjustable with `--max-entries`,
`--max-bytes`, and `--max-depth`. Manifests have a fixed 16 MiB size limit.

See [the documentation index](docs/README.md), [inventory semantics](docs/inventory.md),
[manifest and publication contract](docs/manifest.md), and [provenance](PROVENANCE.md).

## License and maintenance

Copyright 2026 Aditya Dalmia. Licensed under [Apache-2.0](LICENSE), with
[attribution](NOTICE) and [source provenance](PROVENANCE.md). Public launch is
deferred; repository access remains private. See the [release preparation index](docs/release/README.md),
[contributing guide](CONTRIBUTING.md), and [security contact](SECURITY.md).
