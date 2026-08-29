param (
    [Parameter(Mandatory=$true)]
    [string]$RepoName
)

# The 51Did package is built from its own tox environment by the unit test
# step, and that build needs the OWID source in place, so put it there before
# anything builds. See ci/copy-owid-source.ps1 for the full reasoning.
& "$PSScriptRoot/copy-owid-source.ps1" -RepoRoot $RepoName

$packages = "fiftyone_pipeline_core", "fiftyone_pipeline_engines", "fiftyone_pipeline_engines_fiftyone", "fiftyone_pipeline_cloudrequestengine", "fiftyone_pipeline_translation"
./python/build-project.ps1 -RepoName $RepoName -Packages $packages

exit $LASTEXITCODE
