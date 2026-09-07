# Scribus MCP

MCP server for [Scribus](https://www.scribus.net/) — lets LLMs create professional RGB/CMYK layouts programmatically.

## Architecture

```
Claude Code/Desktop ←(MCP stdio)→ server.py ←(subprocess NDJSON)→ Scribus -g -py bridge.py
```

Scribus runs headless as a persistent subprocess. The bridge script executes inside Scribus's embedded Python, receives JSON commands over stdin, returns results over stdout. Mutations are auto-saved on a deferred 30-second timer (batching rapid changes into a single write). New documents save to `~/.scribus-mcp/workspace/document.sla`; opened documents save back to their original path.

## Prerequisites

- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **Scribus** installed at one of:
  - macOS: `/Applications/Scribus.app/Contents/MacOS/Scribus`
  - Linux: `/usr/bin/scribus`
  - Windows: `C:\Program Files\Scribus 1.6\Scribus.exe`
  - Or set `SCRIBUS_EXECUTABLE` env var (see [Custom Scribus Path](#custom-scribus-path))

## Setup

```bash
git clone https://github.com/chrisgliddon/scribus-mcp.git
cd scribus-mcp
uv sync
```

## Docker

If you don't want to install Scribus or uv locally, build the Docker image:

```bash
docker build -t scribus-mcp .
```

Then use the Docker-based MCP config examples below — no local Scribus or uv needed.

## Configure in Claude Code

Add to `.mcp.json` in the project root, or `~/.claude.json` for global access across all sessions.

**Native (uv) — macOS / Linux:**

```json
{
  "mcpServers": {
    "scribus": {
      "command": "uv",
      "args": ["--directory", "/path/to/scribus-mcp", "run", "scribus-mcp"]
    }
  }
}
```

**Native (uv) — Windows:**

```json
{
  "mcpServers": {
    "scribus": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\scribus-mcp", "run", "scribus-mcp"]
    }
  }
}
```

**Docker (cross-platform):**

```json
{
  "mcpServers": {
    "scribus": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "scribus-mcp"]
    }
  }
}
```

## Configure in Claude Desktop

Add a `"scribus"` entry to the `mcpServers` object in your config file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

**Native (uv) — macOS / Linux:**

```json
{
  "mcpServers": {
    "scribus": {
      "command": "uv",
      "args": ["--directory", "/path/to/scribus-mcp", "run", "scribus-mcp"]
    }
  }
}
```

**Native (uv) — Windows:**

```json
{
  "mcpServers": {
    "scribus": {
      "command": "uv",
      "args": ["--directory", "C:\\path\\to\\scribus-mcp", "run", "scribus-mcp"]
    }
  }
}
```

**Docker (cross-platform):**

```json
{
  "mcpServers": {
    "scribus": {
      "command": "docker",
      "args": ["run", "--rm", "-i", "scribus-mcp"]
    }
  }
}
```

## Tools

### Document

| Tool | What it does |
|------|-------------|
| `create_document` | New document with asymmetric margins, facing pages, and bleeds. Params: `width`, `height`, `margins`, `margin_top/bottom/left/right`, `facing_pages`, `first_page_left`, `bleed_top/bottom/left/right`, `unit` (mm/pt/in), `pages`, `orientation` |
| `open_document` | Open an existing `.sla` file. Returns page count, page sizes, and object list. Auto-save writes back to the opened file. Params: `file_path` |
| `add_page` | Add pages. Params: `count`, `where` (-1=append), `master_page` |
| `get_document_info` | Query doc state — pages, margins, objects, colors, master pages, paragraph styles, character styles |
| `set_baseline_grid` | Set document baseline grid for cross-column text alignment. Params: `grid` (spacing in pt), `offset` |

### Colors

| Tool | What it does |
|------|-------------|
| `define_color` | Named color. Params: `name`, `mode` (cmyk/rgb), `c/m/y/k` (0-100%) or `r/g/b` (0-255) |

### Text & Typography

| Tool | What it does |
|------|-------------|
| `place_text` | Text frame with content, styling, columns, and paragraph style. Params: `x`, `y`, `w`, `h`, `text`, `font`, `font_size`, `color`, `alignment`, `page`, `line_spacing`, `line_spacing_mode` (0=fixed, 1=auto, 2=baseline grid), `columns`, `column_gap`, `style` |
| `edit_text` | Edit text in an existing frame. Params: `name`, `action` (insert/apply_char_style/apply_para_style/hyphenate/dehyphenate), `text`, `position`, `start`, `count`, `style` |
| `get_text_info` | Get text frame metrics: overflow count, character count, line count. Params: `name`, `refresh_layout` |
| `create_paragraph_style` | Named paragraph style. Params: `name`, `font`, `font_size`, `line_spacing`, `line_spacing_mode`, `alignment`, `first_indent`, `space_above`, `space_below`, `drop_cap`, `drop_cap_lines`, `char_style` |
| `create_char_style` | Named character style. Params: `name`, `font`, `font_size`, `fill_color`, `features` (e.g. "bold,italic,smallcaps"), `tracking` |
| `link_text_frames` | Link two frames for text flow. Params: `from_frame`, `to_frame` |
| `unlink_text_frames` | Unlink a frame from its text chain. Params: `frame` |

### Images & Shapes

| Tool | What it does |
|------|-------------|
| `place_image` | Image frame. Params: `x`, `y`, `w`, `h`, `file_path`, `scale_to_frame`, `proportional`, `page` |
| `place_svg` | Place an SVG file on the page. Params: `file_path`, `x`, `y`, `page` |
| `draw_shape` | Rectangle, ellipse, or line. Params: `shape`, `x/y/w/h` or `x1/y1/x2/y2`, `fill_color`, `line_color`, `line_width` |
| `modify_object` | Change object props. Params: `name`, + any of: position, size, rotation, colors, text props, `line_spacing`, `line_spacing_mode`, `columns`, `column_gap`, `corner_radius`, `text_flow_mode`, `fill_transparency`, `line_style` |
| `get_object_properties` | Inspect an object's properties (position, size, rotation, corner_radius, text_flow_mode, fill_transparency, type-specific: text content, font, colors, columns). Params: `name` |
| `delete_object` | Remove an object from the document. Params: `name` |
| `control_image` | Get or set image offset/scale within a frame. Params: `name`, `action` (get/set_offset/set_scale/fit_frame_to_image), `offset_x`, `offset_y`, `scale_x`, `scale_y` |
| `duplicate_objects` | Duplicate one or more objects. Params: `names` |

### Layers & Grouping

| Tool | What it does |
|------|-------------|
| `manage_layers` | Create, delete, list, activate, and configure layers. Params: `action` (create/delete/list/get_active/set_active/send_to_layer/set_properties/get_properties), `layer`, `name`, `visible`, `locked`, `printable` |
| `organize_objects` | Group, ungroup, or change z-order. Params: `action` (group/ungroup/move_to_front/move_to_back), `names`, `name` |

### Tables

| Tool | What it does |
|------|-------------|
| `create_table` | Create a table frame. Params: `x`, `y`, `w`, `h`, `rows`, `columns`, `page` |
| `modify_table_structure` | Insert/remove rows/columns, resize, merge cells. Params: `name`, `action` (insert_rows/insert_columns/remove_rows/remove_columns/resize_row/resize_column/merge_cells/get_size), `index`, `count`, `size`, `row`, `col`, `num_rows`, `num_cols` |
| `set_table_content` | Read or write text in table cells. Params: `name`, `cells` (list of {row, col, text}), `get_cell` ({row, col}) |
| `style_table` | Style a table and its cells. Params: `name`, `table_fill_color`, `table_style`, `cells` (list with fill_color, style, border_*, padding_*) |

### Layout & Master Pages

| Tool | What it does |
|------|-------------|
| `set_guides` | Set horizontal/vertical guides on a page. Params: `horizontal`, `vertical`, `page` |
| `create_master_page` | Create a new master page. Params: `name` |
| `edit_master_page` | Enter master page editing mode. Params: `name` |
| `close_master_page` | Exit master page editing mode |
| `apply_master_page` | Apply a master page to a document page. Params: `master_page`, `page` |
| `list_master_pages` | List all master page names |
| `delete_page` | Delete a page from the document. Params: `page` |

### PDF Export

| Tool | What it does |
|------|-------------|
| `export_pdf` | Export PDF with prepress options. Params: `file_path`, `quality` (screen/ebook/press), `pdf_version` (1.3/1.4/1.5/x-1a/x-3/x-4), `pages`, `crop_marks`, `bleed_marks`, `registration_marks`, `color_marks`, `mark_length`, `mark_offset`, `use_doc_bleeds`, `output_profile` (ICC profile name), `embed_profiles`, `info`, `font_embedding` (embed/outline/none), `resolution` |

### Advanced

| Tool | What it does |
|------|-------------|
| `run_script` | Execute raw Scribus Python. Params: `code`. Set `result` variable to return data. **Disabled by default**; enable with `SCRIBUS_ALLOW_SCRIPT=1` |
| `get_font_names` | List all available font names in Scribus |

## Example Prompts

> Create an A4 document, define a CMYK color called "BrandBlue" at C=100 M=80 Y=0 K=20, add a heading "Hello World" in 36pt centered at the top, draw a blue rectangle behind it, then export as PDF to ~/Desktop/test.pdf

> Open a US Letter landscape document, place the image at ~/logo.png in the top-left corner scaled to 50x50mm, add body text below it, export to PDF

> Open the file ~/Documents/layout.sla, show me what objects are on page 1, delete the old "header_text" frame, and replace it with a new heading "Updated Title" in 24pt centered at the top

> Create a 245x290mm facing-pages book with 3mm bleeds, asymmetric margins (top=17, bottom=20, left=20, right=15), set a 13pt baseline grid, define a "Body" paragraph style in DejaVu Serif 9.5pt with justified alignment, then export as PDF/X-4 with crop marks and ISOcoated_v2 ICC profile

## Development

```bash
# install dev deps
uv sync

# run tests
uv run pytest tests/ -v

# test with MCP Inspector
npx @modelcontextprotocol/inspector uv run scribus-mcp
```

### CI

Runs `ruff check` and `pytest` on every push/PR to `main` (Python 3.10-3.12).

## Configuration

### Custom Scribus Path

If Scribus isn't in a standard location:

**macOS / Linux (bash/zsh):**

```bash
export SCRIBUS_EXECUTABLE=/path/to/scribus
```

**Windows (Command Prompt):**

```cmd
set SCRIBUS_EXECUTABLE=C:\path\to\Scribus.exe
```

**Windows (PowerShell):**

```powershell
$env:SCRIBUS_EXECUTABLE = "C:\path\to\Scribus.exe"
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRIBUS_COMMAND_TIMEOUT` | `30` | Seconds to wait for a command response before killing Scribus |
| `SCRIBUS_STARTUP_TIMEOUT` | `60` | Seconds to wait for the ready sentinel at startup |
| `SCRIBUS_SAVE_INTERVAL` | `30` | Seconds between deferred auto-saves. Set to `0` to save after every command (legacy behavior) |
| `SCRIBUS_ALLOW_SCRIPT` | `disabled` | Set to `1` to enable the `run_script` tool (arbitrary Python execution in Scribus). Off by default for safety |

## How It Works

1. On first tool call, `client.py` launches Scribus headless (`-g -ns -py bridge.py`)
2. `bridge.py` redirects stdout to avoid protocol contamination, sends `{"ready": true}` sentinel
3. Client sends NDJSON commands over stdin, reads JSON responses from stdout
4. Each command has a timeout (default 30s) — if Scribus stalls, the process is killed and auto-restarted on the next call
5. Mutations are batched into a deferred auto-save (default every 30s); a forced save runs before PDF export and at shutdown
6. New documents save to `~/.scribus-mcp/workspace/document.sla`; opened documents save back to their original path

## License

MIT — see [LICENSE](LICENSE)
