import setuptools

setuptools.setup(
    name="fiftyone_pipeline_cloudrequestengine",
    version="0.0.1",
    author="51Degrees",
    python_requires='>=2.7',
    packages=["fiftyone_pipeline_cloudrequestengine"],
    install_requires=[
          'requests'
    ]
)