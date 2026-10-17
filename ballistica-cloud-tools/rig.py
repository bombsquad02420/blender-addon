"""Game data the addon needs, copied from ballistica.

The addon never reads game files at runtime, so these values are vendored.
Source: ballistica `tools/bacommon/` at commit 5cd091644 (2026-10-14):
`characterrig.py` (SPAZ_RIG), `characterranges.py` (ranges) and
`characterbuilder.py` (defaults and enums), plus the wing frame from
`src/ballistica/scene_v1/node/spaz_node.cc`. Update them together when
ballistica changes.

Coordinates are game space: Y up, Z forward, the character's right is -X.
"""

# ---- characterrig.py: SPAZ_RIG ----

HEAD_RADIUS = 0.23
PELVIS_SIZE = (0.35, 0.16, 0.1)
ROLLER_RADIUS = 0.3
UPPER_ARM_RADIUS = 0.06
UPPER_ARM_LENGTH = 0.16
LOWER_ARM_RADIUS = 0.06
LOWER_ARM_LENGTH = 0.13
UPPER_LEG_LENGTH = 0.12
LOWER_LEG_SPAN = 0.26
TOES_RADIUS = 0.075

STAND_HEAD_HEIGHT = 2.25
STAND_TORSO_HEIGHT = 1.8
STAND_PELVIS_HEIGHT = 1.66
STAND_ROLLER_HEIGHT = 1.6

PELVIS_JOINT_DROP = 0.05
PELVIS_JOINT_FORWARD = 0.05
SHOULDER_ON_TORSO = (-0.15, 0.14, 0.0)
SHOULDER_ON_UPPER_ARM = (0.02, 0.0, -0.1)
ELBOW_ON_UPPER_ARM = (0.0, 0.0, 0.07)
ELBOW_ON_LOWER_ARM = (0.0, 0.0, -0.08)
HIP_ON_PELVIS = (-0.1, -0.01, 0.0)
HIP_ON_UPPER_LEG = (0.0, 0.0, -0.05)
KNEE_ON_UPPER_LEG = (0.0, 0.0, 0.05)
KNEE_ON_LOWER_LEG = (0.0, 0.0, -0.05)
ANKLE_ON_LOWER_LEG = (0.0, 0.05, 0.05)
ANKLE_ON_TOES = (0.0, -0.04, 0.0)

FOREARM_STRETCH_PIVOT = 0.1
HAND_OFFSET = 0.04
HAND_TURN = 10.0
EYE_MESH_SCALE = 0.09
EYEBALL_PITCH = -10.0

# Wings (src/ballistica/scene_v1/node/spaz_node.cc: kWingAttach*, at rest,
# and ApplyWingTransform_). A wing's frame sits at the torso centre with
# +Z pointing from there toward this torso-space point; this is the right
# wing's, the left mirrors it.
WING_ATTACH = (-0.3, 0.0, -0.45)

# Segment counts per simulated attachment kind (characterrig.ATTACHMENT_RIGS).
ATTACHMENT_SEGMENTS = {
	'legacy_tuft_large': 1,
	'legacy_tuft_medium': 1,
	'legacy_tuft_small': 1,
	'legacy_ponytail_2': 2,
	'antenna': 1,
	'antenna_2': 2,
	'antenna_3': 3,
	'antenna_4': 4,
	'static': 1,
}

# Joint anchors of each simulated segment, first segment first:
# (parent_anchor on the previous segment, child_anchor on this one), both in
# the segment's own space. A first segment hangs from the attachment's spot.
_TUFT = ((0.0, 0.0, 0.0), (0.0, -0.08, -0.12))
_ANTENNA_ROOT = ((0.0, 0.0, 0.0), (0.0, 0.0, -0.065))
_ANTENNA = ((0.0, 0.0, 0.065), (0.0, 0.0, -0.065))
ATTACHMENT_ANCHORS = {
	'legacy_tuft_large': (_TUFT,),
	'legacy_tuft_medium': (_TUFT,),
	'legacy_tuft_small': (_TUFT,),
	'legacy_ponytail_2': (
		((0.0, 0.0, 0.0), (0.0, -0.01, 0.1)),
		((0.0, 0.01, -0.1), (0.0, -0.01, 0.12)),
	),
	'antenna': (_ANTENNA_ROOT,),
	'antenna_2': (_ANTENNA_ROOT, _ANTENNA),
	'antenna_3': (_ANTENNA_ROOT, _ANTENNA, _ANTENNA),
	'antenna_4': (_ANTENNA_ROOT, _ANTENNA, _ANTENNA, _ANTENNA),
}

# ---- characterranges.py ----

BASIC_SPAZ_RANGES = {
	'color': (0.0, 1.0),
	'highlight': (0.0, 1.0),
	'team_coloring_strength': (0.0, 1.0),
	'torso_radius': (0.11, 0.3),
	'shoulder_offset': (-0.05, 0.03),
	'thigh_radius': (0.04, 0.06),
	'ankle_radius': (0.045, 0.07),
	'step_separation': (0.03, 0.08),
	'idle_arm_stiffness': (0.2, 1.0),
	'arm_swing': (0.3, 0.6),
	'idle_sway': (0.02, 0.05),
	'eye_scale': (0.5, 2.0),
	'eye_offset': (-0.5, 0.5),
	'eye_color': (0.0, 2.0),
	'eyeball_color': (0.0, 1.0),
	'eyelid_color': (0.0, 1.0),
	'eyelid_angle': (-30.0, 30.0),
	'reflection_scale': (0.0, 2.0),
}

ATTACHMENT_RANGES = {
	'position': (-0.5, 0.5),
	'stiffness': (0.0, 1.0),
	'damping': (0.0, 1.0),
	'drag': (0.0, 1.0),
	'curl': (-1.0, 1.0),
	'length': (0.0, 1.0),
	'radius': (0.0, 1.0),
	'curl_change': (-1.0, 1.0),
	'length_change': (-1.0, 1.0),
	'radius_change': (-1.0, 1.0),
	'stiffness_change': (-1.0, 1.0),
	'damping_change': (-1.0, 1.0),
}

# ---- characterbuilder.py: BasicSpazBuilder ----

CHARACTER_TYPE = 'basic_spaz'

# Reference fields, in web UI form order. Required ones must be set.
REQUIRED_REFS = (
	'name', 'icon_texture', 'icon_mask_texture',
	'color_texture', 'color_mask_texture',
	'head_mesh', 'torso_mesh', 'upper_arm_mesh',
	'upper_leg_mesh', 'lower_leg_mesh', 'toes_mesh',
)

# Body parts, in web UI form order, with their .bchar mesh field.
PARTS = (
	('head', 'head_mesh', True),
	('torso', 'torso_mesh', True),
	('pelvis', 'pelvis_mesh', False),
	('upper_arm', 'upper_arm_mesh', True),
	('forearm', 'forearm_mesh', False),
	('hand', 'hand_mesh', False),
	('upper_leg', 'upper_leg_mesh', True),
	('lower_leg', 'lower_leg_mesh', True),
	('toes', 'toes_mesh', True),
)
PAIRED_PARTS = ('upper_arm', 'forearm', 'hand', 'upper_leg', 'lower_leg', 'toes')

SOUND_FIELDS = (
	'jump_sounds', 'attack_sounds', 'impact_sounds',
	'death_sounds', 'pickup_sounds', 'fall_sounds',
)

# Defaults for every optional value the addon models (standard Spaz).
DEFAULTS = {
	'highlight_name': '',
	'highlight_editing': True,
	'highlight2': (1.0, 1.0, 1.0),
	'highlight2_name': '',
	'highlight2_editing': False,
	'torso_radius': 0.15,
	'shoulder_offset': (0.0, 0.0, 0.0),
	'thigh_radius': 0.04,
	'ankle_radius': 0.07,
	'step_separation': 0.08,
	'idle_arm_stiffness': 1.0,
	'arm_swing': 0.6,
	'idle_sway': 0.05,
	'eye_style_left': 'regular',
	'eye_style_right': 'regular',
	'eye_scale': 1.0,
	'eye_offset': (0.065, -0.036, 0.205),
	'eye_color': (0.5, 0.5, 1.2),
	'eyeball_color': (0.46, 0.38, 0.36),
	'eyelid_color': (0.5, 0.3, 0.2),
	'eyelid_angle': 0.0,
	'reflection_scale': 0.1,
	'flippers': False,
}

EYE_STYLES = ('regular', 'lidless', 'none')
ATTACH_TARGETS = (
	'head', 'torso', 'pelvis', 'upper_arm', 'forearm', 'hand',
	'upper_leg', 'lower_leg', 'toes', 'wing',
)
# Targets that are a single body part, so only side 'both' is allowed.
UNSIDED_TARGETS = ('head', 'torso', 'pelvis')
ATTACH_SIDES = ('both', 'right', 'left')
ATTACH_KINDS = tuple(ATTACHMENT_SEGMENTS)

ATTACHMENT_DEFAULTS = {
	'side': 'both',
	'stiffness': 0.5,
	'damping': 0.5,
	'drag': 0.5,
	'curl': 0.0,
	'length': 0.5,
	'radius': 0.0,
	'curl_change': 0.0,
	'length_change': 0.0,
	'radius_change': 0.0,
	'stiffness_change': 0.0,
	'damping_change': 0.0,
}


def clamp(value, span):
	return min(max(value, span[0]), span[1])
