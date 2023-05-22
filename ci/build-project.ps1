param (
    [Parameter(Mandatory=$true)]
    [string]$RepoName
)

./python/build-project.ps1 -RepoName $RepoName

exit $LASTEXITCODE
