# pornhub-cli

PornHub scraping, browsing, and download toolkit for the terminal.

Search for videos, inspect metadata, and download in your preferred quality — all from the command line.

> This is an unofficial CLI for PornHub. Use at your own risk. Not affiliated with PornHub.

## Installation

```bash
pip install -e .
```

Requires Python 3.10+.

### System Dependencies

[FFmpeg](https://ffmpeg.org/) must be installed and available on `$PATH` — it is used to merge downloaded `.ts` segments into a single `.mp4` file.

```bash
# Debian / Ubuntu / Kali
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Quick Start

```bash
# 1. Search for videos
pornhub search search-videos "your query"

# 2. Copy a view_key from the results, then download
pornhub video get-video-info <view_key>
# → choose quality → segments download in parallel → merged into .mp4
```

## Commands

### Search — find videos

```bash
pornhub search search-videos <query> [--page N]
```

| Option | Description |
|---|---|
| `--page` / `-p` | Page number to fetch (default: `1`) |

Outputs a list of matching videos with:

- Title, author, duration, view count, date added
- `view_key` — the unique identifier used for download

### Video — inspect & download

```bash
pornhub video get-video-info <view_key>
```

Interactive flow:

1. Fetches video metadata (title, duration, available qualities) from `flashvars` embedded in the page
2. Lists all available quality tiers (e.g. `240p`, `480p`, `720p`, `1080p`)
3. Prompts you to choose one
4. Parses the HLS `.m3u8` playlist for that quality to get segment URLs
5. Downloads all `.ts` segments in parallel (8 workers) with automatic retry on failure
6. Merges segments via FFmpeg into `<view_key>_<quality>.mp4`

Parallel download uses a `ThreadPoolExecutor` — failed segments are retried once before being skipped.

## Configuration

The config file lives at `~/.pornhub-cli/cache/config.json`.

### Custom User-Agent

```json
{
  "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
}
```

When a User-Agent is provided, the browser type is auto-detected (Chrome, Firefox, Edge, Safari, Chrome Android, Safari iOS) and the matching TLS fingerprint is used via `curl-cffi`. If no User-Agent is set, it defaults to Chrome's TLS fingerprint.

## Shell Autocompletion

```bash
eval "$(python autocomp.py)"
```

Detects your shell (bash, zsh, or PowerShell) and prints the appropriate `eval` command. To make it permanent, add the printed command to your shell's rc file (`.zshrc`, `.bashrc`, or PowerShell `$PROFILE`).

## Architecture

```
src/pornhub_cli/
├── __init__.py              # Package init
├── main.py                  # Click CLI — all command groups defined here
├── config.py                # Thread-safe ConfigManager singleton
├── utils.py                 # Utility functions (time conversion, etc.)
└── handlers/
    ├── requests.py           # HTTP session with TLS impersonation
    ├── search.py             # Video search & result parsing
    └── video.py              # flashvars extraction, HLS playlist handling
```

### Key Design Decisions

- **TLS impersonation**: Uses `curl-cffi` to mimic real browser TLS fingerprints (Chrome, Firefox, Edge, Safari). The browser type is auto-detected from the configured User-Agent string — no manual fingerprint selection needed.
- **Lazy imports**: Heavy dependencies (`ffmpeg`, search/video handlers) are imported inside command functions, not at module level. This keeps `pornhub --help` fast — you only pay the import cost for the command you actually run.
- **HLS pipeline**: Video extraction follows the path: page HTML → `flashvars` JSON → `mediaDefinitions` array → `.m3u8` master playlist → quality-specific playlist → segment `.ts` URLs. The last `mediaDefinitions` entry (a loopback to the master playlist) is automatically discarded.
- **Parallel download with retry**: Segments are fetched concurrently via `ThreadPoolExecutor` (8 workers). Any failed segment is retried once; if it fails again, it is skipped with a warning rather than aborting the entire download.
- **Thread-safe config**: `ConfigManager` is a singleton with double-checked locking for initialization and a reentrant lock for file operations. Atomic writes use a `.tmp` → `replace` pattern to avoid corruption.

## Data Directory

All runtime data lives under `~/.pornhub-cli/`:

| Path | Purpose |
|---|---|
| `cache/config.json` | User configuration (User-Agent, etc.) |
| `cache/headers.json` | Cached HTTP headers |
| `cache/profiles/` | Named profile storage |
| `cache/content/` | Cached downloaded content |

## How It Works

**TLS impersonation** happens transparently — `_build_session()` creates a `curl_cffi.Session` with the `impersonate` parameter set to the detected browser type. The session is a module-level global, shared across all handlers. `reload_session()` rebuilds it when configuration changes.

**Search** hits `https://www.pornhub.com/video/search?search=<query>&page=<N>`, parses the result list with BeautifulSoup, filters out ad items, and extracts title, author, duration, views, date added, and `view_key` from each `<li>` element.

**Video download** extracts `flashvars` (a JavaScript variable embedded in the page HTML) via regex, parses it as JSON, then walks the `mediaDefinitions` array to find HLS `.m3u8` URLs for each quality tier. The chosen quality's playlist is parsed with the `m3u8` library to enumerate segment URLs and durations. Segments are downloaded in parallel, written to a temp directory, concatenated via a `filelist.txt`, and merged with `ffmpeg concat` into the final `.mp4`.

## Development

```bash
# Install dev dependencies
pip install -e .

# Run linting & formatting
pre-commit run --all-files
# or directly:
ruff check --fix src/
ruff format src/
```

Uses [ruff](https://github.com/astral-sh/ruff) for linting and formatting (configured in `pyproject.toml`), with pre-commit hooks for automated enforcement.

## License

MIT — see [LICENSE](LICENSE) for details.
