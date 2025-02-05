#! /usr/bin/env nix-shell
#! nix-shell -i bash -p entr

# This script watch for changes in the addon directory,
# and automatically builds the addon using blender.

# find ./addons/bombsquad-tools/ | entr -s 'blender --command extension build --source-dir $(realpath ./addons/bombsquad-tools/) --output-dir $(realpath ./addons/bombsquad-tools/)'

find ./addons/bombsquad-tools/ | entr -cs 'date --rfc-email; (cd ./addons/bombsquad-tools/ && zip -r bombsquad-tools-3.0.0.zip . -x *.zip -x *.md)'
