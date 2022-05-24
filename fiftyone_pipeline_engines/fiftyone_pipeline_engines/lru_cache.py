# *********************************************************************
# This Original Work is copyright of 51 Degrees Mobile Experts Limited.
# Copyright 2022 51 Degrees Mobile Experts Limited, Davidson House,
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

from .datakeyed_cache import DataKeyedCache

from cachetools import LRUCache

class LRUEngineCache(DataKeyedCache):
    """!
     An instance of DataKeyed cache using a least recently used (LRU) method
    """
    def __init__(self, size = 1000):
        """!
        Constructor for LRUCache
        @type size: int
        @param size: maximum entries in the cache
        """

        self.cache = LRUCache(maxsize=size)

    def get_cache_value (self, cache_key):

        return self.cache.get(cache_key)

    def set_cache_value(self, key, value):
        self.cache.__setitem__(key, value)
