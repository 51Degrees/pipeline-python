# Pipeline Translation

![51Degrees](https://51degrees.com/img/logo.png?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_translation-readme.md&utm_term=pipeline-translation "Data rewards the curious") **Python Pipeline Translation**

[Developer Documentation](https://51degrees.com/pipeline-python/index.html?utm_source=github&utm_medium=readme&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_translation-readme.md&utm_term=pipeline-translation "Developer Documentation")

## Introduction

The Pipeline is a generic web request intelligence and data processing solution with the ability to add a range of 51Degrees and/or custom plug ins (Engines)

## Requirements

* Python 3.8+

## This package fiftyone_pipeline_translation

This package adds a generic translation flow element to the pipeline. It takes
string based values from a single source element (a plain string, a list of
strings, or a weighted list of strings) and translates them into another
language using YAML translation files. The language to translate to can be
fixed, or resolved from the request evidence (for example an `Accept-Language`
header).

This package is built on top of:

* [fiftyone_pipeline_core](https://pypi.org/project/fiftyone-pipeline-core/)
