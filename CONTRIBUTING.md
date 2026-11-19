# Contributing

This branch generates a Profilarr v2 PCD from TRaSH-Guides source data.

## Development

Install the project dependencies and run the checks with:

```sh
uv sync --extra dev
uv run pytest -q
uv run pylint scripts tests
```

## PCD changes

The generator maps TRaSH-Guides JSON into the pinned relational schema. Update the mapping and its tests when source semantics change. Validate the PCD with `uv run scripts/validate.py .`.

Generated SQL operations are append-only. Generate a new numbered operation for source changes; do not edit or remove an operation that has already been emitted.

## Commit messages

Use `type(component): Description`, for example `fix(generator): Handle a new source field`.
