# Pipeline Core

![51Degrees](https://51degrees.com/img/logo.png?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_core-readme.md&utm_term=pipeline-core "Data rewards the curious") **Python Pipeline Core**

[Developer Documentation](https://51degrees.com/pipeline-python/index.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_core-readme.md&utm_term=pipeline-core "Developer Documentation")

## Introduction

The Pipeline is a generic web request intelligence and data processing solution with the ability to add a range of 51Degrees and/or custom plug ins (Engines) 

## This package fiftyone_pipeline_core

This package defines the essential components of the Pipeline API such as `flow elements`, `flow data` and `evidence`. It also packages together JavaScript served by a pipeline and allows for client side requests for additional data populated by evidence from the client side.

It can be used on its own or with the following additional packages.

- **fiftyone_pipeline_engines** - Adds a specialized type of flow element called an engine which allows for additional features including an auto-updating data file for properties, a service called when a requested property is missing and a caching system.

Engines created by 51Degrees:

- [**fiftyone_devicedetection**](https://pypi.org/project/fiftyone-devicedetection/) - Get details about the devices accessing your web page
- [**fiftyone_location**](https://pypi.org/project/fiftyone-location/) - Get postal address details from the location of devices accessing your web page

## Requirements

* Python 3.8+
* The `flask` python library to run the web examples 
