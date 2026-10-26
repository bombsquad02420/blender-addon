# Ballistica Cloud Tools. Run from this folder (or `make -C ballistica-cloud-tools ...`).
#
# Mirrors the bombsquad-tools targets in the repo root's Makefile. Built with
# Blender's extension builder (not zip) so the manifest's [build] excludes
# (docs, tests, this Makefile) apply and the bundled asset .blend is generated
# first. Tags are `ballistica-cloud-tools-v<version>` so they don't trigger the bombsquad-tools
# release workflow (tags `v*`).

BLENDER ?= blender
NAME := $(shell sed -n 's/^id = "\(.*\)"/\1/p' blender_manifest.toml)
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' blender_manifest.toml)
ZIP := $(NAME)-$(VERSION).zip
DEV_ZIP := $(NAME)-dev.zip
TAG := ballistica-cloud-tools-v$(VERSION)

.PHONY: all dev watch install build assets template test blender-test clean tag publish CHANGELOG.md

# Versioned release archive; refuses uncommitted changes in this folder.
all: $(ZIP)

$(ZIP): . ./**
	@if ! git diff --quiet . || ! git diff --cached --quiet .; then \
		echo "Error: Work directory is not clean. Please commit your changes before creating a versioned archive." >&2; \
		exit 1; \
	fi
	$(MAKE) build

# Development archive from the working tree, uncommitted changes included.
dev: assets
	$(BLENDER) --command extension build --source-dir . --output-filepath $(DEV_ZIP)

# Rebuild the dev archive whenever a file changes (needs entr).
watch:
	find . -not -path '*/__pycache__/*' -not -name '*.blend1' -not -name '*.zip' | entr -cs 'date; $(MAKE) dev'

# Install the dev archive into Blender's user extensions and enable it.
install: dev
	$(BLENDER) --command extension install-file -r user_default --enable $(DEV_ZIP)

build: assets
	$(BLENDER) --command extension build --source-dir . --output-dir .

assets:
	$(BLENDER) -b --factory-startup --python assets/build_assets.py

# Regenerate the committed New Character starter files (assets/template/).
template:
	$(BLENDER) -b --factory-startup --python assets/build_template.py

# Pure-Python tests, no Blender.
test:
	python3 -m unittest discover -s tests

# End-to-end in Blender, on the sample workspace extracted fresh from its
# zip into a temporary folder (deleted afterwards; see tests/_sample.py).
SAMPLE_ZIP ?= $(or $(BCT_SAMPLE_ZIP),tests/fixtures/ClassicCharacterAssets.zip)
blender-test:
	@test -f "$(SAMPLE_ZIP)" || { echo "Sample workspace zip not found: $(SAMPLE_ZIP)" >&2; exit 1; }
	@tmp=$$(mktemp -d) && unzip -q "$(SAMPLE_ZIP)" -d "$$tmp" && \
		$(BLENDER) -b --factory-startup --python tests/blender_smoke.py -- "$$tmp"; \
		status=$$?; rm -rf "$$tmp"; exit $$status

clean:
	rm -f $(NAME)-*.zip

tag:
	@if [ $$(git branch --show-current) != "main" ]; then \
		echo "Error: Not on the main branch!" >&2; \
		exit 1; \
	fi
	git tag $(TAG)
	git push origin $(TAG)

# docs: https://extensions.blender.org/api/v1/swagger/
publish:
	curl -sS -X POST \
		https://extensions.blender.org/api/v1/extensions/$(NAME)/versions/upload/ \
		-H "Accept: */*" \
		-H "Authorization: Bearer $(BLENDER_EXTENSIONS_API_TOKEN)" \
		-H "Content-Type: multipart/form-data" \
		-F "version_file=@$(ZIP)" \
		-F "release_notes=<CHANGELOG.md"

# Changes since the previous ballistica-cloud-tools-v* tag, to this addon only.
CHANGELOG.md:
	@git cliff --latest --tag-pattern 'ballistica-cloud-tools-v.*' --include-path 'ballistica-cloud-tools/**' --output $@
