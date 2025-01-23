def map_range(value, from_start=0, from_end=1, to_start=0, to_end=127, clamp=False, cast_to_int=False):
    mapped_value = to_start + (to_end - to_start) * (value - from_start) / (from_end - from_start)
    if clamp:
        if to_start < to_end:
            mapped_value = max(min(mapped_value, to_end), to_start)
        else:
            mapped_value = max(min(mapped_value, to_start), to_end)
    if cast_to_int:
        mapped_value = int(mapped_value)
    return mapped_value
