import logging
import os
import unittest
from unittest.mock import patch

from insertion_spike.contracts import (
    ClipboardSnapshot,
    InsertionMethod,
    InsertionRequest,
    TargetToken,
    get_logger,
)


CANARY = "CANARY_sensitive_payload_7f13"


class ContractPrivacyTests(unittest.TestCase):
    def test_request_repr_excludes_text(self) -> None:
        request = InsertionRequest("request-1", CANARY, InsertionMethod.AUTO)

        rendered = repr(request)

        self.assertNotIn(CANARY, rendered)
        self.assertIn("request-1", rendered)

    def test_opaque_repr_excludes_platform_and_clipboard_state(self) -> None:
        rendered = repr(TargetToken(CANARY)) + repr(ClipboardSnapshot(CANARY))

        self.assertNotIn(CANARY, rendered)

    def test_log_level_is_configurable(self) -> None:
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            logger = get_logger()

        self.assertEqual(logging.DEBUG, logger.level)


if __name__ == "__main__":
    unittest.main()
