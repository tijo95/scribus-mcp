"""FastMCP server exposing Scribus layout tools to LLMs."""

import atexit
import logging
import os
import threading
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import ScribusClient

logger = logging.getLogger(__name__)

mcp = FastMCP("Scribus")

# Lazy singleton client
_client: ScribusClient | None = None

# Deferred save state
_dirty = False
_dirty_lock = threading.Lock()
_save_timer: threading.Timer | None = None
_SAVE_INTERVAL = int(os.environ.get("SCRIBUS_SAVE_INTERVAL", 30))


def _script_allowed() -> bool:
    """Return True if raw script execution is enabled via environment.

    ``run_script`` executes arbitrary Python inside the Scribus interpreter,
    so it is disabled by default. Set ``SCRIBUS_ALLOW_SCRIPT`` to a truthy
    value (1, true, yes, on; case-insensitive) to enable it.
    """
    return os.environ.get("SCRIBUS_ALLOW_SCRIPT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _get_client() -> ScribusClient:
    """Get or create the ScribusClient singleton."""
    global _client
    if _client is None:
        _client = ScribusClient()
        atexit.register(_shutdown)
    return _client


def _mark_dirty():
    """Mark the document as having unsaved changes and schedule a deferred save."""
    global _dirty, _save_timer
    if _SAVE_INTERVAL == 0:
        # Legacy mode: save immediately
        try:
            _get_client().save_document()
        except Exception as e:
            logger.warning("Auto-save failed: %s", e)
        return
    with _dirty_lock:
        _dirty = True
        if _save_timer is None or not _save_timer.is_alive():
            _save_timer = threading.Timer(_SAVE_INTERVAL, _flush_save)
            _save_timer.daemon = True
            _save_timer.start()


def _flush_save():
    """Periodic callback: save if dirty."""
    global _dirty, _save_timer
    with _dirty_lock:
        if not _dirty:
            return
        _dirty = False
        _save_timer = None
    try:
        _get_client().save_document()
        logger.info("Deferred auto-save completed")
    except Exception as e:
        logger.warning("Deferred auto-save failed: %s", e)


def _ensure_saved():
    """Force an immediate save if there are pending changes."""
    global _dirty, _save_timer
    with _dirty_lock:
        if _save_timer is not None:
            _save_timer.cancel()
            _save_timer = None
        if not _dirty:
            return
        _dirty = False
    try:
        _get_client().save_document()
        logger.info("Forced save completed")
    except Exception as e:
        logger.warning("Forced save failed: %s", e)


def _shutdown():
    """Ensure pending changes are saved, then shut down the client."""
    _ensure_saved()
    if _client is not None:
        _client.shutdown()


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def create_document(
    width: float = 210,
    height: float = 297,
    margins: float = 20,
    margin_top: float | None = None,
    margin_bottom: float | None = None,
    margin_left: float | None = None,
    margin_right: float | None = None,
    facing_pages: bool = False,
    first_page_left: bool = False,
    bleed_top: float = 0,
    bleed_bottom: float = 0,
    bleed_left: float = 0,
    bleed_right: float = 0,
    unit: str = "mm",
    pages: int = 1,
    orientation: int = 0,
) -> str:
    """Create a new Scribus document.

    Args:
        width: Page width in the specified unit (default: 210 for A4)
        height: Page height in the specified unit (default: 297 for A4)
        margins: Uniform page margins on all sides (default: 20)
        margin_top: Top margin (overrides uniform margins)
        margin_bottom: Bottom margin (overrides uniform margins)
        margin_left: Left/inner margin (overrides uniform margins)
        margin_right: Right/outer margin (overrides uniform margins)
        facing_pages: Enable facing pages (spreads) for book layouts
        first_page_left: Start book with a left page (default: right start)
        bleed_top: Top bleed in document units (default: 0)
        bleed_bottom: Bottom bleed in document units (default: 0)
        bleed_left: Left bleed in document units (default: 0)
        bleed_right: Right bleed in document units (default: 0)
        unit: Measurement unit - "mm", "pt", "in", or "p" (default: "mm")
        pages: Number of initial pages (default: 1)
        orientation: 0 for portrait, 1 for landscape (default: 0)

    """
    client = _get_client()
    params: dict[str, Any] = {
        "width": width,
        "height": height,
        "margins": margins,
        "unit": unit,
        "pages": pages,
        "orientation": orientation,
        "facing_pages": facing_pages,
        "first_page_left": first_page_left,
        "bleed_top": bleed_top,
        "bleed_bottom": bleed_bottom,
        "bleed_left": bleed_left,
        "bleed_right": bleed_right,
    }
    if margin_top is not None:
        params["margin_top"] = margin_top
    if margin_bottom is not None:
        params["margin_bottom"] = margin_bottom
    if margin_left is not None:
        params["margin_left"] = margin_left
    if margin_right is not None:
        params["margin_right"] = margin_right

    result = client.send_command("create_document", params)
    client._document_path = None
    _mark_dirty()
    w, h, u, p = result["width"], result["height"], result["unit"], result["pages"]
    return f"Created {w}x{h}{u} document with {p} page(s)."


@mcp.tool()
def define_color(
    name: str,
    mode: str = "cmyk",
    c: float = 0,
    m: float = 0,
    y: float = 0,
    k: float = 0,
    r: int = 0,
    g: int = 0,
    b: int = 0,
) -> str:
    """Define a named color in the document palette.

    Args:
        name: Color name (e.g. "BrandRed")
        mode: "cmyk" or "rgb" (default: "cmyk")
        c: Cyan 0-100% (CMYK mode)
        m: Magenta 0-100% (CMYK mode)
        y: Yellow 0-100% (CMYK mode)
        k: Black 0-100% (CMYK mode)
        r: Red 0-255 (RGB mode)
        g: Green 0-255 (RGB mode)
        b: Blue 0-255 (RGB mode)

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name, "mode": mode}
    if mode == "cmyk":
        params.update({"c": c, "m": m, "y": y, "k": k})
    else:
        params.update({"r": r, "g": g, "b": b})

    client.send_command("define_color", params)
    _mark_dirty()

    if mode == "cmyk":
        return f"Defined CMYK color '{name}' (C={c} M={m} Y={y} K={k})."
    else:
        return f"Defined RGB color '{name}' (R={r} G={g} B={b})."


@mcp.tool()
def place_text(
    x: float,
    y: float,
    w: float,
    h: float,
    text: str = "",
    font: str | None = None,
    font_size: float | None = None,
    color: str | None = None,
    alignment: str | None = None,
    page: int | None = None,
    line_spacing: float | None = None,
    line_spacing_mode: int | None = None,
    columns: int | None = None,
    column_gap: float | None = None,
    style: str | None = None,
) -> str:
    """Create a text frame and optionally fill it with styled text.

    Args:
        x: X position of the text frame
        y: Y position of the text frame
        w: Width of the text frame
        h: Height of the text frame
        text: Text content to place in the frame
        font: Font name (e.g. "Arial Regular")
        font_size: Font size in points
        color: Color name (must be defined in the document palette)
        alignment: Text alignment - "left", "center", "right", "justify"
        page: Page number (1-based) to place the text on
        line_spacing: Line spacing (leading) in points
        line_spacing_mode: 0=fixed, 1=automatic, 2=align to baseline grid
        columns: Number of text columns
        column_gap: Gap between columns in document units
        style: Paragraph style name to apply

    """
    client = _get_client()
    params: dict[str, Any] = {"x": x, "y": y, "w": w, "h": h, "text": text}
    for key, val in [
        ("font", font),
        ("font_size", font_size),
        ("color", color),
        ("alignment", alignment),
        ("page", page),
        ("line_spacing", line_spacing),
        ("line_spacing_mode", line_spacing_mode),
        ("columns", columns),
        ("column_gap", column_gap),
        ("style", style),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("place_text", params)
    _mark_dirty()

    desc = f"Created text frame '{result['name']}' at ({x}, {y})"
    if text:
        preview = text[:50] + "..." if len(text) > 50 else text
        desc += f' with text: "{preview}"'
    return desc + "."


@mcp.tool()
def place_image(
    x: float,
    y: float,
    w: float,
    h: float,
    file_path: str,
    scale_to_frame: bool = True,
    proportional: bool = True,
    page: int | None = None,
) -> str:
    """Create an image frame and load an image file into it.

    Args:
        x: X position of the image frame
        y: Y position of the image frame
        w: Width of the image frame
        h: Height of the image frame
        file_path: Absolute path to the image file
        scale_to_frame: Whether to scale image to fit the frame (default: True)
        proportional: Keep aspect ratio when scaling (default: True)
        page: Page number (1-based) to place the image on

    """
    client = _get_client()
    params: dict[str, Any] = {
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "file_path": file_path,
        "scale_to_frame": scale_to_frame,
        "proportional": proportional,
    }
    if page is not None:
        params["page"] = page

    result = client.send_command("place_image", params)
    _mark_dirty()
    return f"Placed image '{file_path}' in frame '{result['name']}' at ({x}, {y})."


@mcp.tool()
def draw_shape(
    shape: str = "rectangle",
    x: float = 0,
    y: float = 0,
    w: float = 100,
    h: float = 100,
    x1: float | None = None,
    y1: float | None = None,
    x2: float | None = None,
    y2: float | None = None,
    fill_color: str | None = None,
    line_color: str | None = None,
    line_width: float | None = None,
) -> str:
    """Draw a shape: rectangle, ellipse, or line.

    For rectangles and ellipses, use x/y/w/h.
    For lines, use x1/y1/x2/y2.

    Args:
        shape: Shape type - "rectangle", "ellipse", or "line"
        x: X position (rectangles/ellipses)
        y: Y position (rectangles/ellipses)
        w: Width (rectangles/ellipses)
        h: Height (rectangles/ellipses)
        x1: Start X (lines only)
        y1: Start Y (lines only)
        x2: End X (lines only)
        y2: End Y (lines only)
        fill_color: Fill color name (must be defined in palette)
        line_color: Stroke/line color name
        line_width: Line width in points

    """
    client = _get_client()
    params: dict[str, Any] = {"shape": shape}

    if shape == "line":
        params.update(
            {
                "x1": x1 if x1 is not None else 0,
                "y1": y1 if y1 is not None else 0,
                "x2": x2 if x2 is not None else 100,
                "y2": y2 if y2 is not None else 100,
            }
        )
    else:
        params.update({"x": x, "y": y, "w": w, "h": h})

    if fill_color is not None:
        params["fill_color"] = fill_color
    if line_color is not None:
        params["line_color"] = line_color
    if line_width is not None:
        params["line_width"] = line_width

    result = client.send_command("draw_shape", params)
    _mark_dirty()
    return f"Drew {result['shape']} '{result['name']}'."


@mcp.tool()
def modify_object(
    name: str,
    x: float | None = None,
    y: float | None = None,
    w: float | None = None,
    h: float | None = None,
    rotation: float | None = None,
    fill_color: str | None = None,
    line_color: str | None = None,
    line_width: float | None = None,
    text: str | None = None,
    font: str | None = None,
    font_size: float | None = None,
    text_color: str | None = None,
    alignment: str | None = None,
    line_spacing: float | None = None,
    line_spacing_mode: int | None = None,
    columns: int | None = None,
    column_gap: float | None = None,
    corner_radius: float | None = None,
    text_flow_mode: int | None = None,
    fill_transparency: float | None = None,
    line_style: int | None = None,
) -> str:
    """Modify properties of an existing object.

    Only provided parameters will be changed; others are left untouched.

    Args:
        name: Object name (returned by create functions)
        x: New X position
        y: New Y position
        w: New width
        h: New height
        rotation: Rotation angle in degrees
        fill_color: New fill color name
        line_color: New line/stroke color name
        line_width: New line width in points
        text: New text content (text frames only)
        font: New font name (text frames only)
        font_size: New font size in points (text frames only)
        text_color: New text color name (text frames only)
        alignment: New text alignment (text frames only)
        line_spacing: Line spacing (leading) in points (text frames only)
        line_spacing_mode: 0=fixed, 1=automatic, 2=align to baseline grid (text frames only)
        columns: Number of text columns (text frames only)
        column_gap: Gap between columns in document units (text frames only)
        corner_radius: Rounded corner radius in document units
        text_flow_mode: Text flow around object: 0=none, 1=frame, 2=bbox, 3=contour
        fill_transparency: Fill transparency 0.0 (opaque) to 1.0 (transparent)
        line_style: Dash pattern style (1-37)

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name}

    for key, val in [
        ("x", x),
        ("y", y),
        ("w", w),
        ("h", h),
        ("rotation", rotation),
        ("fill_color", fill_color),
        ("line_color", line_color),
        ("line_width", line_width),
        ("text", text),
        ("font", font),
        ("font_size", font_size),
        ("text_color", text_color),
        ("alignment", alignment),
        ("line_spacing", line_spacing),
        ("line_spacing_mode", line_spacing_mode),
        ("columns", columns),
        ("column_gap", column_gap),
        ("corner_radius", corner_radius),
        ("text_flow_mode", text_flow_mode),
        ("fill_transparency", fill_transparency),
        ("line_style", line_style),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("modify_object", params)
    _mark_dirty()
    modified = ", ".join(result.get("modified", []))
    return f"Modified '{name}': updated {modified}."


@mcp.tool()
def add_page(
    count: int = 1,
    where: int = -1,
    master_page: str = "",
) -> str:
    """Add one or more pages to the document.

    Args:
        count: Number of pages to add (default: 1)
        where: Position to insert (-1 = append at end, or page number)
        master_page: Name of the master page to apply

    """
    client = _get_client()
    result = client.send_command(
        "add_page",
        {
            "count": count,
            "where": where,
            "master_page": master_page,
        },
    )
    _mark_dirty()
    return f"Added {result['added']} page(s). Document now has {result['total_pages']} pages."


@mcp.tool()
def export_pdf(
    file_path: str,
    quality: str = "press",
    pdf_version: str | None = None,
    pages: list[int] | None = None,
    crop_marks: bool = False,
    bleed_marks: bool = False,
    registration_marks: bool = False,
    color_marks: bool = False,
    mark_length: float | None = None,
    mark_offset: float | None = None,
    use_doc_bleeds: bool = True,
    output_profile: str | None = None,
    embed_profiles: bool = False,
    info: str | None = None,
    font_embedding: str = "embed",
    resolution: int | None = None,
) -> str:
    """Export the document as a PDF file.

    Args:
        file_path: Output PDF file path
        quality: Quality preset - "screen" (150dpi), "ebook" (150dpi), "press" (300dpi)
        pdf_version: PDF version - "1.3", "1.4", "1.5", "x-1a", "x-3", "x-4"
        pages: List of page numbers to export (default: all pages)
        crop_marks: Add crop/trim marks
        bleed_marks: Add bleed marks
        registration_marks: Add registration marks
        color_marks: Add color calibration marks
        mark_length: Length of printer marks in points
        mark_offset: Offset of marks from page edge in points
        use_doc_bleeds: Use document bleed settings (default: True)
        output_profile: ICC output color profile name (e.g. "ISOcoated_v2_300_eci")
        embed_profiles: Embed ICC color profiles in the PDF
        info: PDF info string (required for PDF/X)
        font_embedding: "embed", "outline", or "none" (default: "embed")
        resolution: Custom DPI resolution (overrides quality preset)

    """
    _ensure_saved()
    client = _get_client()
    params: dict[str, Any] = {"file_path": file_path, "quality": quality}
    if pdf_version is not None:
        params["pdf_version"] = pdf_version
    if pages is not None:
        params["pages"] = pages

    # Prepress options
    params["crop_marks"] = crop_marks
    params["bleed_marks"] = bleed_marks
    params["registration_marks"] = registration_marks
    params["color_marks"] = color_marks
    params["use_doc_bleeds"] = use_doc_bleeds
    params["embed_profiles"] = embed_profiles
    params["font_embedding"] = font_embedding

    for key, val in [
        ("mark_length", mark_length),
        ("mark_offset", mark_offset),
        ("output_profile", output_profile),
        ("info", info),
        ("resolution", resolution),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("export_pdf", params)
    return f"Exported PDF to {result['file_path']}."


@mcp.tool()
def get_document_info() -> str:
    """Get information about the current document.

    Includes pages, objects, colors, margins, master pages, and styles.
    """
    client = _get_client()
    result = client.send_command("get_document_info", {})

    lines = [f"Document has {result['page_count']} page(s)."]

    if result.get("pages"):
        lines.append("Pages:")
        for p in result["pages"]:
            lines.append(f"  Page {p['number']}: {p['width']}x{p['height']}")

    if result.get("margins"):
        m = result["margins"]
        lines.append(
            f"Margins: top={m['top']}, bottom={m['bottom']}, left={m['left']}, right={m['right']}"
        )

    if result.get("objects"):
        lines.append(f"Objects ({len(result['objects'])}):")
        for obj in result["objects"]:
            lines.append(f"  {obj['name']} (type={obj['type']}, page={obj['page']})")

    if result.get("colors"):
        lines.append(f"Colors: {', '.join(result['colors'])}")

    if result.get("master_pages"):
        lines.append(f"Master pages: {', '.join(result['master_pages'])}")

    if result.get("paragraph_styles"):
        lines.append(f"Paragraph styles: {', '.join(result['paragraph_styles'])}")

    if result.get("char_styles"):
        lines.append(f"Character styles: {', '.join(result['char_styles'])}")

    return "\n".join(lines)


@mcp.tool()
def open_document(file_path: str) -> str:
    """Open an existing Scribus .sla document for inspection and editing.

    Args:
        file_path: Absolute path to the .sla file to open

    """
    client = _get_client()
    result = client.send_command("open_document", {"file_path": file_path})
    client._document_path = Path(file_path)

    lines = [f"Opened '{file_path}' ({result['page_count']} page(s))."]
    if result.get("pages"):
        lines.append("Pages:")
        for p in result["pages"]:
            lines.append(f"  Page {p['number']}: {p['width']}x{p['height']}")
    if result.get("objects"):
        lines.append(f"Objects ({len(result['objects'])}):")
        for obj in result["objects"]:
            lines.append(f"  {obj['name']} (type={obj['type']}, page={obj['page']})")
    return "\n".join(lines)


@mcp.tool()
def get_object_properties(name: str) -> str:
    """Get detailed properties of a named object in the document.

    Returns position, size, rotation, and type-specific properties
    (text content, font, colors, etc.).

    Args:
        name: Object name (as returned by create functions or get_document_info)

    """
    client = _get_client()
    result = client.send_command("get_object_properties", {"name": name})

    obj_type = result["type"]
    lines = [
        f"Object '{name}' ({obj_type})",
        f"  Position: ({result['x']}, {result['y']})",
        f"  Size: {result['w']} x {result['h']}",
    ]
    if result.get("rotation"):
        lines.append(f"  Rotation: {result['rotation']}°")

    if obj_type == "text":
        text = result.get("text", "")
        preview = text[:80] + "..." if len(text) > 80 else text
        lines.append(f'  Text: "{preview}"')
        if result.get("font"):
            lines.append(f"  Font: {result['font']} {result.get('font_size', '')}pt")
        if result.get("text_color"):
            lines.append(f"  Text color: {result['text_color']}")
        if result.get("columns", 1) > 1:
            lines.append(f"  Columns: {result['columns']} (gap: {result.get('column_gap', 0)})")

    if obj_type in ("text", "image", "shape") and result.get("fill_color"):
        lines.append(f"  Fill: {result['fill_color']}")
    if result.get("line_color"):
        lines.append(f"  Line color: {result['line_color']}")
    if result.get("line_width"):
        lines.append(f"  Line width: {result['line_width']}")

    if result.get("corner_radius"):
        lines.append(f"  Corner radius: {result['corner_radius']}")
    if result.get("text_flow_mode"):
        lines.append(f"  Text flow mode: {result['text_flow_mode']}")
    if result.get("fill_transparency"):
        lines.append(f"  Fill transparency: {result['fill_transparency']}")

    return "\n".join(lines)


@mcp.tool()
def delete_object(name: str) -> str:
    """Delete a named object from the document.

    Args:
        name: Object name to delete

    """
    client = _get_client()
    client.send_command("delete_object", {"name": name})
    _mark_dirty()
    return f"Deleted object '{name}'."


@mcp.tool()
def set_baseline_grid(
    grid: float,
    offset: float = 0,
) -> str:
    """Set the document baseline grid for aligning text across columns.

    Args:
        grid: Grid spacing in points
        offset: Grid offset from top of page in points (default: 0)

    """
    client = _get_client()
    result = client.send_command("set_baseline_grid", {"grid": grid, "offset": offset})
    _mark_dirty()
    return f"Set baseline grid: {result['grid']}pt spacing, {result['offset']}pt offset."


@mcp.tool()
def create_paragraph_style(
    name: str,
    font: str | None = None,
    font_size: float | None = None,
    line_spacing: float | None = None,
    line_spacing_mode: int | None = None,
    alignment: str | None = None,
    first_indent: float | None = None,
    space_above: float | None = None,
    space_below: float | None = None,
    drop_cap: bool | None = None,
    drop_cap_lines: int | None = None,
    char_style: str | None = None,
) -> str:
    """Create a named paragraph style for consistent text formatting.

    Args:
        name: Style name
        font: Font name (e.g. "DejaVu Serif")
        font_size: Font size in points
        line_spacing: Line spacing (leading) in points
        line_spacing_mode: 0=fixed, 1=automatic, 2=align to baseline grid
        alignment: Text alignment - "left", "center", "right", "justify"
        first_indent: First line indent in document units
        space_above: Space above paragraph in points
        space_below: Space below paragraph in points
        drop_cap: Enable drop caps
        drop_cap_lines: Number of lines for drop cap
        char_style: Associated character style name

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name}
    for key, val in [
        ("font", font),
        ("font_size", font_size),
        ("line_spacing", line_spacing),
        ("line_spacing_mode", line_spacing_mode),
        ("alignment", alignment),
        ("first_indent", first_indent),
        ("space_above", space_above),
        ("space_below", space_below),
        ("drop_cap", drop_cap),
        ("drop_cap_lines", drop_cap_lines),
        ("char_style", char_style),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("create_paragraph_style", params)
    _mark_dirty()
    return f"Created paragraph style '{result['name']}'."


@mcp.tool()
def create_char_style(
    name: str,
    font: str | None = None,
    font_size: float | None = None,
    fill_color: str | None = None,
    features: str | None = None,
    tracking: float | None = None,
) -> str:
    """Create a named character style.

    Args:
        name: Style name
        font: Font name
        font_size: Font size in points
        fill_color: Text color name
        features: Comma-separated features (e.g. "bold,italic,smallcaps")
        tracking: Letter spacing adjustment

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name}
    for key, val in [
        ("font", font),
        ("font_size", font_size),
        ("fill_color", fill_color),
        ("features", features),
        ("tracking", tracking),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("create_char_style", params)
    _mark_dirty()
    return f"Created character style '{result['name']}'."


@mcp.tool()
def link_text_frames(
    from_frame: str,
    to_frame: str,
) -> str:
    """Link two text frames so text flows from one to the next.

    Args:
        from_frame: Source text frame name
        to_frame: Destination text frame name

    """
    client = _get_client()
    client.send_command(
        "link_text_frames", {"from_frame": from_frame, "to_frame": to_frame}
    )
    _mark_dirty()
    return f"Linked '{from_frame}' → '{to_frame}'."


@mcp.tool()
def unlink_text_frames(
    frame: str,
) -> str:
    """Unlink a text frame from its text flow chain.

    Args:
        frame: Text frame name to unlink

    """
    client = _get_client()
    client.send_command("unlink_text_frames", {"frame": frame})
    _mark_dirty()
    return f"Unlinked '{frame}'."


@mcp.tool()
def set_guides(
    horizontal: list[float] | None = None,
    vertical: list[float] | None = None,
    page: int | None = None,
) -> str:
    """Set horizontal and/or vertical guides on a page.

    Args:
        horizontal: List of Y positions for horizontal guides
        vertical: List of X positions for vertical guides
        page: Page number (1-based); defaults to current page

    """
    client = _get_client()
    params: dict[str, Any] = {}
    if horizontal is not None:
        params["horizontal"] = horizontal
    if vertical is not None:
        params["vertical"] = vertical
    if page is not None:
        params["page"] = page

    result = client.send_command("set_guides", params)
    _mark_dirty()
    parts = []
    if result.get("horizontal") is not None:
        parts.append(f"{len(result['horizontal'])} horizontal")
    if result.get("vertical") is not None:
        parts.append(f"{len(result['vertical'])} vertical")
    return f"Set {' and '.join(parts)} guide(s)."


@mcp.tool()
def create_master_page(
    name: str,
) -> str:
    """Create a new master page.

    Args:
        name: Master page name

    """
    client = _get_client()
    result = client.send_command("create_master_page", {"name": name})
    _mark_dirty()
    return f"Created master page '{result['name']}'."


@mcp.tool()
def edit_master_page(
    name: str,
) -> str:
    """Enter editing mode for a master page.

    Args:
        name: Master page name to edit

    """
    client = _get_client()
    result = client.send_command("edit_master_page", {"name": name})
    _mark_dirty()
    return f"Editing master page '{result['name']}'."


@mcp.tool()
def close_master_page() -> str:
    """Exit master page editing mode and return to normal editing."""
    client = _get_client()
    client.send_command("close_master_page", {})
    _mark_dirty()
    return "Closed master page editing."


@mcp.tool()
def apply_master_page(
    master_page: str,
    page: int,
) -> str:
    """Apply a master page to a document page.

    Args:
        master_page: Name of the master page to apply
        page: Target page number (1-based)

    """
    client = _get_client()
    client.send_command(
        "apply_master_page", {"master_page": master_page, "page": page}
    )
    _mark_dirty()
    return f"Applied master page '{master_page}' to page {page}."


@mcp.tool()
def list_master_pages() -> str:
    """List all master pages in the document."""
    client = _get_client()
    result = client.send_command("list_master_pages", {})
    names = result.get("master_pages", [])
    if names:
        return f"Master pages: {', '.join(names)}"
    return "No master pages defined."


@mcp.tool()
def edit_text(
    name: str,
    action: str,
    text: str | None = None,
    position: int | None = None,
    start: int | None = None,
    count: int | None = None,
    style: str | None = None,
) -> str:
    """Edit text content within an existing text frame.

    Args:
        name: Text frame name
        action: "insert", "apply_char_style", "apply_para_style", "hyphenate", "dehyphenate"
        text: Text to insert (for "insert" action)
        position: Character position for insertion (-1 = append)
        start: Selection start position (for style actions)
        count: Selection character count (for style actions)
        style: Style name to apply (for style actions)

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name, "action": action}
    for key, val in [
        ("text", text),
        ("position", position),
        ("start", start),
        ("count", count),
        ("style", style),
    ]:
        if val is not None:
            params[key] = val

    client.send_command("edit_text", params)
    _mark_dirty()
    return f"Edited text in '{name}': {action}."


@mcp.tool()
def get_text_info(
    name: str,
    refresh_layout: bool = False,
) -> str:
    """Get text frame info: overflow count, character count, line count.

    Args:
        name: Text frame name
        refresh_layout: Force layout recalculation before reading (default: False)

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name}
    if refresh_layout:
        params["refresh_layout"] = True

    result = client.send_command("get_text_info", params)
    lines = [
        f"Text frame '{name}':",
        f"  Characters: {result['length']}",
        f"  Lines: {result['lines']}",
        f"  Overflow: {result['overflow']}",
    ]
    return "\n".join(lines)


@mcp.tool()
def manage_layers(
    action: str,
    layer: str | None = None,
    name: str | None = None,
    visible: bool | None = None,
    locked: bool | None = None,
    printable: bool | None = None,
) -> str:
    """Manage document layers.

    Args:
        action: "create", "delete", "list", "get_active", "set_active",
            "send_to_layer", "set_properties", "get_properties"
        layer: Layer name (required for most actions)
        name: Object name (for "send_to_layer")
        visible: Layer visibility (for "set_properties")
        locked: Layer locked state (for "set_properties")
        printable: Layer printable state (for "set_properties")

    """
    client = _get_client()
    params: dict[str, Any] = {"action": action}
    for key, val in [
        ("layer", layer),
        ("name", name),
        ("visible", visible),
        ("locked", locked),
        ("printable", printable),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("manage_layers", params)

    mutating = {"create", "delete", "set_active", "send_to_layer", "set_properties"}
    if action in mutating:
        _mark_dirty()

    if action == "list":
        return f"Layers: {', '.join(result['layers'])}"
    elif action == "get_active":
        return f"Active layer: {result['layer']}"
    elif action == "get_properties":
        return (
            f"Layer '{result['layer']}': "
            f"visible={result['visible']}, locked={result['locked']}, "
            f"printable={result['printable']}"
        )
    else:
        return f"Layer action '{action}' completed."


@mcp.tool()
def organize_objects(
    action: str,
    names: list[str] | None = None,
    name: str | None = None,
) -> str:
    """Group, ungroup, or reorder objects.

    Args:
        action: Operation - "group", "ungroup", "move_to_front", "move_to_back"
        names: List of object names (for "group")
        name: Single object name (for "ungroup", "move_to_front", "move_to_back")

    """
    client = _get_client()
    params: dict[str, Any] = {"action": action}
    if names is not None:
        params["names"] = names
    if name is not None:
        params["name"] = name

    result = client.send_command("organize_objects", params)
    _mark_dirty()

    if action == "group":
        return f"Grouped objects into '{result['group_name']}'."
    elif action == "ungroup":
        return f"Ungrouped '{name}'."
    else:
        return f"Moved '{name}' to {action.replace('move_to_', '')}."


@mcp.tool()
def create_table(
    x: float,
    y: float,
    w: float,
    h: float,
    rows: int,
    columns: int,
    page: int | None = None,
) -> str:
    """Create a table frame.

    Args:
        x: X position
        y: Y position
        w: Width
        h: Height
        rows: Number of rows
        columns: Number of columns
        page: Page number (1-based)

    """
    client = _get_client()
    params: dict[str, Any] = {
        "x": x, "y": y, "w": w, "h": h,
        "rows": rows, "columns": columns,
    }
    if page is not None:
        params["page"] = page

    result = client.send_command("create_table", params)
    _mark_dirty()
    return f"Created {rows}x{columns} table '{result['name']}' at ({x}, {y})."


@mcp.tool()
def modify_table_structure(
    name: str,
    action: str,
    index: int | None = None,
    count: int | None = None,
    size: float | None = None,
    row: int | None = None,
    col: int | None = None,
    num_rows: int | None = None,
    num_cols: int | None = None,
) -> str:
    """Modify table structure: insert/remove rows/columns, resize, merge cells.

    Args:
        name: Table object name
        action: "insert_rows", "insert_columns", "remove_rows",
            "remove_columns", "resize_row", "resize_column", "merge_cells",
            "get_size"
        index: Row or column index (for insert/remove/resize)
        count: Number of rows/columns to insert or remove
        size: New size for resize operations
        row: Starting row (for merge_cells)
        col: Starting column (for merge_cells)
        num_rows: Number of rows to merge
        num_cols: Number of columns to merge

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name, "action": action}
    for key, val in [
        ("index", index),
        ("count", count),
        ("size", size),
        ("row", row),
        ("col", col),
        ("num_rows", num_rows),
        ("num_cols", num_cols),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("modify_table_structure", params)
    if action != "get_size":
        _mark_dirty()

    if action == "get_size":
        return f"Table '{name}': {result['rows']} rows x {result['columns']} columns."
    return f"Table '{name}': {action} completed."


@mcp.tool()
def set_table_content(
    name: str,
    cells: list[dict[str, Any]] | None = None,
    get_cell: dict[str, int] | None = None,
) -> str:
    """Read or write text in table cells.

    Args:
        name: Table object name
        cells: List of {"row": int, "col": int, "text": str} dicts for batch writing
        get_cell: {"row": int, "col": int} dict to read a single cell

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name}
    if cells is not None:
        params["cells"] = cells
    if get_cell is not None:
        params["get_cell"] = get_cell

    result = client.send_command("set_table_content", params)
    if cells:
        _mark_dirty()

    if "text" in result:
        return f"Cell ({result['row']}, {result['col']}): \"{result['text']}\""
    return f"Wrote {result['cells_written']} cell(s) in table '{name}'."


@mcp.tool()
def style_table(
    name: str,
    table_fill_color: str | None = None,
    table_style: str | None = None,
    cells: list[dict[str, Any]] | None = None,
) -> str:
    """Style a table and its individual cells.

    Args:
        name: Table object name
        table_fill_color: Background color for the entire table
        table_style: Table style name to apply
        cells: List of cell style dicts with row, col, fill_color, style,
            border_top/bottom/left/right, padding_top/bottom/left/right

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name}
    if table_fill_color is not None:
        params["table_fill_color"] = table_fill_color
    if table_style is not None:
        params["table_style"] = table_style
    if cells is not None:
        params["cells"] = cells

    result = client.send_command("style_table", params)
    _mark_dirty()
    return f"Styled table '{name}' ({result['cells_styled']} cell(s))."


@mcp.tool()
def control_image(
    name: str,
    action: str = "get",
    offset_x: float | None = None,
    offset_y: float | None = None,
    scale_x: float | None = None,
    scale_y: float | None = None,
) -> str:
    """Control image positioning and scaling within a frame.

    Args:
        name: Image frame name
        action: "get", "set_offset", "set_scale", or "fit_frame_to_image"
        offset_x: Horizontal offset (for set_offset)
        offset_y: Vertical offset (for set_offset)
        scale_x: Horizontal scale factor (for set_scale)
        scale_y: Vertical scale factor (for set_scale)

    """
    client = _get_client()
    params: dict[str, Any] = {"name": name, "action": action}
    for key, val in [
        ("offset_x", offset_x),
        ("offset_y", offset_y),
        ("scale_x", scale_x),
        ("scale_y", scale_y),
    ]:
        if val is not None:
            params[key] = val

    result = client.send_command("control_image", params)
    if action != "get":
        _mark_dirty()

    if action == "get":
        return (
            f"Image '{name}': offset=({result['offset_x']}, {result['offset_y']}), "
            f"scale=({result['scale_x']}, {result['scale_y']})"
        )
    return f"Image '{name}': {action} completed."


@mcp.tool()
def delete_page(page: int) -> str:
    """Delete a page from the document.

    Args:
        page: Page number (1-based) to delete

    """
    client = _get_client()
    result = client.send_command("delete_page", {"page": page})
    _mark_dirty()
    return f"Deleted page {page}. Document now has {result['total_pages']} pages."


@mcp.tool()
def get_font_names() -> str:
    """Get a list of all available font names in Scribus."""
    client = _get_client()
    result = client.send_command("get_font_names", {})
    fonts = result.get("fonts", [])
    return f"Available fonts ({len(fonts)}): {', '.join(fonts)}"


@mcp.tool()
def duplicate_objects(names: list[str]) -> str:
    """Duplicate one or more objects.

    Args:
        names: List of object names to duplicate

    """
    client = _get_client()
    result = client.send_command("duplicate_objects", {"names": names})
    _mark_dirty()
    new_names = result.get("new_names", [])
    return f"Duplicated {len(new_names)} object(s): {', '.join(new_names)}."


@mcp.tool()
def place_svg(
    file_path: str,
    x: float,
    y: float,
    page: int | None = None,
) -> str:
    """Place an SVG file on the page.

    Args:
        file_path: Absolute path to the SVG file
        x: X position
        y: Y position
        page: Page number (1-based)

    """
    client = _get_client()
    params: dict[str, Any] = {"file_path": file_path, "x": x, "y": y}
    if page is not None:
        params["page"] = page

    result = client.send_command("place_svg", params)
    _mark_dirty()
    return f"Placed SVG '{file_path}' as '{result['name']}' at ({x}, {y})."


@mcp.tool()
def run_script(code: str) -> str:
    """Execute raw Scribus Python code (escape hatch for advanced operations).

    The `scribus` module is available in the execution namespace.
    Set a `result` variable to return data.

    This tool is disabled by default for safety. Enable it by setting the
    SCRIBUS_ALLOW_SCRIPT environment variable (e.g. SCRIBUS_ALLOW_SCRIPT=1).

    Args:
        code: Python code to execute inside Scribus

    """
    if not _script_allowed():
        raise RuntimeError(
            "run_script is disabled for safety. Set SCRIBUS_ALLOW_SCRIPT=1 "
            "in the server environment to enable it."
        )
    client = _get_client()
    result = client.send_command("run_script", {"code": code})
    _mark_dirty()

    script_result = result.get("result")
    if script_result is not None:
        return f"Script executed. Result: {script_result}"
    return "Script executed successfully."


def main():
    """Entry point for the MCP server."""
    logging.basicConfig(level=logging.INFO)
    mcp.run()


if __name__ == "__main__":
    main()
