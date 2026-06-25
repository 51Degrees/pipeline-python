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

import yaml

from fiftyone_pipeline_core.flowelement import FlowElement
from fiftyone_pipeline_core.elementdata_dictionary import ElementDataDictionary
from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue
from fiftyone_pipeline_core.basiclist_evidence_keyfilter import (
    BasicListEvidenceKeyFilter)
from fiftyone_pipeline_core.flowerror import FlowError

from .languages import Languages, validate_locale
from .translator import Translator
from .missing_translation_behavior import MissingTranslationBehavior


class TranslationEngineBase(FlowElement):

    """!
    Flow element that translates values from a single source element and stores
    the translated values under its own element data key.

    Translations are provided as YAML format strings keyed on file name, where
    the file name defines the language contained in the file (for example
    "countries.fr_FR.yml"). Only string based types are supported for
    translation, e.g. a string, a list of strings or a weighted list of
    strings; the type of the output property matches the input.

    The language to translate to is either fixed (set in the constructor) or
    resolved from the evidence, looking through the evidence keys defined in
    EVIDENCE_KEYS in precedence order.
    """

    # The evidence keys checked, in precedence order, for the locale code of
    # the language to translate to.
    EVIDENCE_KEYS = [
        "query.translation",
        "query.accept-language",
        "header.accept-language",
    ]

    def __init__(
            self,
            source_element_data_key,
            translations,
            sources,
            fixed_language=None,
            behavior=MissingTranslationBehavior.ORIGINAL):

        """!
        Constructor.

        @type source_element_data_key: string
        @param source_element_data_key: Element data key of the source element.

        @type translations: list
        @param translations: List of (source_property, destination_property)
        name pairs to translate.

        @type sources: dict
        @param sources: Translation sources as YAML format strings keyed on
        file name.

        @type fixed_language: string
        @param fixed_language: Fixed language to translate to. If set the engine
        always translates to this language, otherwise the language is resolved
        from the evidence.

        @type behavior: MissingTranslationBehavior
        @param behavior: Behavior when a translation is missing for a value.
        """

        super().__init__()

        if not translations:
            raise ValueError(
                "At least one property translation must be configured.")
        if not sources:
            raise ValueError("At least one source file must be configured.")
        if not source_element_data_key or not source_element_data_key.strip():
            raise ValueError("The source element key must be configured.")

        self.datakey = "translation"
        self.source_element_data_key = source_element_data_key.strip()
        self._behavior = behavior
        self._empty_translator = Translator({}, behavior)
        self._fixed_language = (
            validate_locale(fixed_language) if fixed_language else None)
        self._translation_properties = list(translations)
        self._languages = self._parse_sources(sources, behavior)
        self._evidence_filter = BasicListEvidenceKeyFilter(self.EVIDENCE_KEYS)

        # Advertise the destination properties.
        self.properties = {}
        for _source, destination in self._translation_properties:
            self.properties[destination] = {"type": "object"}

    def get_evidence_key_filter(self):
        return self._evidence_filter

    @staticmethod
    def _parse_sources(sources, behavior):

        """!
        Parse the YAML source strings into a Languages instance containing a
        Translator for each file.
        """

        languages = Languages()
        for name, content in sources.items():
            locale = TranslationEngineBase._get_language_name(name)
            translations = yaml.safe_load(content) or {}
            languages.add_language(locale, Translator(translations, behavior))
        return languages

    @staticmethod
    def _get_language_name(name):

        """!
        Get the language locale code from the source file name, for example
        "countries.fr_FR.yml" yields "fr_FR".
        """

        if not name or not name.strip():
            raise ValueError("Source name cannot be None or whitespace.")
        parts = name.split(".")
        if len(parts) < 3:
            raise ValueError(
                f"Source name '{name}' does not have the correct format. It "
                f"should be 'somename.locale.yml' e.g. 'countries.en_GB.yml'.")
        locale = validate_locale(parts[-2])
        if locale is None:
            raise ValueError(
                f"Source name '{name}' does not contain a valid locale code.")
        return locale

    def process_internal(self, flowdata):

        element_data = self._create_element_data(flowdata)
        flowdata.set_element_data(element_data)

        source_data = self._get_source_data(flowdata)
        if source_data is None:
            self._populate_missing_source(element_data)
            return True

        translator, _locale = self._resolve_translator(flowdata)
        if translator is None:
            translator = self._empty_translator

        self._populate(source_data, translator, element_data, flowdata)
        return True

    def _create_element_data(self, flowdata):
        return ElementDataDictionary(self, {})

    def _get_source_data(self, flowdata):
        try:
            return flowdata.get(self.source_element_data_key)
        except Exception:
            return None

    def _get_target_language(self, flowdata):

        """!
        Find the highest precedence evidence value that holds a language to
        translate to, or the fixed language if one is configured.
        """

        if self._fixed_language is not None:
            return self._fixed_language

        evidence = flowdata.evidence.get_all()
        # Evidence keys are matched case-insensitively.
        lowered = {str(key).lower(): value for key, value in evidence.items()}
        for key in self.EVIDENCE_KEYS:
            value = lowered.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    def _resolve_translator(self, flowdata):

        """!
        Resolve the translator and matched locale for the language found in the
        evidence (or the fixed language). Returns a (translator, locale) tuple;
        either element is None when no translation applies (for example when
        the language is English or unknown).
        """

        language = self._get_target_language(flowdata)
        if language is None:
            return None, None
        result = self._languages.try_get_translator(language)
        if result is None:
            return None, None
        return result

    def _populate(self, source_data, translator, element_data, flowdata):
        for source, destination in self._translation_properties:
            source_value = self._get_source_value(source_data, source)
            if source_value is None:
                element_data.contents[destination.lower()] = (
                    AspectPropertyValue(
                        no_value_message=(
                            f"The source property '{source}' could not be "
                            f"found in the source data.")))
            else:
                errors = []
                element_data.contents[destination.lower()] = (
                    translator.translate(source_value, errors))
                for error in errors:
                    flowdata.set_error(
                        FlowError(self.datakey, error, str(error)))

    def _populate_missing_source(self, element_data):
        message = (
            f"The source data '{self.source_element_data_key}' could not be "
            f"found in the FlowData.")
        for _source, destination in self._translation_properties:
            element_data.contents[destination.lower()] = AspectPropertyValue(
                no_value_message=message)

    @staticmethod
    def _get_source_value(source_data, source_property):
        if source_data is None or not source_property:
            return None
        try:
            return source_data.get(source_property)
        except Exception:
            return None
