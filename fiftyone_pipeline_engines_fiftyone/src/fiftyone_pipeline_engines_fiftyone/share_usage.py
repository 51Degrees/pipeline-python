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

import random
import json
import gzip
import platform
import datetime
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version

import requests
from fiftyone_pipeline_engines.engine import Engine

from .share_usage_evidencekeyfilter import ShareUsageEvidenceKeyFilter
from .share_usage_tracker import ShareUsageTracker

# The maximum length of a piece of evidence's value which can be
# added to the usage data being sent.
SHARE_USAGE_MAX_EVIDENCE_LENGTH = 512

SHARE_USAGE_VERSION = '1.1'

# The default number of seconds to wait for the server connection before failing the request when sending usage data
REQUEST_TIMEOUT = 60


class ShareUsage(Engine):
    def __init__(
        self,
        interval = 1200,
        requested_package_size = 10,
        cookie = None,
        query_whitelist = [],
        header_blacklist = [],
        share_percentage = 1,
        endpoint = "https://devices-v4.51degrees.com/new.ashx",
        request_timeout=REQUEST_TIMEOUT):
        """!
        Constructor for ShareUsage element
        
        @type interval: int
        @param interval: If exactly the same evidence values are seen 
        multiple times within this time limit (in seconds) then they 
        will only be shared once.
        @type requested_package_size: int
        @param requested_package_size: The usage element will group data into 
        single requests before sending it. This setting controls the minimum 
        number of entries before data is sent. If you are sharing large 
        amounts of data, increasing this value is recommended in order to 
        reduce the overhead of sending HTTP messages.
        For example, the 51Degrees cloud service uses a value of 2500.
        @type cookie: string
        @param cookie: If a cookie is being used to identify user 
        sessions, it can be specified here in order to reduce the 
        sharing of duplicated data.
        @type query_whitelist: list
        @param query_whitelist: By default query string and HTTP form 
        parameters are not shared unless prefixed with '51D_'.
        If you need to share query string parameters, a list can be 
        specified here.
        @type query_blacklist: list
        @param query_blacklist: By default, all HTTP headers 
        (except a few, such as Cookies) are shared. 
        Individual headers can be excluded from sharing by adding them 
        to this list.
        @type share_percentage : float
        @param share_percentage: approximate proportion of requests to
        be shared. 1 = 100%, 0.5 = 50%, etc..
        """

        super(ShareUsage, self).__init__()

        self.query_whitelist = query_whitelist

        self.header_blacklist = header_blacklist

        self.datakey = "shareusage"

        self.interval = interval
        self.requested_package_size = requested_package_size
        self.cookie = cookie
        self.share_percentage = share_percentage
        self.endpoint = endpoint
        self.request_timeout = request_timeout

        # Add the share usage tracker which detects when
        # to send up sharing data

        self.tracker = ShareUsageTracker(interval = interval)

        # Initialise share data list 
        self.share_data = []

        self.constant_xml = None

        # Reusable thread pool for sending usage in background
        # According to the doc on ThreadPoolExecutor - all threads will be joined before the interpreter can exit
        # this ensures that all the data will be sent correctly before the actual exit happens

        self.thread_pool = ThreadPoolExecutor(thread_name_prefix='ShareUsage')

    def __del__(self):
        self.thread_pool.shutdown(wait=True)

    def get_constant_xml(self):
        if self.constant_xml is None:
            coreVersion = version("fiftyone_pipeline_core")
            osVersion = f"{ReplacedString(platform.system()).result} {ReplacedString(platform.release()).result}"
            pyVersion = ReplacedString(platform.python_version()).result

            xml = ""

            # The version number of the Pipeline API
            xml += f"<Version>{coreVersion}</Version>"
            # Write Pipeline information
            # The product name
            xml += "<Product>Pipeline</Product>"
            # The flow elements in the current pipeline
            for flow_element in self.get_flow_elements():
                xml += f"<FlowElement>{flow_element}</FlowElement>"
            xml += "<Language>Python</Language>"
            # The software language version
            xml += f"<LanguageVersion>{pyVersion}</LanguageVersion>"
            # The OS name and version
            xml += f"<Platform>{osVersion}</Platform>"
            self.constant_xml = xml
        return self.constant_xml

    def get_flow_elements(self):
        if len(self.pipelines) == 1:
            list = []
            
            for flow_element in self.pipelines[0].flow_elements:
                list.append(type(flow_element).__name__)
            return list
        else:
            # This element has somehow been registered to too
            # many (or zero) pipelines.
            # This means we cannot know the flow elements that
            # make up the pipeline so a warning is logged
            # but otherwise, the system can continue as normal.
            self._log(
                "warn",
                "Share usage element registered "
                f"to {'too many' if len(self.pipelines) > 0 else 'no'}"
                " pipelines. Unable to send share usage information.")
            return []


    def get_evidence_key_filter(self):

        """!

        The share useage element comes with its own evidence
        key filter that uses the whitelists and blacklists to
        determine which evidence to share    
    
        """

        return ShareUsageEvidenceKeyFilter(
            cookie = self.cookie,
            query_whitelist = self.query_whitelist,
            header_blacklist = self.header_blacklist
        )

    def share_send_usage(self):
        """!
        Internal method to send the share usage bundle to the 51Degrees servers
        """

        share_data = self.share_data
        self.share_data = []

        data = f'<Devices version="{SHARE_USAGE_VERSION}">{"".join(share_data)}</Devices>'

        self.thread_pool.submit(self.send_thread, self.endpoint, data)

    def send_thread(self, endpoint, data):
        data = gzip.compress(bytearray(data, encoding='utf8'))

        # setting a reasonable time out and catching any exceptions
        try:
            requests.post(endpoint, headers={"Content-Encoding": "gzip", "Content-Type": "text/xml"}, data=data,
                          timeout=self.request_timeout)
        except Exception as e:
            print(e)
            self._log(
                "error",
                f"ShareUsage failed sending {len(data)} bytes of data: {e}"
            )

    def add_to_share_usage(self, data):
        """!
        Internal method which adds to the share usage bundle (generating XML)
        @type key: dict
        @param key: data value store of current evidence in FlowData
        """

        xml = ""
        
        xml += "<Device>"

        # --- write invariant data
        xml += self.get_constant_xml()

        # --- write variable data
        # The SessionID used to track a series of requests
        xml += f"<SessionId>{data.session_id}</SessionId>"
        # The sequence number of the request in a series of requests.
        xml += f"<Sequence>{data.sequence}</Sequence>"
        # The client IP of the request
        xml += f"<ClientIP>{data.client_ip}</ClientIP>"

        # The UTC date/time this entry was written
        date = datetime.datetime.now().isoformat() 
        xml += f"<DateSent>{date}</DateSent>"

        # Write all other evidence data that has been included.
        for category_key, category_value in data.evidence_data.items():
            for entry_key, entry_value in category_value.items():
                replaced_string = ReplacedString(entry_value)
                # Write start element
                if len(category_key) > 0:
                    xml += f"<{category_key} Name=\"{entry_key}\""
                else:
                    xml += f"<{entry_key}"
                # Write any attributes
                if replaced_string.replaced:
                    xml += ' replaced="true"'
                if replaced_string.truncated:
                    xml += ' truncated="true"'
                # End the start element
                xml += ">"
                # Write the value
                xml += replaced_string.result
                # Write end element
                if len(category_key) > 0:
                    xml += f"</{category_key}>"
                else:
                    xml += f"</{entry_key}>"
        
        xml += "</Device>"
 
        self.share_data.append(xml)

        # Send share usage data if data size greater than requested
        # package size
        if len(self.share_data) >= self.requested_package_size:
            self.share_send_usage()

    def process_internal(self, flow_data):

        """!

        Internal process method which uses the ShareUsageTracker
        to determine whether to add usage data to a batch and adds it if necessary.
        @type flow_data: FlowData
        @param flow_data: FlowData to process

        """
        
        if random.uniform(0, 1) <= self.share_percentage:
            cachekey = self.get_evidence_key_filter().filter_evidence(flow_data.evidence.get_all())
            cachekey = json.dumps(cachekey)
            share = self.tracker.track(cachekey) 
            if share:
                self.tracker.set_cache_value(cachekey)
                self.add_to_share_usage(self.get_data_from_evidence(flow_data))

    def get_data_from_evidence(self, flow_data):
        """!    
         Creates a ShareUsageData instance populated from the evidence
         within the flow data provided.
         @param {FlowData} flowData the flow data containing the evidence to use
         @returns a new ShareUsageData instance, populated from the evidence
         provided 
        """
        data = ShareUsageData()

        for key, value in flow_data.evidence.get_all().items():
            if key == 'server.client-ip':
                # The client IP is dealt with separately for backwards
                # compatibility purposes.
                data.client_ip = value
            elif key == 'query.session-id':
                # The SessionID is dealt with separately.
                data.session_id = value
            elif key == 'query.sequence':
                # The Sequence is dealt with separately.
                try:
                    sequence = int(value)
                    data.sequence = sequence
                except:
                    self._log(
                        "error",
                        f"The value '{value}' could not be parsed to an integer.")
            else:
                # Check if we can send this piece of evidence
                if self.get_evidence_key_filter().filter_evidence_key(key):
                    data.try_add(key, value)

        return data


# a set of valid XML character values (ignoring valid controls x09, x0a, x0d, x85)
VALID_XML_CHARS = [*range(int("0x20", 16), int("0x7F", 16))]
VALID_XML_CHARS.extend(range(int("0x40", 16), int("0x100", 16)))

def get_is_valid_char_map():
  maxChar = int('0x100', 16)
  isValidChar = {}
  for c in range(maxChar):
    isValidChar[c] = c in VALID_XML_CHARS
  return isValidChar

# an array describing whether a character value is valid
IS_VALID_XML_CHAR = get_is_valid_char_map()


class ReplacedString:
    """!
    replace characters that cause problems in XML with the "Replacement character"
    """
    def __init__(self, text):
        self.result = ""
        self.replaced = False
        self.truncated = False
        if text:
            escapedText = text\
                .replace('&', '&amp;')\
                .replace('"', '&quot;')\
                .replace('\'', '&apos;')\
                .replace('<', '&lt;')\
                .replace('>', '&gt;')

            length = min(len(escapedText), SHARE_USAGE_MAX_EVIDENCE_LENGTH)
            self.truncated = len(escapedText) > SHARE_USAGE_MAX_EVIDENCE_LENGTH
            self.result = "".join(map(self.map_char, list(escapedText[0:length])))


    def map_char(self, char):
        charV = ord(char)
        if charV < len(IS_VALID_XML_CHAR) and IS_VALID_XML_CHAR[charV]:
            return char
        else:
            self.replaced = True
            return chr(int("0xFFFD", 16))

class ShareUsageData:
    """!
    Internal class that is used to store details of data in memory
    prior to it being sent to 51Degrees.
    """

    def __init__(self):
        self.evidence_data = {}
        self.session_id = ""
        self.client_ip = ""
        self.sequence = ""

    def try_add(self, key, value):
        # Get the category and field names from the evidence key.
        category = ""
        field = key

        first_separator = key.index(".")
        if first_separator > 0:
            category = key[0:first_separator]
            field = key[first_separator + 1:len(key)]

        # Add the evidence to the dictionary.
        if category in self.evidence_data:
            category_dict = self.evidence_data[category]
        else:
            category_dict = {}
            self.evidence_data[category] = category_dict

        category_dict[field] = value
