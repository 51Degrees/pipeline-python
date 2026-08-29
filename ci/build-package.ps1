param (
    [Parameter(Mandatory=$true)]
    [string]$RepoName,
	[Parameter(Mandatory=$true)]
    [string]$Version
)

# The 51Did package carries the OWID source inside itself, because the
# dependency cannot come from a package registry. Copy it in before the
# distributions are built, so that both the source distribution and the wheel
# contain it. See ci/copy-owid-source.ps1 for the full reasoning.
& "$PSScriptRoot/copy-owid-source.ps1" -RepoRoot $RepoName

$packages = "fiftyone_pipeline_core", "fiftyone_pipeline_engines", "fiftyone_pipeline_engines_fiftyone", "fiftyone_pipeline_cloudrequestengine", "fiftyone_pipeline_translation", "fiftyone_pipeline_did"
./python/build-package-pypi.ps1 -RepoName $RepoName -Version $Version -Packages $packages

exit $LASTEXITCODE
