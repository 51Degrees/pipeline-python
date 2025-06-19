# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2025 51 Degrees Mobile Experts Limited, Davidson House,
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

## @example usagesharing/usagesharing.py
#
# @include{doc} example-usage-sharing-intro.txt
#
# Usage sharing is enabled by default if using some 51Degrees pipeline 
# builders such as the [DeviceDetectionOnPremisePipelineBuilder](https://github.com/51Degrees/device-detection-python/blob/main/fiftyone_devicedetection_onpremise/src/fiftyone_devicedetection_onpremise/devicedetection_onpremise_pipelinebuilder.py).
# In this example, we show how to specifically add a usage sharing 
# element to a Pipeline using configuration.
#
# As with all flow elements, this can also be handled in code, 
# using the constructor parameters. The commented section in the 
# example demonstrates this.
#
# The 51d.json file contains all the configuration options.
# These are all optional, so each can be omitted if the default 
# for that option is sufficient:
#
# @include usagesharing/51d.json
#
# For details of what each setting does, see the constructor
# parameters in the reference documentation for the 
# [share usage element](https://51degrees.com/pipeline-python/classfiftyone__pipeline__engines__fiftyone_1_1share__usage_1_1_share_usage.html) 
#
# This example is available in full on [GitHub](https://github.com/51Degrees/pipeline-python/blob/main/fiftyone_pipeline_engines_fiftyone/examples/usagesharing/usagesharing.py).
#
# Expected output:
# ```
# Constructing pipeline from configuration file.
# 
# Pipeline created with share usage element. Evidence processed 
# with this pipeline will now be shared with 51Degrees using the 
# specified configuration.
# ```

import os
import json
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder
from fiftyone_pipeline_engines_fiftyone.share_usage import ShareUsage

print("Constructing pipeline from configuration file.")
print()

# Create a new pipeline from the supplied config file.
dir = os.path.dirname(__file__)
with open(os.path.join(dir, '51d.json')) as json_file:
  pipeline = PipelineBuilder().build_from_configuration(json.load(json_file))

# Alternatively, the commented code below shows how to
# configure the ShareUsageElement in code, rather than
# using a configuration file.
#usageElement = ShareUsage(
#  share_percentage = 0.1,
#  requested_package_size = 2000
#)
#pipeline = PipelineBuilder().add(usageElement).build()

print("""Pipeline created with share usage element. Evidence processed 
with this pipeline will now be periodically shared with 51Degrees using 
the specified configuration.""")
