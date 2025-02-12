import os
import bpy

from . import operators, ui, bob, cob, leveldefs

addon_dir = os.path.dirname(__file__)

def register():
	operators.register()
	ui.register()
	bob.register()
	cob.register()
	leveldefs.register()
	bpy.utils.register_preset_path(addon_dir)


def unregister():
	leveldefs.unregister()
	cob.unregister()
	bob.unregister()
	ui.unregister()
	operators.unregister()
	bpy.utils.unregister_preset_path(addon_dir)
