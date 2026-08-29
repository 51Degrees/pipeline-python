param (
    # The root of the pipeline-python working copy. Defaults to the parent of
    # this script, which is right for a developer checkout, and is passed
    # explicitly by the CI scripts because they run from the workspace above
    # the clone.
    [string]$RepoRoot = (Split-Path $PSScriptRoot -Parent)
)
$ErrorActionPreference = "Stop"

# Copies the OWID source into the 51Did package as the private module
# fiftyone_pipeline_did._owid, so that a published wheel can be imported
# without the OWID library being installed separately.
#
# The dependency cannot come from a package registry. The 51Degrees fork of
# OWID is not published to PyPI, and the name "owid" on PyPI belongs to an
# unrelated project, so declaring install_requires=["owid"] would install the
# wrong thing. The name here carries a leading underscore so that installing
# the 51Did package never claims the top level name "owid" on a consumer's
# machine.
#
# Nothing is fetched over the network, because owid-python is a submodule and
# CI clones with --recurse-submodules. Nothing is written back to the
# repository either, as the copy is ignored by git and main keeps the
# submodule as the single source of the OWID code.

$owidRepo = Join-Path $RepoRoot "owid-python"
$owidSource = Join-Path $owidRepo "owid"
$target = Join-Path $RepoRoot `
    "fiftyone_pipeline_did/src/fiftyone_pipeline_did/_owid"

if (-not (Test-Path (Join-Path $owidSource "__init__.py"))) {
    throw "OWID source not found at '$owidSource'. Run " +
        "'git submodule update --init --recursive' first, or clone with " +
        "--recurse-submodules."
}

# The commit the copy was taken from, so the notice can say exactly which
# version of the OWID source is inside the package.
$commit = (git -C $owidRepo rev-parse HEAD 2>$null)
if (-not $commit) {
    $commit = (git -C $RepoRoot rev-parse "HEAD:owid-python" 2>$null)
}
if (-not $commit) {
    throw "Could not determine the owid-python commit to record in the notice."
}

if (Test-Path $target) {
    Remove-Item -Path $target -Recurse -Force
}
$null = New-Item -ItemType Directory -Path $target -Force

Copy-Item -Path (Join-Path $owidSource "*.py") -Destination $target -Force
Copy-Item -Path (Join-Path $owidRepo "LICENSE") `
    -Destination (Join-Path $target "LICENSE") -Force

$notice = @"
The Python modules in this directory are the OWID (Open Web Id) library. They
are copied into the fiftyone_pipeline_did package at build time and are not
part of the 51Degrees source, so they keep their own licence, which is the
Apache License 2.0 in the LICENSE file beside this notice, and not the EUPL
1.2 that covers the rest of the package.

Copyright 2026 51 Degrees Mobile Experts Limited (51degrees.com)

Taken from the 51Degrees fork of the OWID project,
https://github.com/51Degrees/owid-python, at commit
$commit
which follows https://github.com/SWAN-community/owid-python.

The modules are placed under the private name _owid so that installing this
package does not claim the top level name "owid", which on PyPI belongs to an
unrelated project. Import OWID from the fork itself rather than from here.
"@
Set-Content -Path (Join-Path $target "NOTICE") -Value $notice -Encoding utf8

Write-Output "Copied OWID source at $commit into '$target'"
