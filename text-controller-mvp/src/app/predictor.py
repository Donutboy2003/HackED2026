"""Frequency-ranked, context-aware word prediction using n-gram CSVs."""

import csv
from collections import defaultdict


class PredictiveText:
    def __init__(
        self,
        unigram_path: str = "data/1grams_english.csv",
        bigram_path: str = "data/2grams_english.csv",
        trigram_path: str = "data/3grams_english.csv",
        quadrigram_path: str = "data/4grams_english.csv",
        pentagram_path: str = "data/5grams_english.csv",
    ):
        # List of (word,) tuples sorted by frequency — for prefix fallback
        self.unigrams: list[str] = []

        # { "word1": ["word2a", "word2b", ...] }  (pre-sorted by freq)
        self.bigrams: dict[str, list[str]] = defaultdict(list)

        # { ("word1", "word2"): ["word3a", "word3b\", ...] }  (pre-sorted by freq)
        self.trigrams: dict[tuple[str, str], list[str]] = defaultdict(list)

        # { ("word1", "word2", "word3"): ["word4a", "word4b\", ...] }  (pre-sorted by freq)
        self.quadrigrams: dict[tuple[str, str, str], list[str]] = defaultdict(list)

        # { ("word1", "word2", "word3", "word4"): ["word5a", "word5b\", ...] }  (pre-sorted by freq)
        self.pentagrams: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)

        self._load_unigrams(unigram_path)
        self._load_bigrams(bigram_path)
        self._load_trigrams(trigram_path)
        self._load_quadrigrams(quadrigram_path)
        self._load_pentagrams(pentagram_path)

    # ------------------------------------------------------------------ #
    #  Loaders                                                             #
    # ------------------------------------------------------------------ #

    def _load_unigrams(self, path: str) -> None:
        """Load 1-grams; orgtre CSV has columns: ngram, freq, cumshare[, en]"""
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    word = row["ngram"].strip().upper()
                    if word:
                        self.unigrams.append(word)
        except FileNotFoundError:
            self.unigrams = ["THE", "AND", "YOU", "THAT", "WAS",
                             "FOR", "ARE", "WITH", "THIS", "HAVE"]

    def _load_bigrams(self, path: str) -> None:
        """Load 2-grams; orgtre CSV has columns: ngram, freq"""
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parts = row["ngram"].strip().upper().split()
                    if len(parts) == 2:
                        w1, w2 = parts
                        self.bigrams[w1].append(w2)
        except FileNotFoundError:
            pass

    def _load_trigrams(self, path: str) -> None:
        """Load 3-grams; orgtre CSV has columns: ngram, freq"""
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parts = row["ngram"].strip().upper().split()
                    if len(parts) == 3:
                        w1, w2, w3 = parts
                        self.trigrams[(w1, w2)].append(w3)
        except FileNotFoundError:
            pass

    def _load_quadrigrams(self, path: str) -> None:
        """Load 4-grams; orgtre CSV has columns: ngram, freq"""
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parts = row["ngram"].strip().upper().split()
                    if len(parts) == 4:
                        w1, w2, w3, w4 = parts
                        self.quadrigrams[(w1, w2, w3)].append(w4)
        except FileNotFoundError:
            pass

    def _load_pentagrams(self, path: str) -> None:
        """Load 5-grams; orgtre CSV has columns: ngram, freq"""
        try:
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    parts = row["ngram"].strip().upper().split()
                    if len(parts) == 5:
                        w1, w2, w3, w4, w5 = parts
                        self.pentagrams[(w1, w2, w3, w4)].append(w5)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------ #
    #  Prediction                                                          #
    # ------------------------------------------------------------------ #

    def get_suggestions(
        self,
        current_input: str,
        context: str = "",
        max_results: int = 3,
    ) -> tuple[list[str], str, str]:
        """
        Return suggestions plus debug info about which n-gram level was used.

        Returns:
            (suggestions, level, context_words) where:
              - level        is "3G", "2G", "1G", or "—"
              - context_words is the word(s) used as the lookup key, or ""
        """
        prefix = current_input.strip().upper()
        prev_words = context.strip().upper().split() if context.strip() else []

        candidates: list[str] = []
        level = "—"
        context_words = ""

        # --- 1. Try pentagram context (last 4 words known) -----------------
        if len(prev_words) >= 4 and self.pentagrams:
            key = (prev_words[-4], prev_words[-3], prev_words[-2], prev_words[-1])
            hits = self._filter_by_prefix(self.pentagrams.get(key, []), prefix)
            if hits:
                candidates = hits
                level = "5G"
                context_words = f"{prev_words[-4]} {prev_words[-3]} {prev_words[-2]} {prev_words[-1]}"

        # --- 2. Try quadrigram context (last 3 words known) -----------------
        if len(candidates) < max_results and len(prev_words) >= 3 and self.quadrigrams:
            key = (prev_words[-3], prev_words[-2], prev_words[-1])
            hits = self._filter_by_prefix(self.quadrigrams.get(key, []), prefix)
            if hits:
                candidates = hits
                level = "4G"
                context_words = f"{prev_words[-3]} {prev_words[-2]} {prev_words[-1]}"

        # --- 3. Try trigram context (last 2 words known) -----------------
        if len(candidates) < max_results and len(prev_words) >= 2 and self.trigrams:
            key = (prev_words[-2], prev_words[-1])
            hits = self._filter_by_prefix(self.trigrams.get(key, []), prefix)
            if hits:
                candidates = hits
                level = "3G"
                context_words = f"{prev_words[-2]} {prev_words[-1]}"

        # --- 4. Fall back to bigram context (last word known) -------------
        if len(candidates) < max_results and prev_words and self.bigrams:
            key = prev_words[-1]
            extra = self._filter_by_prefix(self.bigrams.get(key, []), prefix)
            candidates = self._merge(candidates, extra)
            if level == "—" and extra:
                level = "2G"
                context_words = prev_words[-1]

        # --- 5. Fall back to unigram prefix matching ----------------------
        if len(candidates) < max_results:
            extra = self._filter_by_prefix(self.unigrams, prefix)
            candidates = self._merge(candidates, extra)
            if level == "—" and extra:
                level = "1G"
                context_words = prefix or "—"

        # --- 6. Last resort: most common words ----------------------------
        if not candidates:
            candidates = self.unigrams[:max_results]
            level = "1G"
            context_words = "—"

        return candidates[:max_results], level, context_words

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _filter_by_prefix(words: list[str], prefix: str) -> list[str]:
        if not prefix:
            return list(words)
        return [w for w in words if w.startswith(prefix)]

    @staticmethod
    def _merge(primary: list[str], secondary: list[str]) -> list[str]:
        seen = set(primary)
        return primary + [w for w in secondary if w not in seen]
