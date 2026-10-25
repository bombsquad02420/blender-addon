# Ballistica Cloud Tools for Blender — Design

Status: updated 2026-10-19 to match the implemented addon (characters
list, attachments, New Character); game-code findings in
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
  5.2 ships Python 3.13. A Blender-side SDK means a fresh port of the TS SDK
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

Everything lives in **View3D → N panel → Ballistica**.

### Characters list

The top of the panel lists the scene's characters. The selected row is the
**active character**: every section below, plus Export, Check and Reset to
T-Pose, acts on it. It's stored on the scene as a pointer to the character's
collection (`scene.ballistica_active_character`), so it doesn't depend on
what's selected:

- Clicking a row makes that character active.
- Each row's eye icon hides or shows that whole character.
- Clicking any object of a character in the viewport (body part, eye,
  attachment) makes it active.
- New Character and Import make the new character active.
- With no choice yet, or after the chosen character is deleted, the panel falls back to the active object's character, then the
  scene's first.

Beside the list: **+** (New Character) and **−** (Remove Character); below
it **Import Character · Export Character**, the character's workspace folder
and `.bchar` path, its triangle count and **Check**, the *Needs fixing* box
(when something drifted) and the Repair buttons. **Frame Character** and
**Reset to T-Pose** are in Visibility; the Standard Colors fix is in
Textures' Colors.

### Scene layout

One character is one **collection**, with a child collection per group:

```
zoe                         (collection; .bchar settings live here)
├── zoe_root                (flat circle: move the whole character)
├── zoe Rig                 (hidden on import)
│   ├── zoe_rig             (armature, web UI preview pose)
│   └── attach0, attach0.0… (attachment anchors and segment handles)
├── zoe Head                (head)
├── zoe Body                (torso, pelvis)
├── zoe Arms                (upper_arm.R/.L, forearm.R/.L, hand.R/.L)
├── zoe Legs                (upper_leg.R/.L, lower_leg.R/.L, toes.R/.L)
├── zoe Attachments         (attachment segment meshes)
├── zoe Eyes                (the game's eyeball, iris and eyelid; hidden on import)
└── zoe Guides              (physics bodies; never exported)
```

**Visibility** (a sub-section) toggles these groups and has the **Spread**
slider (exploded view, as the web UI's S view).

### Armature: pose and placement

An armature built from the vendored rig numbers, in the web UI's preview
pose (`pose.py`). Bones: `pelvis`, `torso`, `head`, `.R`/`.L` pairs for
`upper_arm`, `forearm`, `hand`, `upper_leg`, `lower_leg`, `toes` (and
`heel`), `wing`, and the offset bones `shoulder_offset.*` and
`eye_offset.*`.

- Body parts are **bone-parented** with their rest placement in the parent
  inverse, so their own transform is identity. Moving a part aside to work
  on it is never exported, and **Repair** puts it back. Export
  writes each part's mesh with its **modifiers applied** (as shown in the
  viewport), still in the part's own space.
- `shoulder_offset` and `eye_offset` are panel values that drive their
  offset bones.
- Rig dimensions (body sizes, joint anchors, start heights) are fixed by
  the game. Per-character radii (`torso_radius`, `thigh_radius`,
  `ankle_radius`) resize the guides.

### Collection properties: the form

All `.bchar` settings are stored on the character collection as a
registered property group (`collection.ballistica_character`): typed,
saved in the `.blend`, with min/max from `characterranges.py`. The panel
shows them in the web UI form's order, with the same defaults:

| Section | Fields |
| --- | --- |
| Identity | `name` (translation key), the icon and icon mask (image pickers: `icon_texture`, `icon_mask_texture`) |
| Textures | **Colors** first (`color`, `highlight`, `highlight2` as swatches, `reflection_scale`, a closed *Profile Editor* with `highlight_name`, `highlight_editing`, `highlight2_name`, `highlight2_editing`, and the Standard Colors fix when needed), then the Textures list (below): `color_texture`, `color_mask_texture` |
| Parts | the Parts list (below): `head_mesh` … `toes_mesh`, the `left_*_mesh` overrides, `flippers` |
| Sounds | the Sounds list: six fixed rows (jump, attack, impact, death, pickup, fall), each showing how many sounds it has and how many are missing; the selected one as comma-separated audio paths, with a picker to add one from the workspace |
| Physique | `torso_radius`, `shoulder_offset`, `thigh_radius`, `ankle_radius`, `step_separation`, `idle_arm_stiffness`, `arm_swing`, `idle_sway` |
| Eyes | `eye_style_left/right`, Size and Position (`eye_scale`, `eye_offset`; see below), `eye_color`, `eyeball_color`, `eyelid_color`, `eyelid_angle` |
| Attachments | see below |

`flippers`, the `left_*` overrides and attachments aren't in the web UI
form (they're JSON-only there).

- **Names are file names.** A mesh's or image's Blender name is its path
  inside its folder: mesh `blob_head` is `meshes/blob_head`, image
  `blob_color` is `textures/blob_color` (no extension: the cloud builds the
  formats); a name with a slash is in a subfolder. Imported files are named
  that way, and renaming one renames its file. Names that make poor file
  names (capitals, spaces, symbols, Blender's `.001` ending) show in Needs
  fixing; **Rename** makes them lowercase with underscores (`.001` →
  `_001`).
- **Pickers.** Every mesh and image (parts, the body textures, attachment
  segments, and the icon and icon mask in Identity) is a picker over
  Blender's data, with buttons: the eyedropper (meshes: take one from an
  object in the viewport), the **folder** (pick a mesh or image from the
  workspace folder, searchable; it's loaded into Blender) and **+** (a new
  one). The `.bchar` paths are written from the pickers on export.
- **Parts list.** One row per body part in rig order (right side for limbs),
  then a Left row per limb. Each row holds the Blender **mesh** the part
  uses (picked from Blender's meshes, taken from an object in the viewport
  with the **eyedropper**, or **+** for a box in the part's size);
  the part's objects follow it. Optional parts (pelvis, forearm, hand) and
  Left rows have a checkbox: an optional part that's off has no objects (its
  mesh stays in the row), and a Left row that's on gives the left limb its
  own mesh, starting as a copy of the right one. Below the list: the
  selected row's mesh and its **UV map** (the render-active one is
  exported).
  The eyedropper shares the object's mesh; it says so when the object's own
  transform or modifiers are left behind (only the mesh comes across).
  Clicking a row selects the part; clicking a part picks its row. The mesh
  fields are written from the rows on export; a row without a mesh (a file
  that wasn't found) keeps its field.
- **Textures list.** Two rows, Color and Color Mask, each holding a
  Blender image (picked, or **+** for a blank one: white, or a black mask
  that tints nothing). Picking one shows it on the body material (made if
  the character has none); clearing one unlinks it, so the body shows plain
  white rather than a broken texture. Below: the image's
  **Build Settings** (role, quality, wrapping, alpha), read from and written
  to `workspace.json`. A mask always gets a Data role on export. An image
  picked from elsewhere is saved under its name in `textures/`.
- **Painting.** **Paint** (under the selected texture) switches to Texture
  Paint on the selected part (or the torso), painting that image whatever
  the material shows; **Done** goes back to Object Mode. The mask has ten
  brushes, shipped in the addon's asset file (always in the brush shelf,
  under the "Ballistica Cloud Tools" library's Mask Brushes catalog, with
  thumbnails), shown as one row per tint (Player Color = red, Highlight =
  green, Highlight 2 = blue): **Add** adds that channel, keeping other tints;
  **Erase** subtracts it, keeping the others; **Only** paints that channel
  alone with a hard edge. A last *All Tints* row has just **Erase**,
  subtracting all three. The brush grid shows only while painting the mask. The panel's
  brush buttons also set Blender's shared brush color; the paint box has a
  **Shared Brush Color** toggle and warns while it's on, since a brush picked
  from the shelf would paint the shared color instead of its tint.
- **Shared meshes and images.** When another character uses the selected
  part's mesh or texture, the panel says which, with **Make Unique**: a copy
  (unsaved paint included) with its own name. Check reports two meshes or
  images from different files with the same path in one workspace.
- **Flippers** only shortens the upper arm under boxing gloves; the engine
  still draws any forearm and hand meshes that are set. If both are set,
  the Parts list and Check show a hint (not an error).
- **Unknown fields** (a newer format, e.g. per-part looks and team coloring
  strengths the engine already reads) are kept from the stored raw JSON and
  written back unchanged; untouched characters round-trip byte for byte.

### Attachments

An **Attachments** section with a list (**+** add, **−** remove, up/down
reorder), like Material Slots. Each row reads *target · kind · side*, with
a warning icon if the attachment breaks a rule. Below the list, the
selected attachment:

- **Target, Side, Kind.** Only valid choices are offered: head, torso and
  pelvis take side `both` only; limbs and `wing` take kind `static` only.
  The segment count follows the kind (`antenna_3` has 3 segments, …).
  Changing any of these rebuilds the attachment.
- **Placement** (open by default): the attachment's `transform`, where it
  hangs on the target part, in game axes (Y up, Z forward); rotation as
  heading, pitch, roll in degrees. **Select Anchor** selects its handle.
- **Spring** (closed; springy kinds only): stiffness, damping, drag, curl,
  length, radius, and their per-segment `*_change` when there's more than
  one segment.
- **Segments** (open): the segment list, and the selected segment's mesh
  (picker, eyedropper, **+** for a small box), texture and mask (pickers,
  **+** for a blank image; both empty: the body's textures), each with
  *also used by* / Make Unique. The `.bchar` paths are written from
  the pickers; a path whose file wasn't found is kept and flagged. **Art Offset** (closed) holds the segment's own
  `transform`: where its mesh sits on its physics segment. For a
  single-segment static attachment it moves the mesh just like Placement;
  for springy kinds Placement moves the pivot and Art Offset moves the mesh
  on its swinging segment. **Select Art** selects its handle.

**Placement handles.** Each attachment has an anchor empty, bone-parented
to its target (its own location/rotation, in `YXZ` mode, are exactly the
`.bchar` translate/rotate), and a handle per segment under it (the kind's
joint chain in its parent inverse, the segment transform as its own). The
handles are the saved placement and live in the Rig collection. Meshes hang
from the handles with an identity transform, so moving a mesh aside to
paint it is never saved, and Repair puts it back. Left copies of
`both`-sided limb attachments follow the right side by drivers. Panel
numbers and handles stay in sync both ways.

**Selection.** Clicking an attachment or segment row selects its meshes (in
Object Mode); clicking an attachment mesh in the viewport selects its row.
Add, remove, reorder and kind/target/side changes rebuild the attachment
objects and then select the active attachment's new meshes.

The **+** beside the list is a menu: **Empty** (an `antenna` on top of the
head with a placeholder box segment, `meshes/<character>_attachment<n>`) or
one of the **templates** (`attach_templates.py`): Hat, Crown, Horns, Bobble
Antenna, Ponytail, Backpack, Cape, Tail, Wings, Shoulder Pads, and for the
hands a Sword (right), Shield (left) and Claws (both). A template
sets the target, kind, placement and spring tuning, and copies in its own
generated low-poly mesh per segment and a small color texture and mask
(tinted with the player color or a highlight, or not), named
`meshes/<character>_<template>` and `textures/<character>_<template>`. The
files ship in `assets/attachments/` (written by `make template`), so they
can be replaced by hand-made ones.

### Eye handle

The engine places each eye at `head + eye_scale × eye_offset`, so in the
`.bchar` a bigger eye also sits further out. The panel shows **Size**
(`eye_scale`) and **Position** (`eye_scale × eye_offset`, from the head
centre) instead; changing the size keeps the eyes where they are. An **eye
handle** (a sphere empty on the head bone, around the +X eye, in the Rig
group like attachment anchors) holds them: move it to move the eyes, scale it
to size them, turn it about the forward axis to tilt the eyelids
(`eyelid_angle`, clamped to ±30°); the other eye mirrors it, and the other
rotation axes are padlocked. **Select Eye Handle** (in Eyes) shows the Rig
group and selects it. Export reads it, like attachment handles.

### Preview and guides

- **Material:** the bundled "Ballistica Colorize" node group, with
  `color`, `highlight` and `highlight2` driven by the panel. **Use Standard
  Colors** sets the scene's view transform to Standard so colors match the
  web UI (Blender's default AgX washes them out).
- **Guides:** head and torso balls, pelvis box, arm-segment and leg
  capsules, toes balls and the roller, sized from the rig and the
  character's radii (the web UI's B view).
- **Eyes:** the game's own eyeball, iris and eyelid meshes and textures,
  bundled with the addon, placed and colored from the Eyes settings.
- **Pose:** the armature in the Rig collection (the web UI's P view).
- **Spread:** the Visibility section's slider (the web UI's S view).
- **Frame Character** frames the rig in the viewport.

### Repair

**Reset to T-Pose** only resets the pose (the rig back onto its root, every
bone back to rest). **Repair** fixes what drifted in the scene, without
touching the pose, mesh shapes or paint: parts moved, detached, hidden or
given another material; scaled attachment anchors (their scale is
padlocked, softly); a deleted rig or bones moved in Edit Mode; a missing
root, eyes, guides, attachment handles, group collection or part object.
The problems show in a *Needs fixing* box under Check, each with its fix
(and **Keep** for a moved part: apply the move to its mesh), and as notes in
Check and Export. **Fix Selected** and **Fix Whole Character** fix them all.
See [UX_DESIGN.md](UX_DESIGN.md).

### Format version

Each character collection is stamped with the addon's scene format
(`format_version`, see `migrate.py`). A character older than the addon
shows only an **Update Character** box, which runs the migration steps it's
missing. Development versions are never migrated; the steps start empty at
version 1, the first release.

### Pre-upload checks

**Check** (also run on export) reports errors (the build would fail or the
character would be broken) and warnings, then a summary as the last message
("3 errors and 5 warnings. Click to view all": the status bar shows only the
last one). It reports: required fields; referenced files
missing from the workspace (meshes and textures made in Blender count, since
export writes them); masks not marked `texture_role: data`; meshes without
UVs; attachment rule problems; the Flippers hint; and a name or highlight labels that aren't translation keys (the
fields show the expected shape as a placeholder). There are no known
server limits on vertex counts or texture sizes, so the checks don't invent
any.

## Character workflow

### Import character

**Import Character** (or File → Import → Ballistica Character), then pick a
`.bchar` inside a workspace folder (one with a `workspace.json` above it):

1. Create the collection and its groups, and fill its settings.
2. Build the armature in the preview pose, and the root.
3. Load each part's OBJ (game axes → Blender) and bone-parent it; left
   limbs share the right side's mesh, or use their `left_*` mesh.
4. Build the material, eyes, attachments (with handles) and guides.
5. Make it the active character.

Loading doesn't change your selection.

### Edit

- Model, UV-map and texture-paint the parts. Limbs are edited on the `.R`
  side; the `.L` side shares the mesh.
- Edit settings in the panel; the preview follows live.
- Place attachments with their handles or the Placement numbers.

### Export character

**Export Character** writes into the character's workspace folder
(overwriting local files):

1. Read the attachment handles into the settings.
2. Write each part's mesh, and each attachment segment mesh, that is new or
   changed since import or the last export (modifiers applied, part-local,
   triangulated, UVs and normals; Blender axes → game). Unchanged meshes
   aren't rewritten; the check covers modifier changes too.
3. Save textures edited, made or picked in Blender as PNG at their export
   paths.
4. Write the body textures' build settings into `workspace.json` (and mark
   the icon mask `texture_role: data`), leaving everything else in it as it
   was.
5. Write the `.bchar`, keeping unknown fields.

**Blender's copy wins:** edits made in the web UI since import are lost
unless you `workspace get` and re-import first. Then sync with
`bacloud-ts workspace put` and check the result in the web UI.

### New character

**New Character** asks for a workspace folder and a lowercase name, then
creates the collection, rig, guides, eyes and a cuboid body: one box per
part, with limbs as long as the default Spaz's and about as thick as the
game's collision capsules, the head a cube inside the head ball. A generated
atlas, color mask (body takes the player color, forearms and shins the
highlight) and icon go with it. All files are named after the character
(`characters/<name>.bchar`, `meshes/<name>_<part>.obj`,
`textures/<name>_color.png`, …). It refuses names already used in the
workspace. **Nothing is written until Export**; the display name's `.bstr`
isn't created (the addon ignores `strings/`).

## Self-contained

The addon never reads game or ballistica files at runtime. Everything it
needs ships inside it:

- the rig numbers (`characterrig.py`) and ranges (`characterranges.py`),
  copied into `rig.py` with a note of the ballistica version they came from;
- the `.bchar` field list and defaults (`characterbuilder.py`);
- the "Ballistica Colorize" node group and the game's eye meshes and
  textures, in `assets/ballistica_assets.blend` (generated at build time by
  `make build` in this folder);
- the new-character template (`template.py`).

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
- ~~Blender version floor~~: 5.2 (`blender_version_min = "5.2.0"`),
  developed and tested on 5.2.2. The bundled asset `.blend` is generated at
  build time, so build releases with the minimum supported Blender.
- ~~Attachments, `left_*`, `flippers`~~: JSON-only in the web UI; the addon
  edits them in its Meshes and Attachments sections.
- ~~`team_coloring_strength`~~: how strongly team colors tone a highlight;
  the engine reads it per highlight (`highlight_team_coloring_strength`,
  `highlight2_team_coloring_strength`). Not in the form; preserved on
  import and export along with every other unmodelled field.

Still open:

1. **Rotation signs.** The derived `YXZ` / `(−p, −r, −h)` conversion puts
   Zoe's hair and Pixel's wings where the web UI shows them by eye; it
   hasn't been checked number for number against the server's conversion.
