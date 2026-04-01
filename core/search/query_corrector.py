"""Typo-tolerant query correction — like ChatGPT/Claude intent understanding.

Uses edit-distance matching against the indexed filename vocabulary
to silently auto-correct typos before search. The corrected query is
used alongside the original to maximize recall.

Example: "hwllo" → finds "hello.pdf" because edit distance is 1.
"""
import re
from difflib import SequenceMatcher
from typing import Optional, List, Tuple
from app.logger import logger


# ── QWERTY adjacency map for keyboard-aware correction ──────
_QWERTY = {
    'q': 'wa', 'w': 'qeas', 'e': 'wrds', 'r': 'etdf', 't': 'ryfg',
    'y': 'tugh', 'u': 'yijh', 'i': 'uojk', 'o': 'iplk', 'p': 'ol',
    'a': 'qwsz', 's': 'awedxz', 'd': 'serfcx', 'f': 'drtgvc',
    'g': 'ftyhbv', 'h': 'gyujnb', 'j': 'huikmn', 'k': 'jiolm',
    'l': 'kop', 'z': 'asx', 'x': 'zsdc', 'c': 'xdfv',
    'v': 'cfgb', 'b': 'vghn', 'n': 'bhjm', 'm': 'njk',
}


def _edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _keyboard_distance(c1: str, c2: str) -> float:
    """Returns 0.5 if keys are adjacent on QWERTY, 1.0 otherwise."""
    c1, c2 = c1.lower(), c2.lower()
    if c1 == c2:
        return 0.0
    if c2 in _QWERTY.get(c1, ''):
        return 0.5
    return 1.0


class QueryCorrector:
    """Builds a vocabulary from indexed filenames and corrects typos.

    Works like ChatGPT: silently understands what you meant, returns
    relevant results without asking "Did you mean...?"
    """

    def __init__(self):
        self._vocab: set = set()
        self._word_freq: dict = {}  # word -> frequency count

    def build_vocab(self, filenames: List[str]):
        """Build vocabulary from indexed filenames.

        Splits filenames into words: "hello_world.pdf" -> {"hello", "world", "pdf"}
        """
        self._vocab.clear()
        self._word_freq.clear()

        for name in filenames:
            # Strip extension for word extraction
            base = name.rsplit('.', 1)[0] if '.' in name else name
            # Split on common separators
            words = re.split(r'[_\-.\s\(\)\[\]]+', base.lower())
            for w in words:
                if len(w) >= 2:
                    self._vocab.add(w)
                    self._word_freq[w] = self._word_freq.get(w, 0) + 1

        logger.info(f"QueryCorrector: vocabulary built with {len(self._vocab)} words")

    def correct_query(self, query: str) -> Tuple[str, bool]:
        """Correct typos in query using the filename vocabulary.

        Returns (corrected_query, was_corrected).
        Uses a combination of edit distance and keyboard adjacency for
        intelligent correction — like how ChatGPT understands "hwllo" as "hello".
        """
        if not self._vocab:
            return query, False

        words = query.lower().split()
        corrected_words = []
        any_corrected = False

        for word in words:
            if len(word) < 2:
                corrected_words.append(word)
                continue

            # Already in vocabulary — no correction needed
            if word in self._vocab:
                corrected_words.append(word)
                continue

            # Find best match using weighted edit distance
            best_match = None
            best_score = float('inf')
            max_dist = max(1, len(word) // 3)  # Allow ~1 error per 3 chars

            for vocab_word in self._vocab:
                # Quick length check — skip if too different
                if abs(len(vocab_word) - len(word)) > max_dist:
                    continue

                dist = _edit_distance(word, vocab_word)
                if dist > max_dist:
                    continue

                # Weight by keyboard adjacency for more natural correction
                kbd_penalty = 0.0
                for i, (c1, c2) in enumerate(zip(word, vocab_word)):
                    if c1 != c2:
                        kbd_penalty += _keyboard_distance(c1, c2)

                # Combined score: edit distance + keyboard weight + frequency bonus
                freq_bonus = min(0.3, self._word_freq.get(vocab_word, 0) / 100.0)
                score = dist + kbd_penalty * 0.3 - freq_bonus

                if score < best_score:
                    best_score = score
                    best_match = vocab_word

            if best_match and best_match != word:
                corrected_words.append(best_match)
                any_corrected = True
                logger.info(f"Typo corrected: '{word}' → '{best_match}' (score={best_score:.2f})")
            else:
                corrected_words.append(word)

        corrected = ' '.join(corrected_words)
        return corrected, any_corrected


# ── Singleton ────────────────────────────────────────────────
_corrector: Optional[QueryCorrector] = None


def get_corrector() -> QueryCorrector:
    global _corrector
    if _corrector is None:
        _corrector = QueryCorrector()
    return _corrector
