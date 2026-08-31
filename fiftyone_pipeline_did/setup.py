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


def read(file_name):
    """Read a text file and return the content as a string."""
    try:
        with io.open(
            os.path.join(os.path.dirname(__file__), file_name), encoding="utf-8"
        ) as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


setuptools.setup(
    name="fiftyone_pipeline_did",
    version=read("version.txt"),
    author="51Degrees Engineering",
    author_email="engineering@51degrees.com",
    url="https://51degrees.com/?utm_source=pypi&utm_medium=package&utm_campaign=pipeline-python&utm_content=fiftyone_pipeline_did-setup.py&utm_term=url",
    description=("Strongly typed reader and cloud client for the 51Did (51Degrees Identifier) value returned by the 51Degrees Cloud service. Parses the OWID envelope in either base64 alphabet and exposes the Flags, License Id and match key plus the identifier type, and verifies a 51Did's signature offline or through the cloud and redeems a sealed creator context result on the server. Compare match keys, never envelopes."),
    long_description=read("readme.md"),
    long_description_content_type='text/markdown',
    python_requires=">=3.9",
    packages=["fiftyone_pipeline_did", "fiftyone_pipeline_did._owid"],
    package_dir={"": "src"},
    # The OWID source is carried inside this package as the private module
    # fiftyone_pipeline_did._owid, copied out of the 51Degrees owid-python
    # fork by ci/copy-owid-source.ps1 before the distribution is built. It
    # cannot
    # come from a package registry, because the 51Degrees fork is not
    # published to PyPI and the name "owid" there belongs to an unrelated
    # project, so a bare install_requires=["owid"] would install the wrong
    # thing. The module is private (leading underscore) so that installing
    # this package never claims the top level name "owid" on a consumer's
    # machine. Its only third party requirement is cryptography, which is
    # declared below and does come from PyPI.
    package_data={"fiftyone_pipeline_did._owid": ["LICENSE", "NOTICE"]},
    install_requires=["cryptography>=41"],
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
