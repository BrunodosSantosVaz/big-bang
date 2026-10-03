"""Error type and stable exit codes of the `bb` CLI (workflows and scripts depend on these numbers)."""

EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_USAGE = 2
EXIT_INVALID_CONFIG = 3
EXIT_UNKNOWN_KEY = 4
EXIT_VERIFICATION_FAILED = 5
EXIT_EXTERNAL_COMMAND = 6
EXIT_INVALID_STATE = 7


class BbError(Exception):
    """An expected failure with a user-facing message (in Portuguese) and a stable exit code."""

    def __init__(self, message, code=EXIT_UNEXPECTED):
        super().__init__(message)
        self.message = message
        self.code = code
