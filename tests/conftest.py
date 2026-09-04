"""Test configuration.

``DATABASE_URL`` must be set before anything imports ``app.db``, because the
engine is created at import time. Setting it here — at collection, above the
test modules — is what keeps the suite off any real database.
"""

import os
import tempfile

_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="exercises-tests-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
# The suite makes far more requests per minute than a real client ever would.
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["AUTH_RATE_LIMIT_PER_MINUTE"] = "100000"
