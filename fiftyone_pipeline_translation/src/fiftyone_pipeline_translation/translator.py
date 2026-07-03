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

from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue

from .missing_translation_behavior import MissingTranslationBehavior


class Translator:

    """!
    Translates values based on a set of translations. The result is the same
    type as the source, for example a string is translated to a string, a list
    of strings to a list of strings and a weighted list of strings (a list of
    {"value", "weighting"} dictionaries) to a weighted list of strings with the
    weightings preserved.

    For AspectPropertyValue inputs, if the value has no value then the no-value
    message is copied to the result.
    """

    def __init__(
            self,
            translations=None,
            behavior=MissingTranslationBehavior.ORIGINAL):

        """!
        Constructor.

        @type translations: dict
        @param translations: Map of source value to translated value. Lookups
        are case-insensitive.

        @type behavior: MissingTranslationBehavior
        @param behavior: Behavior when a translation is missing for a value.
        """

        translations = translations or {}
        # Store with lower-cased keys so lookups are case-insensitive.
        self._translations = {
            str(key).lower(): value for key, value in translations.items()}
        self._behavior = behavior

    def translate(self, value, errors=None):

        """!
        Translate the value to the language this translator is configured for.

        @param value: Value to translate (string, list of strings, weighted
        list, or an AspectPropertyValue wrapping any of those).

        @type errors: list
        @param errors: List that any errors encountered are appended to.

        @return: The translated value, matching the shape of the input.
        """

        if errors is None:
            errors = []

        if isinstance(value, AspectPropertyValue):
            if value.has_value():
                return AspectPropertyValue(
                    value=self._translate_inner(value.value(), errors))
            return AspectPropertyValue(
                no_value_message=value.no_value_message())

        return self._translate_inner(value, errors)

    def _translate_inner(self, value, errors):
        if isinstance(value, str):
            return self._translate_string(value, errors)
        if isinstance(value, list):
            if value and all(
                    isinstance(item, dict) and "value" in item
                    for item in value):
                # Weighted list of {"value", "weighting"} dictionaries.
                return [
                    self._translate_weighted(item, errors) for item in value]
            # Plain list of strings (or an empty list).
            return [self._translate_string(item, errors) for item in value]

        raise TypeError(
            f"The value type '{type(value).__name__}' is not supported "
            f"for translation.")

    def _translate_weighted(self, item, errors):
        # Copy the weighted value so the weighting (and any other keys) are
        # preserved unchanged and only the value is translated.
        result = dict(item)
        result["value"] = self._translate_string(item["value"], errors)
        return result

    def _translate_string(self, value, errors):
        result = self._translations.get(str(value).lower())
        if result is not None and str(result).strip() != "":
            return result

        if self._behavior == MissingTranslationBehavior.EMPTY_STRING:
            return ""
        if self._behavior == MissingTranslationBehavior.FLOW_ERROR:
            errors.append(KeyError(
                f"There was no translation found for the value '{value}'."))
            return None
        # MissingTranslationBehavior.ORIGINAL (default).
        return value
