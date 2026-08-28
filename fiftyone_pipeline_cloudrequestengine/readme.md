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

## Pointing the engine at another host

The engine calls `https://cloud.51degrees.com/api/v4/` unless told
otherwise. Set the `FOD_CLOUD_API_URL` environment variable, or pass
`cloud_endpoint` in the engine settings, to the API base of another
host including the `/api/v4/` segment. A host other than
cloud.51degrees.com would be used to (a) use an on premise web server,
or (b) use a privately hosted version of the 51Degrees cloud for
performance reasons. This is the private hosting option of the cloud
service, and both run the same service, so code written against one
works unchanged against the other.

It is used by the cloud versions of the following 51Degrees engines:

- [**fiftyone_devicedetection**](https://pypi.org/project/fiftyone-devicedetection/) - Get details about the devices accessing your web page
- [**fiftyone_location**](https://pypi.org/project/fiftyone-location/) - Get postal address details from the location of devices accessing your web page
