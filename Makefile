ADDON_NAME := $(shell cat ./bombsquad-tools/blender_manifest.toml | grep -oP '(?<=^id = \").*(?=\")')
VERSION := $(shell cat ./bombsquad-tools/blender_manifest.toml | grep -oP '(?<=^version = \").*(?=\")')

.PHONY: dev tag

all: $(ADDON_NAME)-$(VERSION).zip

$(ADDON_NAME)-$(VERSION).zip: ./bombsquad-tools ./bombsquad-tools/**
	zip -r $@ $<

dev:
	find ./bombsquad-tools/ | entr -cs 'date --rfc-email; make'

clean:
	rm -rf *.zip

tag:
	git tag v$(VERSION)
