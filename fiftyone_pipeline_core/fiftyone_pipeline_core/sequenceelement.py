# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2019 51 Degrees Mobile Experts Limited, 5 Charlotte Close,
# Caversham, Reading, Berkshire, United Kingdom RG4 7BY.
#
# This Original Work is licensed under the European Union Public Licence (EUPL)
# v.1.2 and is subject to its terms as set out below.
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


"""
  The SequenceElement stores session data regarding
  requests for client side JavaScript from the JavaScript
  created by a Pipeline's JavaScriptBuilder
  If a Pipeline is constructed with the JavaScript elements
  enabled this is added automatically along with the JavaScriptBuilder
  and JSONBundler.
"""


from .flowelement import FlowElement
from .evidence_keyfilter import EvidenceKeyFilter
import uuid

class SequenceElementEvidenceKeyFilter(EvidenceKeyFilter):

    def filter(self, key):
   
      if (key == "query.sequence" or key == "query.session-id"):
          return True
            
      return False


class SequenceElement(FlowElement):

    def __init__(self):

        super(SequenceElement, self).__init__()

        self.dataKey = "sequence"

    # """
    # The SequenceElement uses query.sequence and query.session-id evidence
    # """

    def getEvidenceKeyFilter(self):
  
      return SequenceElementEvidenceKeyFilter()

    def processInternal(self, flowData):

        """"
        The SequenceElement stores session data for requests for JavaScript
    
        @type FlowData: FlowData
        @param FlowData: The FlowData

        """
    
        if flowData.evidence.get("query.session-id"):
            
            # Get current sequence number
    
            sequence = flowData.evidence.get("query.sequence")
      
            if sequence:
                sequence = int(sequence)
            else:
                sequence = 1
           
      
            flowData.evidence.set("query.sequence", sequence + 1)

        else:
            flowData.evidence.set(
                "query.session-id",
                uuid.uuid4()
            )
      
            flowData.evidence.set("query.sequence", 1)