# Modules that need bpy are imported in register() so the pure-Python
# modules (rig, bchar, workspace, transforms) can be tested outside Blender.

_modules = []


def register():
	from . import attach_ops, eye_scene, nodegroup, operators, paint, part_scene, props, ui  # noqa: F401 (part_scene registers a hook)
	_modules[:] = [props, operators, attach_ops, eye_scene, paint, ui]
	for module in _modules:
		module.register()
	# Lists the bundled "Ballistica Colorize" node group in the Asset
	# Browser and the shader editor's Add menu.
	nodegroup.register_library()


def unregister():
	from . import nodegroup
	nodegroup.unregister_library()
	for module in reversed(_modules):
		module.unregister()
	_modules.clear()
