$ErrorActionPreference = "Stop"

# Compatibility entrypoint retained for soak scripts. Topic ownership and
# cleanup policies live in one script so manual setup cannot drift from the
# normal local runtime.
& (Join-Path $PSScriptRoot "create-topics.ps1")
