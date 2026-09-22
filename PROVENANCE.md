# Provenance

Source commit: `494799eea3b9e7ce8686506a288c297ccf96be8d`.

Source files inspected: `bin/config-sweep.sh` and `bin/config-sweep-test.sh`.
The reusable idea is a persisted file inventory with content hashes and comparison
of new, changed, and removed entries. This repository is a substantial standalone
Python adaptation, not a verbatim extraction of the Bash implementation.

The adaptation replaces fixed private surfaces and TSV records with explicit named
roots, uniform content/permission metadata, strict versioned JSON, no-follow
symlink handling, bounded reads, and atomic reference publication. Removed entries
are differences, not merely informational output. No filename taxonomy, implicit
home/project roots, verdict ledger, remediation proposals, or security verdicts
are retained.

No private remote or personal path is needed to build or use this component.
Licensing remains pending repository-owner review before wider distribution.
