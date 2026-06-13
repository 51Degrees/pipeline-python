# 51Degrees Pipeline API

![51Degrees](https://51degrees.com/img/logo.png?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=readme.md&utm_term=51degrees-pipeline-api "Data rewards the curious") **Python Pipeline**

[Developer Documentation](https://51degrees.com/pipeline-python/index.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=readme.md&utm_term=51degrees-pipeline-api "Developer Documentation")

## Introduction
This repository contains the components of the Python implementation of the 51Degrees Pipeline API.

The Pipeline is a generic web request intelligence and data processing solution with the ability to add a range of 51Degrees and/or custom plug ins (Engines) 

## Contents
This repository contains 3 modules:

- **fiftyone_pipeline_core** - Defines the essential components of the Pipeline API such as 'flow elements', 'flow data' and 'evidence'
- **fiftyone_pipeline_engines** - Functionality for a specialized type of flow element called an engine.
- **fiftyone_pipeline_cloudrequestengine** - An engine used to make requests to the 51Degrees cloud service.

## Dependencies

For runtime dependencies, see our [dependencies](https://51degrees.com/documentation/_info__dependencies.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=readme.md&utm_term=dependencies) page.
The [tested versions](https://51degrees.com/documentation/_info__tested_versions.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=readme.md&utm_term=dependencies) page shows the Python versions that we currently test against. The software may run fine against other versions, but additional caution should be applied.

## Installation

### From PyPI

Generally, you will want to be installing one of the engines such as [device detection](https://pypi.org/project/fiftyone-devicedetection/) or [location](https://pypi.org/project/fiftyone-location/). However, if you do want to install the core modules directly (for example, to work on your own engine) then just use `pip install` with the relevant module name: 

`pip install fiftyone-pipeline-core`
`pip install fiftyone-pipeline-engines`
`pip install fiftyone-pipeline-cloundrequestengine`

### From GitHub

* Clone repository
* Install `pipenv` https://pypi.org/project/pipenv/
* Run `pipenv install` in the root of the folder
* Launch the environment shell by running `pipenv shell`

## Tests

If you've cloned the repository from GitHub, you can run the tests 
and examples that are available. To run tests:

* Go to each directory (for example `fiftyone_pipeline_core`)
* Run `python -m unittest discover -s tests -p test*.py`

## Examples

There are several examples available that demonstrate how to make use of the Pipeline API in isolation. These are described in the table below.
If you want examples that demonstrate how to use 51Degrees products such as device detection, then these are available in the corresponding [repository](https://github.com/51Degrees/device-detection-python) and on our [website](https://51degrees.com/documentation/_examples__device_detection__index.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=readme.md&utm_term=examples).

| Example                                                                     | Description                                                                                          |
|-----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------|
| fiftyone_pipeline_code/examples/client_side_evidence_custom_flow_element.py | Demonstrates how to create a custom flow element, which can then be included in a pipeline.          |
| fiftyone_pipeline_engines_fiftyone/examples/usagesharing                    | Shows how to share usage with 51Degrees. This helps us to keep our products up to date and accurate. |

To run the custom flow element example, you will need to use flask:
### Linux

Install packages
```shell
pwsh ./setup.ps1
```
Set path to the script
```sh
export FLASK_APP=client_side_evidence_custom_flow_element.py
```
then start your application with
```sh
flask run
```

### Windows

Install packages
```shell
pwsh ./setup.ps1
```
Set path to the script
```pwsh
$env:FLASK_APP = "client_side_evidence_custom_flow_element.py"
```
then start your application with 
```pwsh
flask run
```
