from __future__ import annotations

import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nadikt.domain.dictation import DictationOutcomeCode, DictationSession, InvalidDictationTransition


class DictationSessionTest(unittest.TestCase):
    def test_completed_delivery_clears_retained_transcript(self) -> None:
        session = DictationSession(session_id="session-1")
        session.begin_capture()
        session.begin_recognition(segment_count=1)
        session.retain_final_transcript("SECRET_TRANSCRIPT", segment_count=1)
        session.begin_normalization()
        session.begin_insertion()

        session.complete_delivery()

        self.assertFalse(session.has_retained_result)
        self.assertNotIn("SECRET_TRANSCRIPT", repr(session))

    def test_failed_session_retains_result_until_cancelled(self) -> None:
        session = DictationSession(session_id="session-2")
        session.begin_capture()
        session.begin_recognition(segment_count=1)
        session.retain_partial_transcript("SECRET_PARTIAL", segment_count=1)

        failure = session.fail(DictationOutcomeCode.RECOGNITION_FAILED)

        self.assertTrue(failure.retained_result)
        self.assertTrue(session.has_retained_result)
        self.assertNotIn("SECRET_PARTIAL", repr(session))
        session.cancel()
        self.assertFalse(session.has_retained_result)

    def test_double_insertion_is_rejected(self) -> None:
        session = DictationSession(session_id="session-3")
        session.begin_capture()
        session.begin_recognition(segment_count=1)
        session.retain_final_transcript("text", segment_count=1)
        session.begin_normalization()
        session.begin_insertion()

        with self.assertRaises(InvalidDictationTransition) as context:
            session.begin_insertion()

        self.assertEqual(DictationOutcomeCode.DOUBLE_INSERTION, context.exception.failure.code)


if __name__ == "__main__":
    unittest.main()
