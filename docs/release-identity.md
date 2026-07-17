# Ravan Release Identity

Ravan `1.0.0-beta.1` is the first public source and Docker Compose release
candidate. The public repository is
`https://github.com/Navid-Moradimehr/Ravan` and the project is licensed under
Apache-2.0.

The beta label means the platform APIs and deployment contracts are ready for
pilot use, while final OS installers and real-site certification remain later
release gates. It does not change the self-hosted or operator-owned deployment
model.

GitHub Actions validates Python tests, the production Compose profile, the Helm
chart, and the UI build on every change. A `v*` tag publishes a checksummed
source bundle and `release-manifest.json`. Installer and signed container-image
publishing remain a later packaging phase.

## Command compatibility

The public command names are `ravanctl`, `ravand`, and `ravan-import`.
The older `datastreamctl`, `datastreamd`, and `datastream-import` aliases
remain supported so existing local automation does not break.

## Python runtime boundary

Source contributors can use the Python CLI directly. Docker Compose operators
do not need Python installed on their host: later Compose wrappers run the CLI
inside the Ravan service image. Native installers will embed the approved
Python runtime rather than requiring a separate user-managed Python install.

## Release metadata

Every published image, source bundle, API health response, AI gateway health
response, Helm chart, and release manifest must use the same product version.
Release gates reject placeholder repository URLs and inconsistent versions.
