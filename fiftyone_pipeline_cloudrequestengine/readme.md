# Cloud Request Engine

![51Degrees](https://51degrees.com/img/logo.png?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-readme.md&utm_term=cloud-request-engine "Data rewards the curious") **Python Pipeline Cloud Request Engine**

[Developer Documentation](https://51degrees.com/pipeline-python/index.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-readme.md&utm_term=cloud-request-engine "Developer Documentation")

## Introduction

The Pipeline is a generic web request intelligence and data processing solution with the ability to add a range of 51Degrees and/or custom plug ins (Engines) 

## Requirements

* Python 3.8+

## This package fiftyone_pipeline_cloudrequestengine

This package uses the `engines` class created by the `fiftyone-pipeline-engines`. It makes available:

* A `Cloud Request Engine` which calls the 51Degrees cloud service to fetch properties and metadata about them based on a provided resource key. Get a resource key at https://configure.51degrees.com/?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-readme.md&utm_term=this-package-fiftyone_pipeline_cloudrequestengine
* A `Cloud Engine` template which reads data from the Cloud Request Engine.

It is used by the cloud versions of the following 51Degrees engines:

- [**fiftyone_devicedetection**](https://pypi.org/project/fiftyone-devicedetection/) - Get details about the devices accessing your web page
- [**fiftyone_location**](https://pypi.org/project/fiftyone-location/) - Get postal address details from the location of devices accessing your web page
