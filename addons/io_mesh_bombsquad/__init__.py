from . import bob, cob, leveldefs


def register():
	bob.register()
	cob.register()
	leveldefs.register()


def unregister():
	leveldefs.unregister()
	cob.unregister()
	bob.unregister()
