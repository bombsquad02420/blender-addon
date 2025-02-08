import os
import bpy

from . import operators, ui, bob, cob, leveldefs


def register():
	operators.register()
	ui.register()
	bob.register()
	cob.register()
	leveldefs.register()
	bpy.utils.register_preset_path(os.path.join(os.path.dirname(__file__)))


def unregister():
	leveldefs.unregister()
	cob.unregister()
	bob.unregister()
	ui.unregister()
	operators.unregister()
	bpy.utils.unregister_preset_path(os.path.join(os.path.dirname(__file__)))
