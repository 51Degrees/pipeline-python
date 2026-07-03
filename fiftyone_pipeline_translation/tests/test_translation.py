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

import unittest

from fiftyone_pipeline_core.flowelement import FlowElement
from fiftyone_pipeline_core.elementdata_dictionary import ElementDataDictionary
from fiftyone_pipeline_core.aspectproperty_value import AspectPropertyValue
from fiftyone_pipeline_core.pipelinebuilder import PipelineBuilder

from fiftyone_pipeline_translation.translator import Translator
from fiftyone_pipeline_translation.languages import Languages
from fiftyone_pipeline_translation.missing_translation_behavior import (
    MissingTranslationBehavior)
from fiftyone_pipeline_translation.translation_engine_base import (
    TranslationEngineBase)


class MockSourceElement(FlowElement):

    """A flow element that exposes fixed values for testing the translation."""

    def __init__(self, datakey, contents):
        super().__init__()
        self.datakey = datakey
        self._contents = contents

    def process_internal(self, flowdata):
        flowdata.set_element_data(
            ElementDataDictionary(self, self._contents))
        return True


# A "fr_FR" style source file: English name -> French name.
FR_SOURCE = {
    "countries.fr_FR.yml": "Germany: Allemagne\nUnited Kingdom: Royaume-Uni\n"
}


class TranslatorTests(unittest.TestCase):

    def _translator(self, behavior=MissingTranslationBehavior.ORIGINAL):
        return Translator(
            {"Germany": "Allemagne", "United Kingdom": "Royaume-Uni"},
            behavior)

    def test_translate_string(self):
        self.assertEqual("Allemagne", self._translator().translate("Germany"))

    def test_translate_string_case_insensitive(self):
        self.assertEqual("Allemagne", self._translator().translate("germany"))

    def test_translate_list_of_strings(self):
        result = self._translator().translate(["Germany", "United Kingdom"])
        self.assertEqual(["Allemagne", "Royaume-Uni"], result)

    def test_translate_weighted_preserves_weighting(self):
        source = [
            {"value": "Germany", "weighting": 0.7},
            {"value": "United Kingdom", "weighting": 0.3},
        ]
        result = self._translator().translate(source)
        self.assertEqual("Allemagne", result[0]["value"])
        self.assertEqual(0.7, result[0]["weighting"])
        self.assertEqual("Royaume-Uni", result[1]["value"])
        self.assertEqual(0.3, result[1]["weighting"])

    def test_translate_aspect_property_value(self):
        wrapped = AspectPropertyValue(value=[
            {"value": "Germany", "weighting": 1.0}])
        result = self._translator().translate(wrapped)
        self.assertTrue(result.has_value())
        self.assertEqual("Allemagne", result.value()[0]["value"])

    def test_translate_aspect_property_value_no_value(self):
        wrapped = AspectPropertyValue(no_value_message="missing")
        result = self._translator().translate(wrapped)
        self.assertFalse(result.has_value())
        self.assertEqual("missing", result.no_value_message())

    def test_missing_original(self):
        self.assertEqual("Spain", self._translator().translate("Spain"))

    def test_missing_empty_string(self):
        translator = self._translator(MissingTranslationBehavior.EMPTY_STRING)
        self.assertEqual("", translator.translate("Spain"))

    def test_missing_flow_error(self):
        translator = self._translator(MissingTranslationBehavior.FLOW_ERROR)
        errors = []
        self.assertIsNone(translator.translate("Spain", errors))
        self.assertEqual(1, len(errors))


class LanguagesTests(unittest.TestCase):

    def test_parse_accept_language_orders_by_quality(self):
        result = Languages.parse_accept_language("es,de-DE;q=0.8,en;q=0.5")
        self.assertEqual(["es", "de_DE", "en"], result)

    def test_resolve_exact(self):
        self.assertEqual(
            "fr_FR",
            Languages.try_resolve_locale("fr_FR", ["fr_FR", "de_DE"]))

    def test_resolve_dash(self):
        self.assertEqual(
            "fr_FR",
            Languages.try_resolve_locale("fr-FR", ["fr_FR", "de_DE"]))

    def test_resolve_two_letter_fallback(self):
        self.assertEqual(
            "fr_FR",
            Languages.try_resolve_locale("fr", ["fr_FR", "de_DE"]))

    def test_resolve_english_short_circuit(self):
        self.assertIsNone(
            Languages.try_resolve_locale(
                "en-GB,fr;q=0.5", ["fr_FR", "de_DE"]))

    def test_resolve_preferred_before_lower_priority(self):
        self.assertEqual(
            "es_ES",
            Languages.try_resolve_locale(
                "es,de-DE;q=0.8,fr;q=0.5", ["es_ES", "de_DE", "fr_FR"]))

    def test_resolve_unknown_returns_none(self):
        self.assertIsNone(
            Languages.try_resolve_locale("zz-ZZ", ["fr_FR", "de_DE"]))


class TranslationEngineBaseTests(unittest.TestCase):

    def _build(self, evidence):
        source = MockSourceElement("source", {
            "Names": AspectPropertyValue(value=["Germany", "United Kingdom"])
        })
        engine = TranslationEngineBase(
            "source",
            [("Names", "NamesTranslated")],
            FR_SOURCE)
        pipeline = PipelineBuilder().add(source).add(engine).build()
        flowdata = pipeline.create_flowdata()
        for key, value in evidence.items():
            flowdata.evidence.add(key, value)
        flowdata.process()
        return flowdata.get("translation")

    def test_translates_from_evidence(self):
        result = self._build({"header.accept-language": "fr_FR"})
        translated = result.get("NamesTranslated")
        self.assertTrue(translated.has_value())
        self.assertEqual(
            ["Allemagne", "Royaume-Uni"], translated.value())

    def test_english_passthrough(self):
        result = self._build({"header.accept-language": "en-US,en;q=0.9"})
        translated = result.get("NamesTranslated")
        self.assertEqual(["Germany", "United Kingdom"], translated.value())

    def test_locale_from_filename(self):
        self.assertEqual(
            "fr_FR",
            TranslationEngineBase._get_language_name("countries.fr_FR.yml"))


if __name__ == "__main__":
    unittest.main()
