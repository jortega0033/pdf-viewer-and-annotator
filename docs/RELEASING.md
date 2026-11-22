# Releasing

Only the owner releases. An agent never tags, publishes or creates a release.

## What a release is here

A release is a Git tag on `main` that matches `__version__` in `pdf_annotator/__init__.py` (and the `version` reported by `/api/v1/health`). Nothing is published to a package index: the project has no package manifest and no build step. Users run it from a checkout.

## Steps

1. Be on an up-to-date `main` with CI green on the latest commit.
2. Run `python -m unittest discover -s tests` from the repository root and confirm the last line is `OK`.
3. Start the server (`python -m pdf_annotator --data-dir <scratch dir> --port 0`), run the smoke steps in the README, and check `curl -s http://127.0.0.1:<port>/api/v1/health`. Stop the server.
4. Set `__version__` in `pdf_annotator/__init__.py`, and update README and `docs/PRD.md` text that states the version, if any.
5. In `CHANGELOG.md`, rename `Unreleased` to the version and date, and add an empty `Unreleased` section above it.
6. Commit on a branch, open a pull request, wait for green CI and merge it (owner).
7. Tag the merge commit `vX.Y.Z` and push the tag (owner).
8. Optionally create a GitHub release from the tag with the changelog section as notes (owner).

## Rollback

Delete the tag and release, and revert the version commit with a pull request. Stored databases are not touched by a release; a schema change is a migration that opens older databases, as `CLAUDE.md` requires.
