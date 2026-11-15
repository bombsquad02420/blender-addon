# Upstream: ballistica

The addon mirrors how the game reads and draws a character from
[ballistica](https://github.com/efroemling/ballistica): the `.bchar`
format, its ranges, the rig, and how attachments are built.

|                     |                                                                     |
| ------------------- | ------------------------------------------------------------------- |
| Synced with commit  | `d6049a667286ff906406ccc7d635f3d315256df3` (`v1.8.7-6`, 2026-11-04) |
| Game version        | 1.8.7 (build 23089)                                                 |

To see what changed upstream since this sync:

```bash
git -C ../../ballistica fetch
git -C ../../ballistica log --oneline d6049a667286..origin/main -- \
  tools/bacommon/characterranges.py tools/bacommon/characterrig.py \
  tools/bacommon/characterbuilder.py \
  src/ballistica/base/support/character_def.h \
  src/ballistica/base/support/character_def.cc \
  src/ballistica/scene_v1/node/spaz_node.cc \
  src/ballistica/base/dynamics/bg/bg_dynamics_character.cc \
  src/ballistica/base/graphics/gl/program/program_object_gl.h \
  src/assets/ba_data/python/bascenev1lib/actor/spazappearance.py
```

Also read the character entries in ballistica's `CHANGELOG.md` since the
synced version. After syncing, update the commit and version above.

## File map

| This addon                         | Upstream                                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------------------------ |
| `rig.py`                           | `tools/bacommon/characterranges.py` (ranges), `characterrig.py` (rig table), `characterbuilder.py` (fields, defaults), `spaz_node.cc` |
| `pose.py`, `scene.py`              | `spaz_node.cc` (body placement, joints, shoulder offset)                                         |
| `eye_scene.py`                     | `spaz_node.cc` (`DrawEyeBalls`: eye position and size)                                           |
| `attach_scene.py`, `attachments.py`| `bg_dynamics_character.cc` (joint chain, curl, length, radius), `spaz_node.cc` (attachment placement), `character_def.h` |
| `nodegroup.py`                     | `program_object_gl.h`, `spaz_node.cc` (color, mask and tint shading)                             |
| `BCHAR_FORMAT.md`                  | `character_def.h` / `.cc`, `characterbuilder.py`, `spazappearance.py`                            |

Not in ballistica: the web UI's preview (spread, part layout) was checked
against its JSON dumps (`tests/fixtures/pixel_preview.json`, agent_johnson).

## Sync history

- **1.8.3** (`a9a4a9785`): attachment curl 1 is a half turn per joint (was
  90°); the eye scale minimum is 0.1 (was 0.5). The addon was started on
  the commit before and caught up at `d6049a667`. The web UI still bends
  90° per curl (its agent_johnson dump), so curled antennas look more bent
  in Blender and the game than in the web UI's preview.
