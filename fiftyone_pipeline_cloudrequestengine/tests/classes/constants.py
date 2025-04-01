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


class Constants():
    # expectedUrl = "https://cloud.51degrees.com/api/v4/resource_key.json"
    resourceKey = "resource_key"
    userAgent = "iPhone"
    jsonResponse = '{"device":{"value": 1}}'
    evidenceKeysResponse = '["query.User-Agent"]'
    accessiblePropertiesResponse = \
           {'Products': {'device': {'DataTier': 'tier','Properties': [{'Name': 'value','Type': 'String','Category': 'Device'}]}}}
    accessiblePropertiesResponseCode = 200
    invalidKey = "invalidkey"
    invalidKeyMessage = "58982060: " + invalidKey + " not a valid resource key"
    invalidKeyResponse = { 'errors':[ invalidKeyMessage ]}
    invalidKeyMessageComplete = "Error returned from 51Degrees cloud service: '[\"" + invalidKeyMessage + "\"]'"
    noDataKey = "nodatakey"
    noDataKeyResponse = {}
    noDataKeyMessageComplete = "Error returned from 51Degrees cloud service: 'No data in response " + \
        "from cloud service at https://cloud.51degrees.com/api/v4/accessibleProperties?resource=nodatakey'"
    noErrorNoSuccessKey = "noErrorNoSuccessKey"
    noErrorNoSuccessResponse = {'device': {'value': 'abc'}}
    noErrorNoSuccessMessage= "Error returned from 51Degrees cloud service: 'Cloud service at 'https://cloud.51degrees.com/api/v4/' returned status code '400' with content {'device': {'value': 'abc'}}'"
    accessibleSubPropertiesResponse = \
            { \
                'Products': { \
                    'device': { \
                        'DataTier': 'CloudV4TAC', \
                        'Properties': [ \
                            { \
                                'Name': 'IsMobile', \
                                    'Type': 'Boolean', \
                                    'Category': 'Device' \
                            }, \
                            { \
                                'Name': 'IsTablet', \
                                    'Type': 'Boolean', \
                                    'Category': 'Device' \
                            } \
                        ] \
                    }, \
                    'devices': { \
                        'DataTier': 'CloudV4TAC', \
                        'Properties': [ \
                            { \
                                'Name': 'Devices', \
                                'Type': 'Array', \
                                'Category': 'Unspecified', \
                                'ItemProperties': [ \
                                    { \
                                        'Name': 'IsMobile', \
                                        'Type': 'Boolean', \
                                        'Category': 'Device' \
                                    }, \
                                    { \
                                        'Name': 'IsTablet', \
                                        'Type': 'Boolean', \
                                        'Category': 'Device' \
                                    } \
                                ] \
                            } \
                        ] \
                    } \
                } \
            }
    PRECENDENCE_WARNING = "WARNING: '{}:{}' evidence conflicts with {}:{}"
