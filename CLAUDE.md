# CLAUDE.md

## Fork rules

This repository is Martin's public fork of
[chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp). Everything
committed here is public.

- Never commit personal data: email addresses, phone numbers, names of real
  contacts, chats or channels, chat/user/message IDs taken from a real account,
  API IDs and hashes, bot tokens, session strings or `.session` files, and
  local absolute paths (for example `/Users/<name>/...`). Tests, fixtures and
  docs use made-up values only.
- Secrets live only in the gitignored `.env`. Do not copy them into code,
  tests, docs, commit messages or logs that get committed.
- Keep fork changes minimal: prefer upstream's implementation whenever it
  covers the need, and port only what upstream lacks.
- Keep the fork as clean linear commits rebased on `upstream/main`; no merge
  commits. One feature or fix per commit, with its tests.
- Before committing, run `uv run pytest` and `uv run black --check .`.
