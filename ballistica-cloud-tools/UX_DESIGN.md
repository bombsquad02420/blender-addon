# Ballistica Cloud Tools — Guided editing (design)

Status: agreed 2026-10-22; steps 1–3 built (see DESIGN.md for how they work). Extends [DESIGN.md](DESIGN.md),
which describes the addon as it is.

## Who it's for

Curious kids modding a mobile game. They've watched some Blender tutorials,
but have little experience with code or game art. bacloud sync (planned
separately) keeps them out of the terminal. This plan is about not getting
stuck **inside Blender**.

Principles:

- **Nothing is locked hard.** Moving a part aside to model, paint or unwrap
  it is useful. When something drifted in a way export ignores (or can't
  store), the panel says so in plain words, and offers to fix it.
- **Pick, don't type.** Meshes and textures are chosen from Blender's own
  data, not by typing workspace paths.
- **One place.** What a part or texture needs (its mesh or image, export
  path, UV map, texture settings) is shown under its row, not spread over
  Blender's properties editor.

## Build order

1. Repair, soft locks and warnings.
2. Eye handle.
3. Data model: parts and textures lists with pickers, export paths on
   meshes and images, Make unique, duplicate-path check, per-character eye
   toggle.
4. *(later)* Paint brushes for the colour mask.
5. *(later)* Attachment templates.

## 1. Repair, soft locks and warnings

**Reset to T-Pose** only resets the **pose**: the rig back onto its root,
every bone back to rest. It's the only button that changes the pose (preview
poses may come later).

**Repair** fixes everything else, and never touches the pose, mesh shapes or
paint. Two buttons:

- **Fix Selected**: the parts, eyes or attachment objects that are selected.
- **Fix Whole Character**: everything below.

What Repair checks and fixes:

| Problem | Fix |
| --- | --- |
| A body part, eye or attachment mesh was moved, rotated or scaled in Object Mode (export ignores that) | Put it back on its bone. For body parts there's also **Keep**: apply the change to the mesh, so it is exported |
| A part lost its bone parent (Alt+P, or its rig was deleted) | Parent it to its bone again |
| A part is hidden (H) | Unhide it |
| A part doesn't use the character's material (preview won't match) | Give it back |
| An attachment anchor is scaled (`.bchar` can't store that) | Reset its scale; its scale is padlocked (soft lock: it can be unlocked) |
| The rig was deleted, or its bones were moved in Edit Mode | Rebuild the rig at the game's joints and re-parent everything |
| The root, eyes, guides, attachment handles or a group collection are missing | Rebuild them |
| A file from an older addon version (no parts list, no eye handle) | Add them |

The same problems show in a **Needs fixing** box at the top of the panel
(only when there are any), each with its fix button, and are listed by Check
and reported by Export. They are notes, not errors: export still works.

## 2. Eye handle

The engine places each eye at `head + eye_scale × eye_offset` and sizes it by
`eye_scale` (`spaz_node.cc`, `DrawEyeBalls`: scale, then translate). So
changing the size also moves the eye. The panel and the viewport work in
plain terms instead, converted on import and export like coordinates are:

- **Position**: where the eye sits from the head centre (`eye_scale ×
  eye_offset`), game axes.
- **Size**: `eye_scale`. Changing it keeps the position.

An **eye handle** (a sphere empty on the head bone, around the +X eye) holds
both: move it to move the eyes, scale it (uniformly) to size them. The other
eye mirrors it. Rotation is padlocked. Handle and panel numbers stay in sync
both ways, like attachment handles. Repair makes uneven scale even and clears
rotation.

## 3. Data model

### Meshes and images carry their export path

Each Blender mesh and image used by a character stores its **export path**
(logical path, e.g. `meshes/zoe_head`). Images also store their texture
settings, from `workspace.json` (`assets_v1` `tex_v1` entries):

| Setting | Values (default first) |
| --- | --- |
| Role (`texture_role`) | default, source_premultiplied, straight_alpha, data, premultiplied_data |
| Quality (`texture_quality`) | default, low, high (custom is kept but not editable) |
| Wrapping H/V (`texture_wrapping_h/_v`) | clamp, repeat |
| Alpha (`texture_alpha`) | auto, yes, no |

Loaded from `workspace.json` when the image is loaded; written back on export
(non-default values set, default ones removed, every other key untouched).
Colour and icon masks must be a data role; export sets `data` if not.

### Characters: only what's loaded

The character list shows characters loaded in Blender or created there. Each
row has an **eye toggle** to hide or show that character. Workspaces are not
imported whole: loading one character loads only its meshes and textures.

### Parts list

A fixed list in rig order: Head, Torso, Pelvis, Upper Arm, Forearm, Hand,
Upper Leg, Lower Leg, Toes, then Left Upper Arm … Left Toes.

- A **checkbox** on optional rows: pelvis, forearm and hand (the engine
  draws nothing for an empty one), and every Left row. Off greys the row and
  leaves the part out of the `.bchar`; its mesh is kept, so ticking it back
  on restores it. Required parts have no checkbox.
- A **Left** row off means the left side mirrors the right part. Ticking it
  on gives the left side its own mesh, starting as a copy of the right one.
  The "left parts are modelled as right parts" hint shows only on a selected
  Left row.
- **Selection follows the list** both ways, like attachments.

Under the list, the selected part's:

- **mesh picker** (Blender meshes, searchable) with **New** (a cuboid for
  that part) and, when shared, *used by N characters* and **Make unique**;
- **UV map** to export (the mesh's render-active UV map: Blender's camera
  icon), for people who bake from one UV map to another;
- **export path**;
- Flippers and its hint, on the arm rows.

### Textures list

A fixed list of two: **Colour** and **Colour mask**. Under it, the selected
texture's **image picker** with **New** (a blank image at a sensible size;
Non-Color for the mask), *used by N characters* / **Make unique**, export
path and the texture settings above. Picking an image updates the
character's material (creating it if needed, as on an Empty character).
Clearing it leaves the part plain white instead of broken. The icon and icon
mask stay in Identity.

### Checks

- Two different meshes, or two images, with the same export path.
- A used part without a mesh (its picker cleared).
- Everything Repair finds (as notes).

### Panel

1. Characters (with the eye toggles), Import/Export, Check, and the
   *Needs fixing* box
2. Visibility (Frame, Reset to T-Pose, Spread, groups)
3. Identity (with the icons)
4. Parts
5. Textures
6. Physique, Eyes, Attachments, Sounds

### Not in steps 1–3

- Attachment segments keep their path pickers for now; moving them to mesh
  and image pickers is a follow-up.
- Brushes and attachment templates (steps 4 and 5).
- The in-game preview needs an API that isn't documented yet; see
  `bacloud-ts/docs/bacloudstate-proposal.md`.
