# The 51Did package builds against the OWID source, which lives in the
# owid-python submodule and is copied into the package rather than installed
# from a package registry. See ci/copy-owid-source.ps1 for why.
& "$PSScriptRoot/ci/copy-owid-source.ps1"

python -m pip install -e fiftyone_pipeline_cloudrequestengine/
python -m pip install -e fiftyone_pipeline_core/
python -m pip install -e fiftyone_pipeline_translation/
python -m pip install -e fiftyone_pipeline_engines/
python -m pip install -e fiftyone_pipeline_engines_fiftyone/
python -m pip install -e owid-python/
python -m pip install flask
