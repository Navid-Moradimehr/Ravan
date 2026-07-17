# Release Content Policy

Ravan releases contain platform source, deployment runtime assets, demo data,
and user/operator documentation. They do not contain the maintainer Obsidian
vault, private working notes, implementation logs, benchmark history, or test
artifacts.

The packaging allowlist is defined in `scripts/package-release.py` through
`PUBLIC_DOCUMENT_FILES`. The same public-document boundary is used for the
repository release branch. Development documentation may remain locally for
maintainer work but must be untracked before a public release.

Runtime dependencies are defined in `requirements.txt`. Maintainer and test
dependencies belong in `requirements-dev.txt` and must not be installed by a
production package.

Before publishing an archive, verify the staged directory with:

```powershell
py -3.13 scripts/package-release.py --output-dir .datastream/release compose
py -3.13 scripts/package-release.py verify .datastream/release/demo-site-compose --mode compose
py -3.13 scripts/package-release.py verify .datastream/release/demo-site-compose.zip --mode compose
```

The verifier checks the package manifest, generated site configuration, required
runtime files, the image-based release Compose definition, and deployment-specific assets. It rejects development folders,
compiled Python files, and common secret filenames. It is a content boundary
check, not a substitute for clean-machine installation or runtime acceptance.
