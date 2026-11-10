# Manual checks

What `make test` and `make blender-test` can't cover, because headless
Blender has no viewport clicks, brush strokes, asset shelf or message bus.
Run through this list in Blender after changing the related code. Start from
a fresh install (`make install`) and a restarted Blender.

## Workspace and names

- [ ] **Choose Workspace.** In a new file: only the workspace row shows.
  Choose… a folder without a `workspace.json`: refused. The workspace
  folder: the list, New and Import appear.
- [ ] **Rename.** Rename a character in the outliner: the panel's Name and
  "Exports as" follow, and its root, rig and groups get the new name.

## Picking and handles

- [ ] **Part eyedropper.** Parts: select a row, click the eyedropper, click
  another object in the viewport. The part shows that mesh; your selection
  doesn't change. With a scaled object: a warning says its transform was
  left behind. Esc and right-click cancel.
- [ ] **Pick from workspace.** The folder button on a part, a texture, a
  segment and the icon: a searchable list of the workspace's meshes or
  images opens; picking one shows it.
- [ ] **Segment eyedropper.** The same from an attachment segment's Mesh row.
- [ ] **Attachment handles.** Select Anchor / Select Art Anchor, then drag and
  rotate the handle: the attachment follows, and Export writes where it
  is now.
- [ ] **Anchor limit.** Drag an attachment anchor far from its part: it
  stops 0.5 out along each axis.
- [ ] **Attachment guides.** Turn on Guides; add an antenna_3: three wire
  capsules along the chain. Change Length, Radius and Curl (First and
  Last): the capsules follow; Curl bends only the capsules, not the art.
- [ ] **Eye handle.** Select Eye Handle (the Rig group shows). Move it: the
  eyes move and Position follows. Scale it: Size follows and the eyes stay
  put when Size is typed. Turn it about its free axis: the eyelids tilt and
  stop at ±30°.
- [ ] **Selection sync.** Clicking Parts and Attachments rows selects their
  objects; clicking a part or attachment mesh in the viewport selects its row
  and makes its character active.

- [ ] **Attachment templates.** Attachments → + → each template: it
  appears in a sensible spot on the body, already selected; springy ones
  (antenna, ponytail, cape, tail) look right once uploaded and moving in the
  game.

## Painting

- [ ] **Paint / Done.** Colors → the brush button beside Color: Texture
  Paint on the selected part, painting the color texture; the Textures list
  selects it and the Paint panel shows Painting. Done returns to Object Mode.
- [ ] **Textures panel.** Lists only the character's exported images (body,
  icons, attachment textures), each with what uses it; selecting one shows
  its build settings.
- [ ] **Mask brushes.** The brush button beside Color Mask: the Paint panel's
  brush grid appears. Paint
  over each other with Add (tints combine: red + green looks yellow in the
  mask), Erase (only that tint goes), Only (hard edge, other tints gone) and
  All Tints → Erase (back to black).
- [ ] **Attachment painting.** A template's segment → the brush button on
  its mask: the attachment is painted, with the brush grid.
- [ ] **Shelf brushes.** Ballistica Cloud Tools library → Mask Brushes:
  thumbnails show. With Shared Brush Color off, each brush paints its own
  tint. With it on, the paint box warns.
- [ ] **Reload.** Reload the addon (e.g. `bpy.ops.script.reload_addon()`):
  the shelf still lists the brushes, and the panel's brush buttons work.

## Panel and reports

- [ ] **Check summary.** With several problems, Check ends with a summary
  ("N errors and M warnings. Click to view all"); clicking the status bar
  message lists them all.
- [ ] **Report a Problem.** Help → Report a Problem opens the GitHub issue
  form with the addon, Blender and OS versions filled in (once the form is on
  the default branch).
- [ ] **Layouts.** Look over every section at the N panel's default width:
  nothing cut off, gaps between sections, icons on every header.
