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

```bash
make cloud-test                                  # pure-Python tests, no Blender
make cloud-blender-test BLENDER=/path/to/blender # end-to-end in Blender (needs ../ClassicCharacterAssets)
make cloud-build BLENDER=/path/to/blender        # builds ballistica_cloud_tools-<version>.zip
```
