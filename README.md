# blender-addon

Blender addons for BombSquad / Ballistica:

- **[BombSquad Tools](#bombsquad-tools)** [![brainmade.org](https://img.shields.io/badge/brainmade.org-000000?style=flat&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxZW0iIGhlaWdodD0iNzkiIHZpZXdCb3g9IjAgMCA2NyA3OSIgZmlsbD0ibm9uZSI%2BPHBhdGggZmlsbD0iI2ZmZiIgZD0iTTUyLjYxMiA3OC43ODJIMjMuMzNhMi41NTkgMi41NTkgMCAwIDEtMi41Ni0yLjU1OHYtNy42NzdoLTcuOTczYTIuNTYgMi41NiAwIDAgMS0yLjU2LTIuNTZWNTUuMzE1bC04LjgyLTQuMzk3YTIuNTU5IDIuNTU5IDAgMCAxLS45ODYtMy43MWw5LjgwNy0xNC43MTR2LTQuMzVDMTAuMjQgMTIuNTk5IDIyLjg0MyAwIDM4LjM4OCAwIDUzLjkzMiAwIDY2LjUzNCAxMi42IDY2LjUzOCAyOC4xNDNjLS42MzIgMjcuODI0LTEwLjc2IDIzLjUxNi0xMS4xOCAzNC4wNDVsLS4xODcgMTQuMDM1YTIuNTkgMi41OSAwIDAgMS0uNzUgMS44MSAyLjU1IDIuNTUgMCAwIDEtMS44MDkuNzVabS0yNi43MjMtNS4xMTdoMjQuMTY0bC4yODYtMTQuNTQyYy0uMjYzLTYuNjU2IDExLjcxNi04LjI0MyAxMS4wOC0zMC43MzQtLjM1OC0xMi43MTMtMTAuMzEzLTIzLjI3MS0yMy4wMzEtMjMuMjcxLTEyLjcxOCAwLTIzLjAyOSAxMC4zMDctMjMuMDMyIDIzLjAyNXY1LjExN2MwIC41MDYtLjE1IDEtLjQzIDEuNDJsLTguNjMgMTIuOTQxIDcuNjQ1IDMuODJhMi41NTkgMi41NTkgMCAwIDEgMS40MTUgMi4yOTF2OS42OTdoNy45NzRhMi41NTkgMi41NTkgMCAwIDEgMi41NiAyLjU1OXY3LjY3N1oiLz48cGF0aCBmaWxsPSIjZmZmIiBkPSJNNDAuMzcyIDU4LjIyMlYzOC45MzRjLjExOCAwIC4yMzcuMDE4LjM1NS4wMTggOS43NjktLjAxMiAxNy4wNS05LjAxMiAxNS4wMjItMTguNTY3YTIuMzY2IDIuMzY2IDAgMCAwLTEuODIxLTEuODIyYy04LjEwNi0xLjczLTE2LjEyMSAzLjI5Mi0xOC4wOTggMTEuMzQxLS4wMjQtLjAyNC0uMDQzLS4wNS0uMDY2LS4wNzNhMTUuMzIzIDE1LjMyMyAwIDAgMC0xNC4wNi00LjE3IDIuMzY1IDIuMzY1IDAgMCAwLTEuODIxIDEuODJjLTIuMDI4IDkuNTU1IDUuMjUyIDE4LjU1NCAxNS4wMiAxOC41NjguMjM2IDAgLjQ5Mi0uMDI4LjczOC0uMDR2MTIuMjEzaDQuNzMxWm0yLjgzOS0zMi4xNDNhMTAuNjQ2IDEwLjY0NiAwIDAgMSA4LjEyNC0zLjEwNmMuMzUgNi4zNC00Ljg4OCAxMS41NzctMTEuMjI4IDExLjIzYTEwLjU4IDEwLjU4IDAgMCAxIDMuMTA0LTguMTI0Wk0yNy40MDMgMzguMTkzYTEwLjYwNyAxMC42MDcgMCAwIDEtMy4xMTgtOC4xMjNjNi4zNDQtLjM1OCAxMS41ODcgNC44ODYgMTEuMjI4IDExLjIzLTMuMDIzLjE2OS01Ljk3My0uOTYxLTguMTEtMy4xMDdaIi8%2BPC9zdmc%2B)](https://brainmade.org/)  
  Import and export BombSquad's `.bob` (mesh) and `.cob` (collision mesh)
  files, for BombSquad up to 1.7.
- **[Ballistica Cloud Tools](#ballistica-cloud-tools)**  
  Create and edit characters for Ballistica cloud workspaces, for BombSquad
  1.8+.

## Installation

| Addon | Blender version | BombSquad version | Status | Download URL |
|:------|:----------------|:------------------|:-------|:-------------|
| BombSquad Tools | 2.77 - 2.79b | ~ 1.4 | Unmaintained | https://github.com/Mrmaxmeier/BombSquad-Community-Mod-Manager/tree/master/utils/blender |
| BombSquad Tools | >=2.80 | ~ 1.4 | Unmaintained | https://github.com/bombsquad02420/blender-addon/releases/tag/blender4.2 |
| BombSquad Tools | >=4.2 | 1.7 | Supported | https://extensions.blender.org/add-ons/bombsquad-tools/ |
| Ballistica Cloud Tools | >=5.2 | >=1.8 | Experimental | https://extensions.blender.org/add-ons/ballistica-cloud-tools/ |

> [!IMPORTANT]
> BombSquad Tools works with BombSquad up to 1.7 only. BombSquad 1.8 no
> longer supports offline modding: mods are built in Ballistica cloud from
> workspaces, which is what Ballistica Cloud Tools is for.

> [!NOTE]
> Other versions of blender and bombsquad that are not listed may work.
> I am not tracking the API changes in blender and bombsquad closely.
> If you have had success or issues, please update the version ranges here.

## BombSquad Tools

Lives in [`bombsquad-tools`](bombsquad-tools). Imports and exports BombSquad's
`.bob` and `.cob` files and map location definitions, with presets for maps
and characters.

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
cd ballistica-cloud-tools
make install BLENDER=/path/to/blender   # build and install + enable in Blender
```

See [SETUP.md](SETUP.md) for the other targets.

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
