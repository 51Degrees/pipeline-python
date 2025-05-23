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


from .flowelement import FlowElement
from .evidence_keyfilter import EvidenceKeyFilter
import uuid

class SequenceElementEvidenceKeyFilter(EvidenceKeyFilter):

    def filter(self, key):
    
        if (key == "query.sequence" or key == "query.session-id"):
            return True
            
        return False


class SequenceElement(FlowElement):

    """!
    The SequenceElement stores session data regarding
    requests for client side JavaScript from the JavaScript
    created by a Pipeline's JavaScriptBuilder
    If a Pipeline is constructed with the JavaScript elements
    enabled this is added automatically along with the JavaScriptBuilder
    and JSONBundler.
    """

    def __init__(self):

        super(SequenceElement, self).__init__()

        self.datakey = "sequence"
        self.exclude_from_messages = True


    def get_evidence_key_filter(self):
    
        """!
        The SequenceElement uses query.sequence and query.session-id evidence
        """
  
        return SequenceElementEvidenceKeyFilter()

    def process_internal(self, flowdata):

        """!
        The SequenceElement stores session data for requests for JavaScript
    
        @type flowdata: FlowData
        @param flowdata: The FlowData

        """
    
        if flowdata.evidence.get("query.session-id"):
            
            # Get current sequence number
    
            sequence = flowdata.evidence.get("query.sequence")
      
            if sequence:
                sequence = int(sequence)
            else:
                sequence = 1
           
      
            flowdata.evidence.add("query.sequence", sequence + 1)

        else:
            flowdata.evidence.add(
                "query.session-id",
                str(uuid.uuid4())
            )
      
            flowdata.evidence.add("query.sequence", 1)
