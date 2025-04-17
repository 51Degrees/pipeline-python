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



from fiftyone_pipeline_core.flowelement import FlowElement
from fiftyone_pipeline_core.elementdata_dictionary import ElementDataDictionary
from fiftyone_pipeline_core.basiclist_evidence_keyfilter import BasicListEvidenceKeyFilter
from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue

class APVFlowElement(FlowElement):

    def __init__(self):

        super(APVFlowElement, self).__init__()

        self.datakey = "apv"

        self.properties = {"yes" : { "type": "string"} }
        self.properties = {"no" : { "type": "string"} }

    def process_internal(self, flowdata):

        yes = AspectPropertyValue(value="yes")
        no = AspectPropertyValue(no_value_message="no")

        data = ElementDataDictionary(self, {"yes": yes, "no": no})

        flowdata.set_element_data(data)
    
    def get_evidence_key_filter(self):

        return BasicListEvidenceKeyFilter(["header.user-agent"])
