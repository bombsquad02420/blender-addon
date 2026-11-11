"""The ClassicCharacterAssets sample workspace, fresh for every test run.

It comes from a zip that's never edited (tests/fixtures/ClassicCharacterAssets.zip,
not in git; set BCT_SAMPLE_ZIP to use another), extracted into a temporary
folder that's deleted when the run ends. So tests never see hand edits, and
nothing has to be restored.
"""

import atexit
import os
import shutil
import tempfile
import zipfile

ZIP = os.environ.get('BCT_SAMPLE_ZIP') or os.path.join(os.path.dirname(__file__), 'fixtures', 'ClassicCharacterAssets.zip')
MISSING = f"sample workspace zip not found ({ZIP})"
_extracted = []


def path():
	"""The extracted workspace folder, or None if there's no zip."""
	if not _extracted and os.path.isfile(ZIP):
		folder = tempfile.mkdtemp(prefix='bct-sample-')
		atexit.register(shutil.rmtree, folder, True)
		with zipfile.ZipFile(ZIP) as archive:
			archive.extractall(folder)
		_extracted.append(folder)
	return _extracted[0] if _extracted else None
