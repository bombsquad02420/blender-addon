# BombSquad character format (`.bchar`) and the asset pipeline

Notes from reading the Python shipped in `BombSquad Test.app`
(`Contents/Resources/ba_data/python`) and a downloaded asset workspace.

Key source files:

| File | What it holds |
|---|---|
| `bacommon/characterbuilder.py` | The `.bchar` JSON schema (dataclasses) |
| `bacommon/characterranges.py` | Allowed numeric ranges (values are clamped) |
| `bacommon/characterrig.py` | Fixed rig numbers and the coordinate system |
| `bacommon/assetpackage.py` | Package resolve errors (shows building is server-side) |
| `baclassic/_characterpreview.py` | The "try it in game" preview flow |
| `babase/_asset_packages.py` | Loading of bundled, already-built packages |
| `bascenev1lib/actor/spazappearance.py` | Built-in characters, each backed by a `.bchar` |

## Pipeline

1. You write a character in an **asset workspace**, using the web UI on the
   BombSquad master server. A workspace is a folder of source files plus a
   `workspace.json` that gives each path a type and priority.
2. The **server** reads the `.bchar` and turns it into a compact form, which it
   sends to game clients. The source JSON never reaches the game as written.
3. While you work, the web UI's preview button makes the server build a dev
   version of the package and push it to your running game (if you're signed
   in to the same account). The game downloads it and starts a one-map session
   (Death Match on Rampage) where that character is the only one you can pick.

The built-in characters work the same way now: each one is
`characters/<name>.bchar` in a character package. `spazappearance.py` only adds
the icon and default colors.

### Can it be compiled or previewed locally?

**Not with anything that ships in the app.**

- The resolve errors in `assetpackage.py` show that building happens on the
  server. `INTERNAL` is described as an "assemble error occurred server-side",
  and `CONTENT` means "the package's own source content failed to build".
- Bundled packages live in `ba_data/assets/` as built files filed under
  hash-named folders (`61/`, `9e/`, ...), not as source. Nothing in the Python
  code or the binary's strings turns a workspace folder into that format.
- The downloaded `BuiltinAssets` workspace is the engine's bare-minimum package:
  fonts, cursor textures, UI sounds, `.bstr` strings and 3 `.obj` meshes. It
  contains no `.bchar` files.

The only working path is to upload to a workspace you own and use the web UI's
preview. A local preview would mean reverse-engineering the built format in
`ba_data/assets/` and writing your own compiler. That's a big job, and it could
break with any server or client update.

## Asset references

- **Logical paths:** every asset is named by its path from the workspace root,
  minus the extension. So `zoe/head.obj` becomes `"zoe/head"`. Logical paths
  are unique across all asset types.
- You can only reference assets in your own workspace, so copy in anything you
  want to reuse.
- The character's name points to a `.bstr` string file so it can be translated.

## Schema

The top level is `{"data": {...}}`, with `data.type` set to `"basic_spaz"`.
That's currently the only kind. Any number you leave out uses the standard
Spaz value.

### Textures and tinting

The whole body uses one `color_texture` plus one `color_mask_texture`. In the
mask:

- **red** takes the player's color
- **green** takes the highlight
- **blue** takes `highlight2` (it defaults to white, which leaves that area
  untinted)

### Required fields

`name`, `icon_texture`, `icon_mask_texture`, `color`, `highlight`,
`color_texture`, `color_mask_texture`, `head_mesh`, `torso_mesh`,
`upper_arm_mesh`, `upper_leg_mesh`, `lower_leg_mesh`, `toes_mesh`.

### Optional meshes

- `forearm_mesh`, `hand_mesh`, `pelvis_mesh`: leave one out and that part isn't
  drawn.
- Arm and leg meshes are made for the right side and mirrored for the left.
  `left_upper_arm_mesh`, `left_forearm_mesh`, `left_hand_mesh`,
  `left_upper_leg_mesh`, `left_lower_leg_mesh` and `left_toes_mesh` give the
  left side its own mesh. Left meshes are still authored as right-side parts and
  drawn mirrored.

### Highlights

- `highlight_name`: a `.bstr` path for what the highlight is called in the
  profile editor. Empty means "Highlight".
- `highlight_editing`: whether players can change the highlight. Default `true`.
- `highlight2`, `highlight2_name`, `highlight2_editing`: the same for the second
  highlight. Editing defaults to `false`.

### Sounds

`jump_sounds`, `attack_sounds`, `impact_sounds`, `death_sounds`,
`pickup_sounds`, `fall_sounds`. Each is a list of sound paths and the game picks
one at random. An empty list means silent.

### Physique

These change how the body plays, not just how it looks. Values outside the range
are clamped.

| Field | Default | Range |
|---|---|---|
| `torso_radius` | 0.15 | 0.11–0.3 |
| `shoulder_offset` (vec3) | 0,0,0 | −0.05–0.03 |
| `thigh_radius` | 0.04 | 0.04–0.06 |
| `ankle_radius` | 0.07 | 0.045–0.07 |
| `step_separation` | 0.08 | 0.03–0.08 |
| `idle_arm_stiffness` | 1.0 | 0.2–1.0 |
| `arm_swing` | 0.6 | 0.3–0.6 |
| `idle_sway` | 0.05 | 0.02–0.05 |

### Eyes

| Field | Default | Range |
|---|---|---|
| `eye_style_left`, `eye_style_right` | `regular` | `regular` / `lidless` / `none` |
| `eye_scale` | 1.0 | 0.5–2.0 |
| `eye_offset` (vec3, mirrored) | 0.065, −0.036, 0.205 | −0.5–0.5 |
| `eye_color` (iris) | 0.5, 0.5, 1.2 | 0–2 |
| `eyeball_color` | 0.46, 0.38, 0.36 | 0–1 |
| `eyelid_color` | 0.5, 0.3, 0.2 | 0–1 |
| `eyelid_angle` (degrees; positive looks angry) | 0 | −30–30 |

### Other

- `reflection_scale`: glossiness. Default 0.1, range 0–2.
- `flippers`: set to `true` when one long upper-arm mesh is the whole arm. The
  arms are then drawn shorter while the character wears boxing gloves.
- `color` and `highlight` components: 0–1.

### Attachments

Extra pieces like hair, ears, hats and wings. They're for looks only and never
affect gameplay.

- `target`: the body part it hangs from. One of `head`, `torso`, `pelvis`,
  `upper_arm`, `forearm`, `hand`, `upper_leg`, `lower_leg`, `toes`, `wing`.
  Attaching anything to `wing` gives the character wings that flap.
- `side`: `both` (the only choice for head, torso and pelvis), `left` or
  `right`.
- `kind`:
  - `static`: fixed in place. It's the only kind allowed on limbs and wings.
  - `antenna`, `antenna_2`, `antenna_3`, `antenna_4`: springy chains of 1–4
    segments. Use these for anything new.
  - `legacy_tuft_large`, `legacy_tuft_medium`, `legacy_tuft_small`,
    `legacy_ponytail_2`: copies of the old hair rig. They twirl oddly when
    disturbed.
- `segments`: one entry per segment, starting from the root. Each has `mesh`,
  plus optional `texture`, `mask_texture` and `transform`.
- `transform`: where it's anchored on the body part. Its `scale` is ignored, so
  resize segments through their own transforms.
- Tuning values:
  - `stiffness`, `damping`, `drag`, `length`: 0–1, default 0.5
  - `radius`: 0–1, default 0
  - `curl`: −1 to 1, default 0
- `*_change` values (−1 to 1): how much each tuning value changes from one
  segment to the next. Available for `curl`, `length`, `radius`, `stiffness`
  and `damping`.

### Transforms and coordinates

- A transform is `{translate, rotate, scale}`. The thing is scaled about its own
  origin, then rotated, then moved.
- `rotate` is heading, pitch and roll in degrees:
  - positive heading turns right
  - positive pitch tilts the nose up
  - positive roll is clockwise when seen from behind
- Coordinates: Y is up, Z is forward, and the character's right is −X.

## Example

```json
{
  "data": {
    "type": "basic_spaz",
    "name": "robo/name",
    "icon_texture": "robo/icon",
    "icon_mask_texture": "robo/icon_mask",
    "color": [0.3, 0.5, 0.9],
    "highlight": [1.0, 0.8, 0.1],
    "color_texture": "robo/color",
    "color_mask_texture": "robo/color_mask",
    "head_mesh": "robo/head",
    "torso_mesh": "robo/torso",
    "upper_arm_mesh": "robo/upper_arm",
    "forearm_mesh": "robo/forearm",
    "hand_mesh": "robo/hand",
    "pelvis_mesh": "robo/pelvis",
    "upper_leg_mesh": "robo/upper_leg",
    "lower_leg_mesh": "robo/lower_leg",
    "toes_mesh": "robo/toes",
    "jump_sounds": ["robo/jump1", "robo/jump2"],
    "torso_radius": 0.2,
    "eye_style_left": "none",
    "eye_color": [1.5, 0.2, 0.2],
    "eyelid_angle": 15,
    "reflection_scale": 0.8,
    "attachments": [
      {
        "target": "head",
        "kind": "antenna_3",
        "transform": { "translate": [0, 0.2, 0], "rotate": [0, 80, 0] },
        "segments": [
          { "mesh": "robo/ant1" },
          { "mesh": "robo/ant2" },
          { "mesh": "robo/ant3" }
        ],
        "stiffness": 0.8,
        "stiffness_change": -0.5
      }
    ]
  }
}
```
