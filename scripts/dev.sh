#! /usr/bin/env nix-shell
#! nix-shell -i bash -p entr

# This script watch for changes in the addon directory,
# and automatically builds the addon using blender.

# find ./addons/io_mesh_bombsquad/ | entr -s 'blender --command extension build --source-dir $(realpath ./addons/io_mesh_bombsquad/) --output-dir $(realpath ./addons/io_mesh_bombsquad/)'

find ./addons/io_mesh_bombsquad/ | entr -cs 'date --rfc-email; (cd ./addons/io_mesh_bombsquad/ && zip -r io_mesh_bombsquad-3.0.0.zip . -x *.zip -x *.md)'
