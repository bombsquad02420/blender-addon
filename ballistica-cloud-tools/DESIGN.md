# Ballistica Cloud Tools for Blender — Design

Status: draft, updated 2026-10-17 with the game-code findings in
[`BCHAR_FORMAT.md`](BCHAR_FORMAT.md). Working name `ballistica-cloud-tools`; sits next to
`bombsquad-tools` in this repo.

## Background

Ballistica 1.8 moved modding to the cloud. The game no longer reads local
mod files or the custom `.bob` (mesh) and `.cob` (collision mesh) formats.
Creators upload plain source files — JSON and Wavefront OBJ, plus PNG and
WAV — to a **workspace** in Ballistica cloud, and the cloud compiles them
into game-ready assets.

Today only **custom characters** are supported, so that is this addon's
first and only target. `bombsquad-tools` (the `.bob`/`.cob` addon) stays as
is for the old pipeline.

References:

- [`BCHAR_FORMAT.md`](BCHAR_FORMAT.md): the `.bchar` format as the game
  reads it (fields, defaults, ranges, attachments, coordinates). **This is
  the schema reference; this doc does not repeat it.**
- Ballistica source, `tools/bacommon/` in `../../ballistica`:
  `characterbuilder.py` (schema), `characterranges.py` (clamping ranges),
  `characterrig.py` (rig dimensions and joint anchors).
- The `ClassicCharacterAssets` workspace (all 18 classic characters), cloned
  at `../../ClassicCharacterAssets`.

## Decision: folder-based sync (no SDK inside Blender, for now)

The addon works on a **local workspace folder**. Syncing that folder with the
cloud happens outside Blender:

```
bacloud-ts workspace get MyCharacter     # cloud -> folder
# open/import in Blender, edit, export back into the folder
bacloud-ts workspace put MyCharacter     # folder -> cloud
```

`bacloud-ts` (the TS CLI in `../../bacloud-ts`) or ballistica's own
`tools/bacloud` both work; the folder format is identical. Their put refuses
to overwrite a workspace that changed since the last get (snapshot id in
`.bacloudstate.json`), so the folder flow is safe for collaboration.

Why not sync from inside Blender yet:

- **No reusable Python client.** Ballistica's own Python `bacloud` uses
  Python 3.14-only syntax (e.g. `except ValueError, OSError:`), while Blender
  4.2+ ships Python 3.11. A Blender-side SDK means a fresh port of the TS SDK
  (wire protocol, SmartSocket session, transfers) — similar in size to it.
- **Extra dependency.** The session runs over WebSocket; Blender does not
  bundle `websockets`, so the extension would need to ship it as a wheel.
- **Blender UI constraints.** Sync is slow, blocking network I/O. It would
  need a worker thread plus a modal timer for progress, and Blender dialogs
  for browser sign-in and server input prompts. That is more code than the
  modelling features.
- **The folder flow already works** end to end, and the same folder is
  editable in VS Code via the bacloud VS Code extension.

### Seam for later

Keep sync out of the addon's core: core code only reads and writes a
workspace folder. In-Blender **Get / Put** buttons can be added later as a
separate module, via either:

1. **Shell out to the CLI** — run `bacloud-ts workspace get/put` as a
   subprocess and stream its output into Blender. Cheap; needs Node
   installed.
2. **Python SDK** — a separate `bacloud-py` package ported from the TS SDK
   (stdlib + `websockets`), vendored into the extension as wheels.

## Workspace format (characters)

```
MyCharacter/
  workspace.json           # asset settings (see below)
  characters/<id>.bchar     # character definition (JSON)
  meshes/<part>.obj         # body part meshes
  textures/<name>.png       # color, color mask, icon, icon mask
  audio/<name>.wav          # voice and body sounds
  strings/characters/<id>.bstr  # display name + translations
  .bacloudstate.json        # sync bookkeeping; not part of the workspace
```

### References

Assets refer to each other by **workspace-relative path without extension**
(a *logical path*): `"meshes/agent_head"`, `"textures/agent_color"`,
`"audio/agent1"`, `"strings/characters/agent_johnson"`. Logical paths are
unique across all asset types, so `foo.png` and `foo.obj` cannot coexist.

A character can only reference assets **in its own workspace**. Reusing a
classic mesh or sound means copying the file in.

### `workspace.json`

```json
{
  "global": { "docs": "…" },
  "path": {
    "meshes": { "type": "group_v1", "docs": "Character body part meshes." },
    "textures/agent_color_mask.png": { "type": "tex_v1", "texture_role": "data" },
    "textures/bunny_color.png": { "type": "tex_v1", "texture_alpha": "no" },
    "strings/characters/agent_johnson.bstr": { "type": "str_v1", "st": { "u": "…" } }
  },
  "type": "assets_v1"
}
```

Observed rules:

- Only files that need **non-default settings** are listed; OBJ, WAV, BCHAR
  and plain color/icon PNGs have no entry.
- Folders get `group_v1` entries that carry `docs`.
- **Color masks and icon color masks** are `"texture_role": "data"`
  (non-color data; must not be treated as sRGB).
- Opaque color textures may set `"texture_alpha": "no"`.
- `str_v1` entries carry server-maintained state (`st`). The file is
  **co-owned**: the client edits some parts, the server maintains others.
  The addon must preserve unknown keys and only touch what it owns.

### Character definition (`.bchar`)

`{"data": {...}}` with `data.type = "basic_spaz"` (the only kind). Full field
list, defaults and ranges: [`BCHAR_FORMAT.md`](BCHAR_FORMAT.md). What matters
for the addon:

- **Required:** `name` (a `.bstr` path), `icon_texture`, `icon_mask_texture`,
  `color`, `highlight`, `color_texture`, `color_mask_texture`, and the
  `head`, `torso`, `upper_arm`, `upper_leg`, `lower_leg`, `toes` meshes.
- **Optional parts:** `forearm_mesh`, `hand_mesh`, `pelvis_mesh`; a missing
  part is simply not drawn.
- **Left/right:** arm and leg meshes are authored for the **right** side and
  mirrored for the left. Optional `left_*_mesh` fields give the left side its
  own mesh, still authored as a right-side part.
- **Numbers are clamped** by the game to the spans in `characterranges.py`.
  Leaving a number out means the standard Spaz value. Physique values change
  gameplay; look values don't.
- **Tinting:** one color texture + one color mask for the whole body. Mask
  **red** = player color, **green** = `highlight`, **blue** = `highlight2`
  (defaults to white, i.e. untinted). `highlight_name` / `highlight_editing`
  and the `highlight2*` equivalents control the profile editor.
- **Sounds:** six lists (`jump`, `attack`, `impact`, `death`, `pickup`,
  `fall`); the game picks one at random; empty means silent.
- **Attachments:** look-only extra meshes on a `target` part (`head`,
  `torso`, `pelvis`, limbs, `toes`, or `wing`, which flaps), with a `side`, a
  `kind` (`static`; springy `antenna`…`antenna_4`; or four `legacy_*` hair
  rigs), an anchor `transform` and 1–4 `segments`, each with a mesh and
  optional texture, mask and transform.

The classic characters use only a subset (no `left_*` meshes, no
`highlight2`, attachment kinds `antenna`, `antenna_2` and `static` only), so
the sample alone under-represents the format.

**The schema is newer than our checkout's builder.** The engine
(`src/ballistica/base/support/character_def.h`) already reads more than
`characterbuilder.py` describes, e.g. `highlight_team_coloring_strength` /
`highlight2_team_coloring_strength` (how strongly team colors tone each
highlight; `characterranges.py` has a `team_coloring_strength` span) and
per-part textures, tint masks and tints. The schema's real home is the
server (`bamaster baserver/character.py`), which we can't see. So the addon
**preserves every field it doesn't model**, on import and export.

### Coordinates and transforms

From `characterrig.py`: **Y is up, Z is forward, and the character's own right
is −X**. Units are game world units (≈ metres at Spaz scale).

A transform is `{translate, rotate, scale}`: scale about the origin, then
rotate, then translate. `rotate` is heading, pitch, roll in degrees (positive
heading turns right, positive pitch tilts the nose up, positive roll is
clockwise seen from behind). An attachment's own `scale` is ignored; segments
scale through their own transforms.

**Axes.** Blender is Z-up with −Y forward, so import maps game (x, y, z) →
Blender (x, −z, y), and export the reverse. This is exactly the old addon's
`axis_conversion(from_forward='-Z', from_up='Y')` in `bob.py`/`cob.py`, and
the meshes agree (feet reach forward to z = +0.08). A character faces the
front view; its right (game −X) is Blender −X.

**Rotations.** `BuilderTransform` defines `rotate` as heading, pitch, roll in
degrees, applied in that order as intrinsic turns of the thing's own axes
(nose = +Z). The engine itself only ever sees quaternions: the server
converts, in code we can't see (`character_def.cc` reads a `(w, x, y, z)`
quaternion; its transform short forms compose scale, then rotate, then
translate). From the docstring's sign rules, in game axes:

| Angle | Game axis | Sign |
| --- | --- | --- |
| heading *h* | parent's up (+Y) | positive turns the nose toward the character's right (−X): rotation by −*h* |
| pitch *p* | own +X | positive raises the nose: rotation by −*p* |
| roll *r* | own nose (+Z) | positive is clockwise seen from behind: rotation by +*r* |

so R = R_Y(−h) · R_X(−p) · R_Z(r). In Blender axes that is an Euler in
**`YXZ` mode** with `(x, y, z) = (−p, −r, −h)` in radians (game Y → Blender
Z, game Z → Blender −Y). The algebra and each sign rule were checked
numerically, but the conversion is derived from the docstring, not from the
server code: check it by importing Zoe and Pixel and comparing tuft and wing
placement with the web UI.

### Meshes (`.obj`)

- One OBJ per body part, **in the part's own local space**. Arm and leg
  parts are right-side parts.
- Triangulated, with positions, UVs and normals (`f v/vt/vn`); no objects,
  groups or materials. The whole body shares one color texture.
- Classic characters share some meshes (e.g. `spaz_*`, `lady_*`), but only
  within one workspace (see References above).

### Rig (`characterrig.py`)

The game's fixed rig numbers, enough to place parts in a standing pose
without hand-made tables:

- **Body sizes:** head ball radius 0.23; pelvis box 0.35 × 0.16 × 0.1;
  upper/lower arm capsules (radius 0.06, length 0.16 / 0.13); upper leg
  length 0.12; lower leg span 0.26; toes ball radius 0.075. Torso, thigh and
  ankle radii are per character (`torso_radius`, `thigh_radius`,
  `ankle_radius`). Capsules lie along their own z axis.
- **Start heights:** head 2.25, torso 1.8, pelvis 1.66, roller 1.6.
- **Joint anchors:** pelvis–torso joint (0.05 below and 0.05 in front of the
  torso centre); shoulder on torso (−0.15, 0.14, 0) plus the character's
  `shoulder_offset`; elbow, hip, knee and ankle anchors on each body.
- **Art placement:** limb art is stretched so the two segments of an arm or
  leg keep meeting; the hand sits 0.04 along the lower arm, turned 10°; eye
  art is drawn at scale 0.09.
- **Attachment rigs:** capsule sizes, anchors and spring constants for each
  simulated `kind`.

The addon is **self-contained**: it never reads game or ballistica files at
runtime. The rig numbers and ranges it needs are copied into the addon at
development time, with a note of the ballistica version they came from.
(The modules use Python 3.12 `type` aliases, so Blender 4.2's Python 3.11
couldn't import them anyway.)

### Textures

- Color texture (1024² RGBA in the samples), color mask, icon (512²), icon
  mask. Masks are `texture_role: data` in `workspace.json`.
- The old addon's *BombSquad Colorize* node group previews player color and
  highlight; it needs a third input for `highlight2` (blue channel).

### Strings (`.bstr`)

`input` (source text) plus `docs` for translators, `fit_preset`, and
server-filled `outputs` per language.

**The addon ignores the `strings/` folder entirely.** It never reads or
writes `.bstr` files and never shows languages or translations. String
fields (`name`, `highlight_name`, `highlight2_name`) are shown and edited as
their translation keys only, e.g. `strings/characters/agent_johnson`.

## Building and preview

**There is no local compiler.** The server builds the package from the
workspace source; the game only ever receives the built form. The game's
resolve errors show this: `INTERNAL` is an assemble error on the server, and
`CONTENT` means the package's own source failed to build.

**The web UI is the accurate preview.** Opening a `.bchar` in the workspace
web UI (screenshots of Agent Johnson in [`webui/`](webui/)):

| View | What it shows |
| --- | --- |
| Header | the character's display name; the file's size and modified time |
| Left column | two color swatches (player `color` and `highlight`), then the view buttons **S**, **R**, **B**, **P**, **V** |
| **S** ([spread](webui/spread.png)) | a **Spread** slider that pulls the parts apart (an exploded view; joints still drawn per part when P is on) and a **Stretch** checkbox, presumably the game's limb-art stretching |
| Top right | the icon texture, tinted with its icon mask |
| Default ([screenshot](webui/default.png)) | the model as the game draws it, textures mapped and tints applied, in the rest pose; always shown under the toggles below |
| **R** | **rotate**: the model spins slowly and continuously |
| **B** ([bodies](webui/bodies.png)) | the physics bodies: head ball, torso ball, pelvis box, one capsule per arm segment and per leg, toes balls, and the large translucent roller ball around the lower body. Hands have no body |
| **P** ([pose](webui/pose.png)) | the model with the bone pose drawn over it as joints and links |
| **V** ([visibility](webui/visibility.png)) | toggles for which parts are drawn: All, Left, Right; Head, Body, Arms, Legs; Attachments, Eyes |
| Bottom | triangle count (1,912 for Agent Johnson) and a play button, which builds a dev version and pushes it to your running game |
| Below ([form](webui/form.png)) | the settings form, with dropdown pickers listing the workspace's own assets for every reference |

**Rest pose** (default view and P): standing, legs straight down and slightly apart,
arms out to the sides and angled slightly down, hands at the ends of the
forearms.

**Pose joints** (P): head, the torso top (neck), each shoulder, elbow, wrist
and hand; the pelvis centre; each hip, knee and ankle, and points along the
foot. Links: head–neck; neck–shoulders and shoulders–pelvis (a triangle);
the arm chains; pelvis–hips and hip–hip; the leg chains down to the toes.

**Form** (the whole form for Agent Johnson; one **Save Character** button
at the end writes the `.bchar`):

| Section | Fields, in order | Widget |
| --- | --- | --- |
| Identity | Name, Icon Texture, Icon Mask Texture | asset dropdown |
| | Color, Highlight | text, "three numbers" |
| | Highlight Name | string dropdown, `(none)` allowed |
| | Highlight Editing | checkbox |
| | Highlight 2, Highlight 2 Name, Highlight 2 Editing | as above |
| Textures | Color Texture, Color Mask Texture | asset dropdown |
| Meshes | Head, Torso, Pelvis, Upper Arm, Forearm, Hand, Upper Leg, Lower Leg, Toes | asset dropdown; required parts say `(choose one)`, optional ones (pelvis, forearm, hand) allow `(none)` |
| Sounds | Jump, Attack, Impact, Death, Pickup, Fall | textarea, one sound path per line |
| Physique | Torso Radius, Shoulder Offset (three numbers), Thigh Radius, Ankle Radius, Step Separation, Idle Arm Stiffness, Arm Swing, Idle Sway | number |
| Eyes | Eye Style Left, Eye Style Right | dropdown: Regular / Lidless / None |
| | Eye Scale, Eye Offset, Eye Color, Eyeball Color, Eyelid Color, Eyelid Angle | number or "three numbers" |
| Surface | Reflection Scale | number |

Notes:

- **Defaults are filled in.** Agent Johnson's `.bchar` has no physique or
  eye-color values, yet the form shows `0.15`, `0, 0, 0`, `0.04`, … — the
  standard Spaz values from `BCHAR_FORMAT.md`.
- **Dropdowns aren't filtered by role.** Every texture field lists every
  workspace texture (colors, masks, icons alike); every mesh field lists
  every mesh, including attachment meshes; the name fields list every
  string.
- **Not in the form:** `left_*` meshes, `flippers`, and `attachments`.
  Those can only be set by editing the `.bchar` (and must survive the form's
  Save).

The addon mirrors that page inside Blender: the same three things side by
side, a **preview** (textured, tinted model), **guides** (physics bodies and
bone pose), and a **form** for every `.bchar` property. Blender adds what the
web UI can't do: modelling, UVs, texture painting, and placing things by hand.

Final check: `workspace put`, then the web UI preview and the game.

## Blender interface

### Scene layout

One character is one **collection**, holding:

```
Character: zoe                     (collection; .bchar settings live here)
├── zoe_rig                        (armature: pose source)
├── head, torso, pelvis            (part meshes, parented to their bones)
├── upper_arm.R, forearm.R, hand.R … toes.R
├── upper_arm.L … toes.L           (mirrored instances of the .R meshes,
│                                   or their own mesh if a left_* is set)
├── eye.L, eye.R                   (preview-only eye art)
├── attachment: hair_tuft1 …       (attachment segments, parented to bones)
└── Guides                         (child collection, never exported)
    ├── head ball, torso, pelvis box, limb capsules, toes, roller
```

### Armature: pose and placement

An armature built from the vendored rig numbers, in the web UI's arms-out
rest pose. Bones: `pelvis`, `torso`, `head`, and `.R`/`.L` pairs for
`upper_arm`, `forearm`, `hand`, `upper_leg`, `lower_leg`, `toes`, plus
`wing` and one bone (or chain) per attachment.

- Part meshes are **bone-parented**, so their mesh data stays in the part's
  own local space. Export writes mesh data as-is; posing the armature never
  changes what's exported.
- Placement values in the `.bchar` come **from the armature**, so editing
  them is a viewport action, not typing numbers:

  | `.bchar` field | Armature source |
  | --- | --- |
  | `shoulder_offset` | shoulder bone head, relative to the rig's shoulder-on-torso point |
  | `eye_offset` | `eye.R` bone (mirrored to `eye.L`) |
  | attachment `transform` | attachment root bone, relative to its target bone |
  | segment `transform` | each segment bone relative to the previous one |

  Values are converted game↔Blender axes and clamped to
  `characterranges.py` spans on export, with a warning when clamping
  changes something.
- Everything else in the rig (body sizes, joint anchors, start heights) is
  fixed by the game, so those bones are locked. Changing per-character radii
  (`torso_radius`, `thigh_radius`, `ankle_radius`) updates the guides, not
  the bones.

### Collection properties: the form

All other `.bchar` settings are stored on the character collection as a
registered property group (`collection.ballistica_character`), so they are
typed, saved in the `.blend`, and get min/max from `characterranges.py`. A
sidebar panel (**N panel → Ballistica**) shows them in the same order and
groups as the web UI form, with the same defaults filled in:

| Section | Fields |
| --- | --- |
| Identity | `name` (translation key), `icon_texture`, `icon_mask_texture`, `color`, `highlight`, `highlight_name`, `highlight_editing`, `highlight2`, `highlight2_name`, `highlight2_editing` |
| Textures | `color_texture`, `color_mask_texture` |
| Meshes | `head_mesh`, `torso_mesh`, `pelvis_mesh`, `upper_arm_mesh`, `forearm_mesh`, `hand_mesh`, `upper_leg_mesh`, `lower_leg_mesh`, `toes_mesh` (the part objects, filled from the scene; optional ones can be empty) |
| Sounds | the six sound lists (`jump`, `attack`, `impact`, `death`, `pickup`, `fall`), each a plain string list of audio paths (one per line, as in the web UI) |
| Physique | `torso_radius`, `shoulder_offset` (shown, but placed with the shoulder bone), `thigh_radius`, `ankle_radius`, `step_separation`, `idle_arm_stiffness`, `arm_swing`, `idle_sway` |
| Eyes | `eye_style_left/right`, `eye_scale`, `eye_offset` (shown, but placed with the eye bone), `eye_color`, `eyeball_color`, `eyelid_color`, `eyelid_angle` |
| Surface | `reflection_scale` |
| Advanced *(beyond the web UI)* | `left_*` mesh overrides, `flippers` |
| Attachments *(beyond the web UI)* | list (UIList): `target`, `side`, `kind`, spring values and their `*_change`, segments with optional texture and mask |

The first eight sections match the web UI form one-to-one. The last two
cover what the web form leaves out; Blender is the friendlier place to edit
them anyway, since attachments need placing in 3D.

Unlike the web UI, pickers can be **filtered by role** (color textures vs
masks vs icons, body-part meshes vs attachment meshes), using names and
`workspace.json` roles as a hint, with an option to show everything.

Reference fields are pickers over the workspace's own files, like the web
UI's dropdowns. The panel header shows the icon texture and the character's
triangle count, as the web UI does.

Fields the addon doesn't know (a newer format) are kept as raw JSON on the
collection and written back unchanged.

### Preview and guides

Panel toggles that match the web UI's views:

- **Color swatches:** the player `color` and `highlight`, as in the web UI's
  left column, for quickly trying tints.
- **Preview:** material preview with the colorize node group, driven live by
  `color`, `highlight` and `highlight2` from the form; `reflection_scale`
  maps to roughness/specular as a rough approximation.
- **Bodies:** the guides collection, matching the web UI's B view: head
  and torso balls, pelvis box, arm-segment and leg capsules, toes balls and
  the translucent roller, sized from the rig numbers and the character's
  radii and updated when the physique values change. No hand body.
- **Pose:** the armature drawn over the model, with the same joints as the
  web UI's P view (stick display).
- **Rotate:** not needed; Blender's viewport already orbits freely.
- **Spread:** the exploded layout from `bombsquad-tools` stands in for the
  web UI's Spread slider; that's enough for now. Stretch is not mirrored.
- **Visibility:** not a panel feature. Blender's outliner already hides and
  shows objects, so the scene is organised to make that easy: one object per
  part with `.L`/`.R` names, attachments and eyes as their own objects, and
  guides in a child collection.

Eye art isn't in the workspace (the game draws shared eye meshes), so the
addon ships a simple stand-in eye, scaled by `eye_scale` and the rig's
`eye_mesh_scale`, so eye placement can be judged.

### Pre-upload checks

A **Check** button (also run on export): required fields set; every
referenced file exists in the workspace; meshes triangulated with UVs and
normals; masks marked `texture_role: data`; values in range. There are no known
server limits on vertex counts or texture sizes, so the checks don't invent
any; the panel just shows the triangle count, like the web UI.

## Character workflow

### Import character

From a workspace folder, pick a `.bchar`:

1. Create the collection and fill its properties from the `.bchar`.
2. Build the armature in the rest pose; apply `shoulder_offset`,
   `eye_offset` and attachment transforms to their bones.
3. Import each part OBJ (game axes → Blender) and bone-parent it. Create the
   left limbs as mirrored instances, or from the `left_*` meshes.
4. Load the textures and build the material.
5. Import attachment segments onto their bones.
6. Build the guides.

### Edit

- Model, UV-map and texture-paint the parts. Limbs are edited on the `.R`
  side and shown mirrored.
- Move the shoulder, eye and attachment bones to place them.
- Edit everything else in the panel; the preview updates live.

### Export character

1. Write each part OBJ from its mesh data (part-local, triangulated, UVs and
   normals; Blender axes → game). Limbs are written as right-side parts.
2. Save modified images as PNG into the workspace.
3. Write the `.bchar` from the collection properties and the armature,
   keeping unknown fields. **Blender's copy wins:** export overwrites the
   local files. Edits made in the web UI since import are lost unless you
   `workspace get` and re-import first.
4. Update `workspace.json` only for files the addon creates (e.g. mark new
   masks `texture_role: data`), preserving everything else.
5. Run the checks, then `bacloud-ts workspace put` and look at the result in
   the web UI.

### New character

**New character** creates the collection, armature, guides and a stand-in
body from a template shipped in the addon (the addon can't read the game's
files), with required fields filled and Spaz defaults elsewhere. Classic
characters can be started from by copying their files into the workspace
(e.g. from `ClassicCharacterAssets`) and importing.

## Self-contained

The addon never reads game or ballistica files at runtime. Everything it
needs is shipped inside it:

- the rig numbers (`characterrig.py`) and ranges (`characterranges.py`),
  copied in with a note of the ballistica version they came from;
- the `.bchar` field list and defaults (`characterbuilder.py`);
- the colorize node group, stand-in eye mesh and new-character template.

When ballistica changes these, the addon needs a new release.

## Reuse from `bombsquad-tools`

| Keep | Drop |
| --- | --- |
| Part names, exploded layout, mirroring | `.bob` / `.cob` readers and writers |
| Colorize shader node group (add `highlight2`) | Hard-coded standing pose (use the vendored rig) |
| Panel and operator patterns, presets | Map / level-definition tools, `ba_data` path lookups |

## Open questions

Answered:

- ~~Web UI views S and V~~: S is Spread (exploded view, plus Stretch); V
  is Visibility; R is Rotate (turntable spin). Blender covers them with the
  exploded layout, the outliner and the viewport.
- ~~Rest of the web UI form~~: captured above (Sounds, Physique, Eyes,
  Surface after Meshes).
- ~~Interface shape~~: like the web UI: preview, guides and a form, on a
  character collection with an armature.
- ~~Source of truth for pose~~: the game's rig numbers, vendored.
- ~~Schema source~~: `characterbuilder.py` + `characterranges.py`,
  summarised in `BCHAR_FORMAT.md`, vendored.
- ~~Validation~~: no local build; the server builds on upload and the web UI
  previews it. The addon runs its own pre-upload checks.
- ~~Shared meshes across characters~~: only inside one workspace; anything
  from elsewhere is copied in.

Answered 2026-10-17:

- ~~Matching the web UI's rest pose~~: estimate from the rig and the
  screenshots; close enough is fine.
- ~~Rotation order~~: heading → pitch → roll, intrinsic; Blender `YXZ`
  Euler with `(−p, −r, −h)` (see Coordinates and transforms). Axis mapping
  confirmed by the old addon and the meshes; rotation signs still to be
  checked against the web UI.
- ~~Editing in two places~~: Blender overwrites the local files on export.
- ~~Server limits~~: none known; no limit checks.
- ~~Triggering a preview~~: deferred until bacloud sync runs inside Blender
  (probably an internal bacloud command).
- ~~Limb stretching~~: not needed; rest pose and exploded layout only.
- ~~Sounds and strings~~: sounds are plain strings; strings are shown as
  translation keys only and the `strings/` folder is ignored.
- ~~In-Blender sync~~: not needed for now.
- ~~Blender version floor~~: 4.2 (`blender_version_min = "4.2.0"`); develop
  and test on Blender 5.2.2 as well.
- ~~Attachments, `left_*`, `flippers`~~: JSON-only in the web UI; the addon
  edits them in its Advanced and Attachments sections.
- ~~`team_coloring_strength`~~: meaning unclear, but preserved on import and
  export along with every other unmodelled field.

Still open:

1. **Rotation signs.** Confirm the derived `YXZ` / `(−p, −r, −h)`
   conversion by importing Zoe and Pixel and comparing with the web UI.
