# Modules that need bpy are imported in register() so the pure-Python
# modules (rig, bchar, workspace, transforms) can be tested outside Blender.

_modules = []


def register():
	from . import props, operators, ui
	_modules[:] = [props, operators, ui]
	for module in _modules:
		module.register()


def unregister():
	for module in reversed(_modules):
		module.unregister()
	_modules.clear()
