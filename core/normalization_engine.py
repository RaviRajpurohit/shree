import logging
import re


LOGGER = logging.getLogger(__name__)


class NormalizationEngine:
    PHRASE_MAPPINGS = {
        "google chrome": "chrome",
    }
    TOKEN_MAPPINGS = {
        "chrom": "chrome",
        "calcy": "calculator",
        "clcy": "calculator",
        "clear": "cls",
        "ls": "dir",
    }

    def normalize(self, text: str) -> str:
        normalized_text = " ".join(str(text or "").strip().lower().split())

        if not normalized_text:
            LOGGER.debug("Normalization skipped because input was empty.")
            return ""

        original_text = normalized_text
        normalized_text = self._apply_phrase_mappings(normalized_text)
        normalized_text = self._apply_token_mappings(normalized_text)

        if normalized_text != original_text:
            LOGGER.info("Normalized user input from '%s' to '%s'", original_text, normalized_text)
        else:
            LOGGER.debug("Normalization made no changes for input: %s", original_text)

        return normalized_text

    def _apply_phrase_mappings(self, text):
        normalized_text = text

        for source, target in self.PHRASE_MAPPINGS.items():
            normalized_text = re.sub(
                rf"\b{re.escape(source)}\b",
                target,
                normalized_text,
            )

        return normalized_text

    def _apply_token_mappings(self, text):
        tokens = text.split()
        return " ".join(self.TOKEN_MAPPINGS.get(token, token) for token in tokens)
