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

## Credentials

The engine authenticates with a resource key, a licence key, or both, set
as `resource_key` and `license_key` in its settings. Which one is set
decides whether `requested_properties`, the list of fully qualified
property names to ask for, is also needed:

| `resource_key` | `license_key` | `requested_properties` | Accepted |
| --- | --- | --- | --- |
| Yes | No | No | Yes. The resource key states which properties it carries. |
| Yes | Yes | No | Yes. The licence key adds the products it grants. |
| No | Yes | Yes | Yes. A licence key names no properties, so the list says which are wanted. |
| No | Yes | No | No. The service answers 400 to every such request. |
| Yes | Either | Yes | No. The service ignores the list while a resource key is present. |
| No | No | Either | No. There is nothing to authenticate with. |

A combination that is not accepted raises `ValueError` when the engine is
built, so a deployment sees one configuration error rather than a failure
on every request. A value that is empty or only whitespace counts as
absent, and each value is trimmed, so a key read from an environment
variable with a trailing newline still works.

A resource key is public by design, because it travels to the browser in a
script URL. A caller that runs only on the server should use a licence
key and name the properties it wants, so the credential stays on the
server and each answer carries only what that caller needs. A licence key
is sent in the body of every request, never in a URL. Where a request
named properties and the answer left some out, the engine warns once that
they are not covered by the licence key; the properties that came back
are usable as normal.

See the [Credentials section of the cloud request engine specification](https://github.com/51Degrees/specifications/blob/main/pipeline-specification/pipeline-elements/cloud-request-engine.md#credentials)
and the rules in
[`cloudrequestengine.py`](src/fiftyone_pipeline_cloudrequestengine/cloudrequestengine.py).

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
