# Examples

Examples of the 51Degrees Pipeline API for Python that call the 51Degrees
cloud service through the cloud request engine, which is the package this
folder sits in.

## Cloud, mixed

The examples in `src/fiftyone_pipeline_examples/cloud/mixed` call the
51Degrees cloud service with a resource key or a licence key, and get device
detection and IP intelligence results from one request.

- `gettingstarted_console.py` runs five pairs of User-Agent and IP address
  through a pipeline and prints the device and IP intelligence results for
  each.
- `gettingstarted_web` is a Flask web application that shows the device
  detection and IP intelligence results for the visitor, or for an IP
  address typed into the page, along with the list of countries translated
  by the cloud service. Client-side evidence gathered in the browser then
  refines the device results.

The pipeline in both is a cloud request engine, which makes the request to
the cloud service, followed by engines that each read their own part of the
answer. Those engines are in `src/fiftyone_pipeline_examples/cloud/engines.py`,
and `src/fiftyone_pipeline_examples/cloud/mixed/pipeline.py` puts them
together.

### Keys

The examples call the cloud service with a resource key or a licence key.

A resource key carries the list of properties it returns. Create one
carrying device detection and IP intelligence properties for free with the
[configurator](https://configure.51degrees.com?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-readme.md&utm_term=resource-key),
and set the `_51DEGREES_RESOURCE_KEY` environment variable to it. The older
name `resource_key` is also read. A resource key limited to particular
domains only answers a request whose origin is one of them, so set
`cloud_request_origin` to one of its domains.

A licence key can be used on its own instead, by setting
`_51DEGREES_LICENSE_KEY`, or the older name `license_key`. A licence key
carries no list of properties, so the examples ask the cloud service for
exactly the properties they show, and the web example also asks for the
properties its client-side script needs. A licence key identifies an
account, so it stays on the server. The web page and its script only ever
talk to the example, never to the cloud service. When both kinds of key are
set, the licence key is the one used.

A property the key does not carry is shown as unknown. The console example
adds the reason, and the web example shows "Unknown" alone. A key carrying
only one of the two products still runs, and the web example shows the list
of countries only when the key carries the translated country names.

The examples use the public cloud service at `https://cloud.51degrees.com`.
Set `cloud_endpoint`, or `FOD_CLOUD_API_URL`, to the address of another
cloud service, including the `api/v4/` path, to use that instead.

### Running the examples

Clone the repository with its submodules, then from this folder create a
virtual environment and install the requirements, which install the
Pipeline packages from this checkout.

```sh
git clone --recurse-submodules https://github.com/51Degrees/pipeline-python.git
cd pipeline-python/fiftyone_pipeline_cloudrequestengine/examples
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows the interpreter is `.venv\Scripts\python.exe`.

Run the console example with

```sh
.venv/bin/python -m fiftyone_pipeline_examples.cloud.mixed.gettingstarted_console
```

and the web example with

```sh
.venv/bin/python -m fiftyone_pipeline_examples.cloud.mixed.gettingstarted_web
```

then open <http://localhost:5000>. Set `PORT` to listen on another port.

### Tests

```sh
.venv/bin/python -m pytest
```

The tests that call the cloud service skip themselves when no resource key
is set.

In CI the examples are run by [ci/run-integration-tests.ps1](../../ci/run-integration-tests.ps1)
through common-ci, on every Python version and operating system in
[ci/options.json](../../ci/options.json), with the resource key the pipeline
holds. No licence key is passed to the pipeline, so the licence-key tests
skip themselves there. That uses the [tox.ini](tox.ini) in this folder,
which can also be run by hand with `python -m tox -e py` from here.

## Find out more

- [Device detection](https://51degrees.com/device-detection?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-readme.md&utm_term=find-out-more-device-detection)
- [IP intelligence](https://51degrees.com/ip-intelligence?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-readme.md&utm_term=find-out-more-ip-intelligence)
- [Resource keys](https://51degrees.com/documentation/_services__cloud__resource_keys.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-readme.md&utm_term=find-out-more-resource-keys)
- [Pricing](https://51degrees.com/pricing?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_cloudrequestengine-examples-readme.md&utm_term=find-out-more-pricing)
- Pipeline API for Python: https://github.com/51Degrees/pipeline-python
- Device detection for Python: https://github.com/51Degrees/device-detection-python
- IP intelligence engine: https://github.com/51Degrees/ip-intelligence-cxx
