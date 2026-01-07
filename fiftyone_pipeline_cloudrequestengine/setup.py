# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2026 51 Degrees Mobile Experts Limited, Davidson House,
# Forbury Square, Reading, Berkshire, United Kingdom RG1 3EU.
#
# This Original Work is licensed under the European Union Public Licence
# (EUPL) v.1.2 and is subject to its terms as set out below.
#
# If a copy of the EUPL was not distributed with this file, You can obtain
# one at https://opensource.org/licenses/EUPL-1.2.
#
# The 'Compatible Licences' set out in the Appendix to the EUPL (as may be
# amended by the European Commission) shall be deemed incompatible for
# the purposes of the Work and the provisions of the compatibility
# clause in Article 5 of the EUPL shall not apply.
#
# If using the Work as, or as part of, a network application, by
# including the attribution notice(s) required under Article 5 of the EUPL
# in the end user terms of the application under an appropriate heading,
# such notice(s) shall fulfill the requirements of that article.
# *********************************************************************

import setuptools
import os
import io


# Read a text file and return the content as a string.
def read(file_name):
    """Read a text file and return the content as a string."""
    try:
        with io.open(
            os.path.join(os.path.dirname(__file__), file_name), encoding="utf-8"
        ) as f:
            return f.read().strip()
    except:
        return "0.0.0"


setuptools.setup(
    name="fiftyone_pipeline_cloudrequestengine",
    version=read("version.txt"),
    author="51Degrees Engineering",
    author_email="engineering@51degrees.com",
    url="https://51degrees.com/",
    description=("This package contains a shared engine that is used to make requests to the 51Degrees cloud service on behalf of other data services such as device detection or location."),
    long_description=read("readme.md"),
    long_description_content_type='text/markdown',
    python_requires=">=3.8",
    packages=["fiftyone_pipeline_cloudrequestengine"],
    package_dir={"": "src"},
    install_requires=[
          'fiftyone_pipeline_engines',
          'requests',
    ],
    license="EUPL-1.2",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python",
        "License :: OSI Approved :: European Union Public Licence 1.2 (EUPL 1.2)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules"
    ],
    include_package_data=True
)
