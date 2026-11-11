"""Updating characters saved by an older version of the addon.

Every character collection is stamped with the scene format it was built
with (`format_version`). When the addon changes how it stores a character
in the scene (new lists, objects, properties or drivers), bump
FORMAT_VERSION and add a step to STEPS that turns a character of the
previous version into the new one. The panel then shows one **Update
Character** box for older characters instead of the usual sections, and
Update runs every step they're missing, in order.

Development versions are never migrated: nothing before the first release
needs to keep working, so STEPS starts empty at version 1.
"""

FORMAT_VERSION = 1

# Version it upgrades *to* -> function(collection). Example, for a future
# version 2 that adds a list:
#
#	def _add_some_list(collection):
#		...
#
#	STEPS = {2: _add_some_list}
STEPS = {}


def needs_update(collection):
	return collection.ballistica_character.format_version < FORMAT_VERSION


def update(collection):
	"""Run the steps a character is missing; returns how many ran."""
	settings = collection.ballistica_character
	ran = 0
	for version in sorted(STEPS):
		if version > settings.format_version:
			STEPS[version](collection)
			ran += 1
	settings.format_version = FORMAT_VERSION
	return ran
