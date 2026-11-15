"""JSON files written the way the cloud writes them.

Workspace JSON (`.bchar`, `workspace.json`) is `indent=2, sort_keys=True`.
Whether a file ends with a newline varies, so that is kept as found, and a
file whose content didn't change isn't rewritten at all.
"""

import json
import os


def read(path):
	with open(path, encoding='utf-8') as infile:
		return json.load(infile)


def dumps(data, trailing_newline=True):
	text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True)
	return text + '\n' if trailing_newline else text


def write(path, data):
	"""Write `data` to `path`; return True if the file changed."""
	old = None
	if os.path.exists(path):
		with open(path, encoding='utf-8') as infile:
			old = infile.read()
	text = dumps(data, trailing_newline=old is None or old.endswith('\n'))
	if text == old:
		return False
	os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
	tmp = f'{path}.tmp'
	with open(tmp, 'w', encoding='utf-8', newline='\n') as outfile:
		outfile.write(text)
	os.replace(tmp, path)
	return True
