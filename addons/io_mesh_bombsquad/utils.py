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
