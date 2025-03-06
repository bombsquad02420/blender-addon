ADDON_NAME := $(shell cat ./bombsquad-tools/blender_manifest.toml | grep -oP '(?<=^id = \").*(?=\")')
VERSION := $(shell cat ./bombsquad-tools/blender_manifest.toml | grep -oP '(?<=^version = \").*(?=\")')

.PHONY: dev tag publish

all: $(ADDON_NAME)-$(VERSION).zip

$(ADDON_NAME)-$(VERSION).zip: ./bombsquad-tools ./bombsquad-tools/**
	zip -r $@ $<

dev:
	find ./bombsquad-tools/ | entr -cs 'date --rfc-email; make'

clean:
	rm -rf *.zip

tag:
	if [ $$(git branch --show-current) != "main" ]; then \
		echo "Error: Not on the main branch!" >&2; \
		exit 1; \
	fi
	git tag v$(VERSION)
	git push origin v$(VERSION)

# docs: https://extensions.blender.org/api/v1/swagger/
publish:
	curl -sS -X POST \
		https://extensions.blender.org/api/v1/extensions/$(ADDON_NAME)/versions/upload/ \
		-H "Accept: */*" \
		-H "Authorization: Bearer $(BLENDER_EXTENSIONS_API_TOKEN)" \
		-H "Content-Type: multipart/form-data" \
		-F "version_file=@$(ADDON_NAME)-$(VERSION).zip"
