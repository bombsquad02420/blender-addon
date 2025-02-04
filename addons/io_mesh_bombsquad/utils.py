import bpy

def map_range(value, from_start=0, from_end=1, to_start=0, to_end=127, clamp=False, precision=6):
    mapped_value = to_start + (to_end - to_start) * (value - from_start) / (from_end - from_start)
    mapped_value = round(mapped_value, precision)
    if precision == 0:
        mapped_value = int(mapped_value)
    if clamp:
        if to_start < to_end:
            mapped_value = max(min(mapped_value, to_end), to_start)
        else:
            mapped_value = max(min(mapped_value, to_start), to_end)
    return mapped_value


# Thanks EasyBPY!
def get_collection(ref = None):
    if ref is None:
        return bpy.context.view_layer.active_layer_collection.collection
    else:
        if isinstance(ref, str):
            if ref in bpy.data.collections:
                return bpy.data.collections[ref]
            else:
                return False
        else:
            return ref


# Thanks EasyBPY!
def set_active_collection(ref):
    colref = None
    if isinstance(ref, str):
        colref = get_collection(ref)
    else:
        colref = ref
    hir = bpy.context.view_layer.layer_collection
    search_layer_collection_in_hierarchy_and_set_active(colref, hir)


# Thanks EasyBPY!
def search_layer_collection_in_hierarchy_and_set_active(colref, hir):
    if isinstance(hir, bpy.types.LayerCollection):
        if hir.collection == colref:
            bpy.context.view_layer.active_layer_collection = hir
        else:
            for child in hir.children:
                search_layer_collection_in_hierarchy_and_set_active(colref, child)
