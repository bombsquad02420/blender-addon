```bash
$ git clone https://github.com/bombsquad02420/blender-addon.git
$ cd blender-addon
```

```bash
$ nix-shell
nix-shell$ uv sync
nix-shell$ code bombsquad_tools.code-workspace
```

## Ballistica Cloud Tools

Its own Makefile, with the same targets as `bombsquad-tools`. Run them in
`ballistica-cloud-tools/` (or with `make -C ballistica-cloud-tools <target>`),
passing the Blender to use with `BLENDER=/path/to/blender` (default: `blender`
on `PATH`).

```bash
cd ballistica-cloud-tools
make                # versioned ballistica_cloud_tools-<version>.zip (refuses uncommitted changes)
make dev            # ballistica_cloud_tools-dev.zip from the working tree
make watch          # rebuild the dev zip on every change (needs entr)
make install        # build the dev zip and install + enable it in Blender
make test           # pure-Python tests, no Blender
make blender-test   # end-to-end in Blender (needs ClassicCharacterAssets next to the repo)
make clean          # remove the zips
make tag            # tag ballistica-cloud-tools-v<version> on main and push it
make publish        # upload the versioned zip to extensions.blender.org
```

Tags are `ballistica-cloud-tools-v<version>` so they don't trigger the bombsquad-tools release
workflow (`v*`).
