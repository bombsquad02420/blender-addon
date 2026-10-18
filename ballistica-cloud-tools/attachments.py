"""Attachment rules and JSON conversion (pure Python).

An attachment in a `.bchar` (characterbuilder.BuilderAttachment):

	{"target": "head", "side": "both", "kind": "antenna_2",
	 "transform": {"translate": [x, y, z], "rotate": [h, p, r]},
	 "stiffness": 0.5, ..., "stiffness_change": 0.0, ...,
	 "segments": [{"mesh": "...", "texture": "...", "mask_texture": "...",
	               "transform": {...}}, ...]}

Records here are flat dicts with every modelled value filled in (defaults
where absent). `to_json` writes a record back over the attachment's
original JSON the way `bchar.Character.set` does: a value absent before
and still at its default isn't written, and unknown keys are kept, so an
untouched attachment round-trips byte for byte.
"""

import copy

from . import rig

TUNING = ('stiffness', 'damping', 'drag', 'curl', 'length', 'radius')
TUNING_CHANGES = ('curl_change', 'length_change', 'radius_change', 'stiffness_change', 'damping_change')
SEGMENT_REFS = ('mesh', 'texture', 'mask_texture')
ZERO3 = (0.0, 0.0, 0.0)
ONE3 = (1.0, 1.0, 1.0)

LIMB_TARGETS = ('upper_arm', 'forearm', 'hand', 'upper_leg', 'lower_leg', 'toes', 'wing')


# ---- rules (characterbuilder docstrings) ----

def allowed_sides(target):
	"""Head, torso and pelvis are single parts: only 'both'."""
	return ('both',) if target in rig.UNSIDED_TARGETS else rig.ATTACH_SIDES


def allowed_kinds(target):
	"""Limbs and wings take static attachments only."""
	return ('static',) if target in LIMB_TARGETS else rig.ATTACH_KINDS


def segment_count(kind):
	return rig.ATTACHMENT_SEGMENTS.get(kind, 1)


def is_springy(kind):
	return kind != 'static'


def problems(record, index=0):
	"""Human-readable rule violations for one attachment record."""
	where = f"Attachment {index + 1}"
	out = []
	if record['target'] not in rig.ATTACH_TARGETS:
		out.append(f"{where}: unknown target '{record['target']}'")
		return out
	if record['side'] not in allowed_sides(record['target']):
		out.append(f"{where}: side '{record['side']}' isn't allowed on {record['target']} (only 'both')")
	if record['kind'] not in allowed_kinds(record['target']):
		out.append(f"{where}: kind '{record['kind']}' isn't allowed on {record['target']} (only 'static')")
	expected = segment_count(record['kind'])
	if len(record['segments']) != expected:
		out.append(f"{where}: {record['kind']} needs {expected} segment(s), has {len(record['segments'])}")
	for j, segment in enumerate(record['segments']):
		if not segment['mesh']:
			out.append(f"{where}, segment {j + 1}: no mesh")
	return out


def fix(record):
	"""Make a record valid in place: legal side and kind, right segment count."""
	if record['side'] not in allowed_sides(record['target']):
		record['side'] = allowed_sides(record['target'])[0]
	if record['kind'] not in allowed_kinds(record['target']):
		record['kind'] = allowed_kinds(record['target'])[0]
	expected = segment_count(record['kind'])
	segments = record['segments']
	del segments[expected:]
	while len(segments) < expected:
		previous = segments[-1] if segments else None
		segments.append(new_segment(previous['mesh'] if previous else ''))
	return record


# ---- records ----

def new_segment(mesh=''):
	return {'mesh': mesh, 'texture': '', 'mask_texture': '', 'translate': ZERO3, 'rotate': ZERO3, 'scale': ONE3}


def new_attachment(target='head', kind='antenna', mesh=''):
	record = {'target': target, 'side': 'both', 'kind': kind, 'translate': ZERO3, 'rotate': ZERO3}
	for key in TUNING + TUNING_CHANGES:
		record[key] = rig.ATTACHMENT_DEFAULTS[key]
	record['segments'] = [new_segment(mesh) for _ in range(segment_count(kind))]
	return record


def from_json(raw):
	"""A full record (defaults filled in) from an attachment's JSON."""
	transform = raw.get('transform') or {}
	record = {
		'target': raw.get('target', 'head'),
		'side': raw.get('side', rig.ATTACHMENT_DEFAULTS['side']),
		'kind': raw.get('kind', 'static'),
		'translate': tuple(transform.get('translate', ZERO3)),
		'rotate': tuple(transform.get('rotate', ZERO3)),
	}
	for key in TUNING + TUNING_CHANGES:
		record[key] = raw.get(key, rig.ATTACHMENT_DEFAULTS[key])
	record['segments'] = []
	for segment in raw.get('segments', []):
		seg_transform = segment.get('transform') or {}
		record['segments'].append({
			'mesh': segment.get('mesh', ''),
			'texture': segment.get('texture', ''),
			'mask_texture': segment.get('mask_texture', ''),
			'translate': tuple(seg_transform.get('translate', ZERO3)),
			'rotate': tuple(seg_transform.get('rotate', ZERO3)),
			'scale': tuple(seg_transform.get('scale', ONE3)),
		})
	return record


def to_json(record, original=None):
	"""The attachment's JSON: `original` with the record's values applied."""
	out = copy.deepcopy(original) if original else {}
	_put(out, 'target', record['target'], None)
	_put(out, 'kind', record['kind'], None)
	_put(out, 'side', record['side'], rig.ATTACHMENT_DEFAULTS['side'])
	_put_transform(out, record, scale=False)
	for key in TUNING + TUNING_CHANGES:
		_put(out, key, _num(record[key]), rig.ATTACHMENT_DEFAULTS[key])
	old_segments = out.get('segments', [])
	segments = []
	for j, segment in enumerate(record['segments']):
		seg = copy.deepcopy(old_segments[j]) if j < len(old_segments) else {}
		for key in SEGMENT_REFS:
			if segment[key]:
				seg[key] = segment[key]
			else:
				seg.pop(key, None)
		_put_transform(seg, segment, scale=True)
		segments.append(seg)
	out['segments'] = segments
	return out


def _put_transform(out, values, scale):
	"""Write translate/rotate(/scale) into `out['transform']` by the set rules."""
	transform = dict(out.get('transform') or {})
	_put(transform, 'translate', _vec(values['translate']), ZERO3)
	_put(transform, 'rotate', _vec(values['rotate']), ZERO3)
	if scale:
		_put(transform, 'scale', _vec(values['scale']), ONE3)
	if transform:
		out['transform'] = transform
	else:
		out.pop('transform', None)


def _put(out, key, value, default):
	"""Set `key`, but leave it out if it was absent and is still the default."""
	if default is not None and key not in out and _same(value, default):
		return
	out[key] = value


def _vec(v):
	return [_num(c) for c in v]


def _num(value):
	if isinstance(value, bool) or not isinstance(value, float):
		return value
	rounded = round(value, 6)
	return 0.0 if rounded == 0 else rounded


def _same(a, b):
	if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
		return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
	if isinstance(a, (int, float)) and isinstance(b, (int, float)):
		return abs(a - b) < 1e-6
	return a == b
