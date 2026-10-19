# blender-addon

Blender addons for BombSquad / Ballistica:

- **[`bombsquad-tools`](bombsquad-tools)**: import and export BombSquad's
  `.bob` and `.cob` files (the classic, pre-1.8 asset pipeline).
- **[`ballistica-cloud-tools`](ballistica-cloud-tools)**: create and edit
  characters for Ballistica cloud workspaces (BombSquad 1.8+). See
  [Ballistica Cloud Tools](#ballistica-cloud-tools) below.

## Installation

| Blender version |Bombsquad Version | Status        | Download URL                                                                            |
|:----------------|:-----------------|:--------------|:----------------------------------------------------------------------------------------|
| 2.77 - 2.79b    | ~ 1.4            | Unmaintained  | https://github.com/Mrmaxmeier/BombSquad-Community-Mod-Manager/tree/master/utils/blender |
| >=2.80          | ~ 1.4            | Supported     | https://github.com/bombsquad02420/blender-addon/releases/tag/blender4.2                 |
| >=4.2           | >=1.7            | Experimental  | https://extensions.blender.org/add-ons/bombsquad-tools/                                 |

> [!NOTE]
> Other versions of blender and bombsquad that are not listed may be work.
> I am not tracking the API changes in blender and bombsquad closely.
> If you have had success or issues, please update the version ranges here.

## Usage

## Ballistica Cloud Tools

Since BombSquad 1.8, mods are cloud **workspaces**: folders of `.bchar`,
`.obj`, `.png` and `.wav` files that the cloud builds into game assets. This
addon edits characters in a local copy of a workspace; syncing with the cloud
happens outside Blender (`bacloud workspace get` / `put`, or `bacloud-ts`).

Requires Blender 5.2+. In the 3D viewport, open **N panel → Ballistica**:

- **New Character** starts a cuboid character in a workspace folder;
  **Import Character** opens a `.bchar`; **Export Character** writes meshes,
  textures and the `.bchar` back (only what changed).
- The characters list picks which character the panel edits. Sections follow
  the web UI's form (Identity, Textures, Meshes, Sounds, Physique, Eyes,
  Surface), plus **Attachments** for hair, antennas, wings and the like.
- **Check** reports problems before you upload.

Build and install:

```bash
make cloud-build BLENDER=/path/to/blender
blender --command extension install-file -r user_default --enable ballistica_cloud_tools-0.1.0.zip
```

Design notes: [`DESIGN.md`](ballistica-cloud-tools/DESIGN.md); the
character format: [`BCHAR_FORMAT.md`](ballistica-cloud-tools/BCHAR_FORMAT.md).

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## Acknowledgment

- This addon is an enhancement of the previous addons made by 
[Mrmaxmeier](https://github.com/Mrmaxmeier/BombSquad-Community-Mod-Manager/tree/master/utils/blender) (Blender 2.79)
and
[shantanuaryan67](https://github.com/shantanuaryan67/BombSquad-Community-Mod-Manager/tree/master/utils/blender_2-80) (Blender 2.83+ (Windows only))

- [Alan North](https://github.com/AlansCodeLog/blender-debugger-for-vscode): VS Code debugger addon

## License

[GNU General Public License v3.0](LICENSE)

----

<picture>
<source
	media="(prefers-color-scheme: dark)"
	srcset="https://brainmade.org/white-logo.svg"
/>
<img
	src="https://brainmade.org/black-logo.svg"
	alt="The Brainmade Mark"
	width="80"
/>
</picture>