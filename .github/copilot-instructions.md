# Copilot Instructions — KQL-ADX-Expert

## Project overview

This repo is a **GitHub Copilot CLI skill** for writing, optimizing, and running KQL (Kusto Query Language) queries against Azure Data Explorer (ADX), Azure Monitor, Microsoft Sentinel, and Defender. It includes:

- `kql-adx-expert/adx_tool.py` — Python CLI tool for live query execution and cluster schema discovery
- `kql-adx-expert/SKILL.md` — Skill definition (triggers, query-building instructions, examples)
- `kql-adx-expert/references/` — Bundled KQL reference documentation (operators, patterns, Azure resources, Sentinel)
- `kql-adx-expert/requirements.txt` — Python dependencies

## Language & runtime

- **Python 3.9+** is required
- Dependencies: `azure-kusto-data`, `azure-identity[cache]`, `tabulate`
- Authentication uses `InteractiveBrowserCredential` from `azure-identity` with persistent MSAL token caching via `TokenCachePersistenceOptions`

## Code conventions

- Use type hints on all function signatures
- Docstrings follow Google-style (summary line, then Args/Returns/Raises sections)
- CLI argument parsing uses `argparse` with subcommands (`query`, `spider`)
- Shared CLI arguments should be extracted into helper functions to avoid duplication
- Error handling: graceful fallbacks preferred over crashing — wrap external library calls that may fail (e.g., cache initialization) in try/except with sensible defaults
- Print user-facing messages to stdout; warnings and errors to stderr via `print(..., file=sys.stderr)`
- Use `sys.exit(1)` for fatal errors

## Security practices

- Token caching defaults to **encrypted** platform secure storage (Keychain, Credential Manager, keyring)
- `allow_unencrypted_storage` must always default to `False`
- Never log or print tokens, credentials, or cache contents
- The `--allow-unencrypted-cache` flag is opt-in only and must include a security warning in help text

## File organization

```
kql-adx-expert/
├── SKILL.md              # Skill definition — do not remove trigger keywords
├── adx_tool.py           # CLI tool — keep as single-file script
├── requirements.txt      # Pin minimum versions with >=
├── README.md             # Tool documentation (auth, CLI reference, examples)
└── references/           # KQL reference docs (operators, patterns, azure-resources, sentinel)
```

## Working with SKILL.md

- `SKILL.md` frontmatter `description` field contains trigger keywords — preserve them when editing
- The skill instructs the AI to read `cluster_schema.json` before building queries — maintain this workflow
- KQL examples in SKILL.md should follow the performance rules (filter-first, project early, time-filter on joins)

## Working with reference docs

- Files in `references/` are bundled documentation consumed by the skill at runtime
- Keep them factual, concise, and in markdown table/code-block format
- Do not add subjective commentary — these are reference material, not tutorials

## Testing guidance

- Tests should go in a `tests/` directory at the `kql-adx-expert/` level
- Use `pytest` with `unittest.mock` for mocking Azure SDK classes
- Mock `InteractiveBrowserCredential` and `KustoClient` — never make real network calls in tests
- Test the fallback logic in `create_client()` (cache init success and failure paths)

## Git conventions

- Commit messages: imperative mood, concise subject line (≤72 chars)
- Branch names: kebab-case, prefixed with category (e.g., `fix/cache-guard`, `feat/add-tests`)
- PRs should reference related issues with `Fixes #N` or `Relates to #N`
