# API Specific CI/CD Approach
This API complies with the `common-ci` approach.

The following secrets are required:
* `ACCESS_TOKEN` - GitHub [access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#about-personal-access-tokens) for cloning repos, creating PRs, etc.
    * Example: `github_pat_l0ng_r4nd0m_s7r1ng`
* `SUPER_RESOURCE_KEY` - [resource key](https://51degrees.com/documentation/_info__resource_keys.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=ci-readme.md&utm_term=api-specific-ci-cd-approach) for integration tests
    * Example: `R4nd0m-S7r1ng`
* `PYPI_TOKEN` - [PyPI token](https://pypi.org/help/#apitoken) for publishing packages
    * Example: `pypi-sUp3r-l0nG_r4nd0m-s7r1Ng`
