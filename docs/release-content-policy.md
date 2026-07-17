# Release Content Policy

Ravan releases contain platform source, deployment runtime assets, demo data,
and user/operator documentation. They do not contain the maintainer Obsidian
vault, private working notes, implementation logs, benchmark history, or test
artifacts.

The packaging allowlist is defined in `scripts/package-release.py` through
`PUBLIC_DOCUMENT_FILES`. The same public-document boundary is used for the
repository release branch. Development documentation may remain locally for
maintainer work but must be untracked before a public release.
