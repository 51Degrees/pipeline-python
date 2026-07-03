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

import re

# Regex used to identify language locale codes in evidence, e.g. "fr_FR".
_LOCALE_REGEX = re.compile(r"[a-z]{2}_[A-Z]{2}")


def validate_locale(locale):

    """!
    Return the validated locale code found in the supplied string, or None if
    none is present. For example "countries.fr_FR" yields "fr_FR".
    """

    if not locale:
        return None
    match = _LOCALE_REGEX.search(locale)
    return match.group(0) if match else None


class Languages:

    """!
    Set of translators for one or more languages, with utility methods for
    parsing Accept-Language headers and resolving language tags against the
    available locales.
    """

    # The 2-char code of the base language that source values are already in.
    BASE_LANGUAGE = "en"

    def __init__(self):

        """!
        Constructor.
        """

        # Map of lower-cased locale -> (original locale, translator).
        self._translators = {}

    def add_language(self, language, translator):

        """!
        Add a language and its translator to the set of languages.

        @type language: string
        @param language: Locale code for the language, e.g. "en_GB", "fr_FR".

        @param translator: Translator for the language.
        """

        if language is None or translator is None:
            raise ValueError("language and translator must not be None.")
        self._translators[language.lower()] = (language, translator)

    @property
    def available_locales(self):

        """!
        The original-cased locale codes available, e.g. ["fr_FR", "de_DE"].
        """

        return [original for (original, _translator)
                in self._translators.values()]

    @staticmethod
    def parse_accept_language(accept_language):

        """!
        Parse an Accept-Language header value (e.g. "es,de-DE;q=0.8,en;q=0.5")
        into an ordered list of normalized language tags. Tags are ordered by
        quality (descending), with dashes replaced by underscores.
        """

        if not accept_language or not accept_language.strip():
            return []

        items = []
        for index, part in enumerate(accept_language.split(",")):
            part = part.strip()
            if not part:
                continue
            segments = part.split(";")
            tag = segments[0].strip().replace("-", "_")
            quality = 1.0
            for segment in segments[1:]:
                segment = segment.strip()
                if segment.lower().startswith("q="):
                    try:
                        quality = float(segment[2:])
                    except ValueError:
                        quality = 1.0
            if tag:
                # Keep the original index to make the sort stable.
                items.append((quality, index, tag))

        items.sort(key=lambda item: (-item[0], item[1]))
        return [tag for (_quality, _index, tag) in items]

    @staticmethod
    def try_resolve_locale(
            accept_language, available_locales, base_language="en"):

        """!
        Resolve an Accept-Language header value against a set of available
        locale keys, returning the best matching locale or None.

        Handles exact locale matches (e.g. "fr_FR") and 2-char language code
        fallbacks (e.g. "fr" matching "fr_FR"). If the highest-priority
        language matches the base language, resolution stops and returns None,
        because the source values are already in the base language.
        """

        available = list(available_locales)
        lower_map = {locale.lower(): locale for locale in available}

        for candidate in Languages.parse_accept_language(accept_language):
            candidate_lower = candidate.lower()

            # Try an exact match first.
            if candidate_lower in lower_map:
                return lower_map[candidate_lower]

            # No exact match. If this candidate's language is the base
            # language (e.g. "en"), the source values are already in that
            # language - stop and return None rather than falling through to a
            # lower-priority language.
            if base_language and candidate_lower.startswith(
                    base_language.lower()):
                return None

            # Try a 2-char language code fallback.
            if len(candidate) == 2:
                for locale in available:
                    if locale.lower().startswith(candidate_lower):
                        return locale

        return None

    def try_get_translator(self, language):

        """!
        Get the translator and matched locale for the supplied language tag or
        Accept-Language header value.

        @type language: string
        @param language: A locale code (e.g. "fr_FR") or a full Accept-Language
        header value (e.g. "es,de-DE;q=0.8,en;q=0.5").

        @return: A (translator, matched_locale) tuple, or None if no match.
        """

        locale = Languages.try_resolve_locale(
            language, self.available_locales, self.BASE_LANGUAGE)
        if locale is not None:
            entry = self._translators.get(locale.lower())
            if entry is not None:
                return entry[1], entry[0]
        return None
