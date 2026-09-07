"""Tests for the bridge.py command handlers running against mock_scribus."""

import io
import json
import sys

import pytest

# Inject mock_scribus as the "scribus" module before importing bridge
from tests import mock_scribus

sys.modules["scribus"] = mock_scribus

from scribus_mcp.bridge import (  # noqa: E402
    COMMANDS,
    _alignment_constant,
    _go_to_page,
    _unit_constant,
    cmd_add_page,
    cmd_apply_master_page,
    cmd_close_master_page,
    cmd_control_image,
    cmd_create_char_style,
    cmd_create_document,
    cmd_create_master_page,
    cmd_create_paragraph_style,
    cmd_create_table,
    cmd_define_color,
    cmd_delete_object,
    cmd_delete_page,
    cmd_draw_shape,
    cmd_duplicate_objects,
    cmd_edit_master_page,
    cmd_edit_text,
    cmd_export_pdf,
    cmd_get_document_info,
    cmd_get_font_names,
    cmd_get_object_properties,
    cmd_get_text_info,
    cmd_link_text_frames,
    cmd_list_master_pages,
    cmd_manage_layers,
    cmd_modify_object,
    cmd_modify_table_structure,
    cmd_open_document,
    cmd_organize_objects,
    cmd_place_image,
    cmd_place_svg,
    cmd_place_text,
    cmd_run_script,
    cmd_save_document,
    cmd_set_baseline_grid,
    cmd_set_guides,
    cmd_set_table_content,
    cmd_shutdown,
    cmd_style_table,
    cmd_unlink_text_frames,
    main,
)


@pytest.fixture(autouse=True)
def reset_scribus():
    mock_scribus._reset()
    yield
    mock_scribus._reset()


def _create_doc(**kwargs):
    defaults = {"width": 210, "height": 297, "unit": "mm", "margins": 20, "pages": 1}
    defaults.update(kwargs)
    return cmd_create_document(defaults)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_unit_mm(self):
        assert _unit_constant("mm") == mock_scribus.UNIT_MILLIMETERS

    def test_unit_pt(self):
        assert _unit_constant("pt") == mock_scribus.UNIT_POINTS

    def test_unit_inch_aliases(self):
        assert _unit_constant("in") == mock_scribus.UNIT_INCHES
        assert _unit_constant("inch") == mock_scribus.UNIT_INCHES

    def test_unit_unknown_defaults_mm(self):
        assert _unit_constant("furlongs") == mock_scribus.UNIT_MILLIMETERS

    def test_alignment_constants(self):
        assert _alignment_constant("left") == mock_scribus.ALIGN_LEFT
        assert _alignment_constant("center") == mock_scribus.ALIGN_CENTERED
        assert _alignment_constant("right") == mock_scribus.ALIGN_RIGHT
        assert _alignment_constant("justify") == mock_scribus.ALIGN_BLOCK
        assert _alignment_constant("forced") == mock_scribus.ALIGN_FORCED

    def test_alignment_unknown_defaults_left(self):
        assert _alignment_constant("wiggle") == mock_scribus.ALIGN_LEFT


class TestGoToPage:
    def test_navigates_to_page(self):
        _create_doc(pages=3)
        _go_to_page(2)
        assert mock_scribus._doc.current_page == 2

    def test_none_is_noop(self):
        _create_doc()
        _go_to_page(None)
        assert mock_scribus._doc.current_page == 1


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


class TestCmdCreateDocument:
    def test_defaults(self):
        result = _create_doc()
        assert result["width"] == 210
        assert result["height"] == 297
        assert result["pages"] == 1
        assert mock_scribus._doc is not None

    def test_custom_dims(self):
        result = cmd_create_document(
            {"width": 100, "height": 200, "unit": "pt", "margins": 10, "pages": 2}
        )
        assert result["width"] == 100
        assert result["height"] == 200
        assert result["pages"] == 2

    def test_uniform_margins(self):
        _create_doc(margins=15)
        assert mock_scribus._doc.margins == (15, 15, 15, 15)

    def test_dict_margins(self):
        cmd_create_document({"margins": {"top": 10, "right": 20, "bottom": 30, "left": 40}})
        assert mock_scribus._doc.margins == (40, 20, 10, 30)

    def test_asymmetric_margins(self):
        cmd_create_document(
            {"margin_top": 17, "margin_bottom": 20, "margin_left": 20, "margin_right": 15}
        )
        # margins tuple is (left, right, top, bottom)
        assert mock_scribus._doc.margins == (20, 15, 17, 20)

    def test_facing_pages(self):
        cmd_create_document({"facing_pages": True})
        doc = mock_scribus._doc
        assert doc is not None
        assert doc.page_type == 1
        assert doc.first_page_order == 1

    def test_first_page_left(self):
        cmd_create_document({"facing_pages": True, "first_page_left": True})
        doc = mock_scribus._doc
        assert doc is not None
        assert doc.first_page_order == 0

    def test_facing_pages_sets_page_type(self):
        cmd_create_document({"facing_pages": True})
        assert mock_scribus._doc.page_type == 1
        assert mock_scribus._doc.first_page_order == 1

    def test_first_page_left_sets_order(self):
        cmd_create_document({"facing_pages": True, "first_page_left": True})
        assert mock_scribus._doc.first_page_order == 0

    def test_first_page_left_without_facing(self):
        cmd_create_document({"facing_pages": False, "first_page_left": True})
        assert mock_scribus._doc.first_page_order == 0
        assert mock_scribus._doc.page_type == 0

    def test_bleeds(self):
        cmd_create_document(
            {"bleed_top": 3, "bleed_bottom": 3, "bleed_left": 3, "bleed_right": 3}
        )
        assert mock_scribus._doc.bleeds == (3, 3, 3, 3)

    def test_no_bleeds_by_default(self):
        _create_doc()
        assert not hasattr(mock_scribus._doc, "bleeds")


class TestCmdSetBaselineGrid:
    def test_basic(self):
        _create_doc()
        result = cmd_set_baseline_grid({"grid": 13})
        assert result["grid"] == 13
        assert result["offset"] == 0
        assert mock_scribus._doc.baseline_grid == 13

    def test_with_offset(self):
        _create_doc()
        result = cmd_set_baseline_grid({"grid": 12, "offset": 5})
        assert result["offset"] == 5
        assert mock_scribus._doc.baseline_offset == 5


class TestCmdDefineColor:
    def test_cmyk(self):
        _create_doc()
        params = {"name": "TestCyan", "mode": "cmyk", "c": 100, "m": 0, "y": 0, "k": 0}
        result = cmd_define_color(params)
        assert result["name"] == "TestCyan"
        assert result["mode"] == "cmyk"
        assert "TestCyan" in mock_scribus._doc.colors

    def test_rgb(self):
        _create_doc()
        result = cmd_define_color({"name": "Blue", "mode": "rgb", "r": 0, "g": 0, "b": 255})
        assert result["name"] == "Blue"
        assert result["mode"] == "rgb"

    def test_cmyk_percentage_conversion(self):
        _create_doc()
        # 100% should map to int(100 * 2.55) = 255
        cmd_define_color({"name": "FullCyan", "mode": "cmyk", "c": 100, "m": 0, "y": 0, "k": 0})
        assert "FullCyan" in mock_scribus._doc.colors


class TestCmdPlaceText:
    def test_basic(self):
        _create_doc()
        result = cmd_place_text({"x": 10, "y": 20, "w": 100, "h": 50, "text": "Hello"})
        assert "name" in result
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["text"] == "Hello"

    def test_empty_text(self):
        _create_doc()
        result = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50, "text": ""})
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["text"] == ""

    def test_all_styling(self):
        _create_doc()
        result = cmd_place_text(
            {
                "x": 0,
                "y": 0,
                "w": 100,
                "h": 50,
                "text": "Styled",
                "font": "Helvetica",
                "font_size": 14,
                "color": "Black",
                "alignment": "center",
            }
        )
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["font"] == "Helvetica"
        assert obj["font_size"] == 14
        assert obj["color"] == "Black"
        assert obj["alignment"] == mock_scribus.ALIGN_CENTERED

    def test_page_navigation(self):
        _create_doc(pages=3)
        cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50, "page": 2})
        assert mock_scribus._doc.current_page == 2

    def test_returns_name(self):
        _create_doc()
        result = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        assert result["name"].startswith("text_")

    def test_line_spacing(self):
        _create_doc()
        result = cmd_place_text(
            {"x": 0, "y": 0, "w": 100, "h": 50, "line_spacing": 13, "line_spacing_mode": 0}
        )
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["line_spacing"] == 13
        assert obj["line_spacing_mode"] == 0

    def test_columns(self):
        _create_doc()
        result = cmd_place_text(
            {"x": 0, "y": 0, "w": 100, "h": 50, "columns": 2, "column_gap": 5}
        )
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["columns"] == 2
        assert obj["column_gap"] == 5

    def test_paragraph_style(self):
        _create_doc()
        result = cmd_place_text(
            {"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello", "style": "Body"}
        )
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["style"] == "Body"


def _make_path(tmp_path, name):
    """Create a tiny placeholder file and return its absolute path."""
    p = tmp_path / name
    p.write_bytes(b"0")
    return str(p)


class TestCmdPlaceImage:
    def test_basic(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        result = cmd_place_image({"x": 10, "y": 20, "w": 100, "h": 100, "file_path": p})
        assert "name" in result
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["image"] == p

    def test_scale_default(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "a.png")
        result = cmd_place_image({"x": 0, "y": 0, "w": 50, "h": 50, "file_path": p})
        assert result["name"].startswith("img_")

    def test_scale_disabled(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "a.png")
        result = cmd_place_image(
            {
                "x": 0,
                "y": 0,
                "w": 50,
                "h": 50,
                "file_path": p,
                "scale_to_frame": False,
            }
        )
        assert "name" in result

    def test_page_navigation(self, tmp_path):
        _create_doc(pages=2)
        p = _make_path(tmp_path, "a.png")
        cmd_place_image({"x": 0, "y": 0, "w": 50, "h": 50, "file_path": p, "page": 2})
        assert mock_scribus._doc.current_page == 2


class TestCmdDrawShape:
    def test_rect_default(self):
        _create_doc()
        result = cmd_draw_shape({})
        assert result["shape"] == "rectangle"
        assert result["name"].startswith("rect_")

    def test_ellipse(self):
        _create_doc()
        result = cmd_draw_shape({"shape": "ellipse", "x": 5, "y": 5, "w": 50, "h": 50})
        assert result["shape"] == "ellipse"
        assert result["name"].startswith("ellipse_")

    def test_line(self):
        _create_doc()
        result = cmd_draw_shape({"shape": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 100})
        assert result["shape"] == "line"
        assert result["name"].startswith("line_")

    def test_fill_and_line_color(self):
        _create_doc()
        result = cmd_draw_shape(
            {
                "shape": "rectangle",
                "fill_color": "Red",
                "line_color": "Blue",
            }
        )
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["fill_color"] == "Red"
        assert obj["line_color"] == "Blue"

    def test_line_width(self):
        _create_doc()
        result = cmd_draw_shape({"shape": "rectangle", "line_width": 2.5})
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["line_width"] == 2.5


class TestCmdModifyObject:
    def test_move(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        name = text["name"]
        result = cmd_modify_object({"name": name, "x": 100, "y": 200})
        assert "position" in result["modified"]
        obj = mock_scribus._doc.objects[name]
        assert obj["x"] == 100
        assert obj["y"] == 200

    def test_resize(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        name = text["name"]
        result = cmd_modify_object({"name": name, "w": 200, "h": 300})
        assert "size" in result["modified"]
        obj = mock_scribus._doc.objects[name]
        assert obj["w"] == 200
        assert obj["h"] == 300

    def test_rotation(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        name = text["name"]
        result = cmd_modify_object({"name": name, "rotation": 45})
        assert "rotation" in result["modified"]
        assert mock_scribus._doc.objects[name]["rotation"] == 45

    def test_colors(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        result = cmd_modify_object({"name": name, "fill_color": "Red", "line_color": "Blue"})
        assert "fill_color" in result["modified"]
        assert "line_color" in result["modified"]

    def test_text_props(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50, "text": "old"})
        name = text["name"]
        result = cmd_modify_object(
            {
                "name": name,
                "text": "new",
                "font": "Courier",
                "font_size": 12,
                "text_color": "Red",
                "alignment": "right",
            }
        )
        assert "text" in result["modified"]
        assert "font" in result["modified"]
        assert "font_size" in result["modified"]
        assert "text_color" in result["modified"]
        assert "alignment" in result["modified"]

    def test_only_specified(self):
        _create_doc()
        text = cmd_place_text({"x": 10, "y": 20, "w": 50, "h": 50})
        name = text["name"]
        result = cmd_modify_object({"name": name, "x": 99})
        assert result["modified"] == ["position"]
        assert mock_scribus._doc.objects[name]["x"] == 99
        assert mock_scribus._doc.objects[name]["y"] == 20

    def test_returns_modified_list(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        result = cmd_modify_object({"name": text["name"]})
        assert result["modified"] == []

    def test_line_spacing(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        name = text["name"]
        result = cmd_modify_object(
            {"name": name, "line_spacing": 14, "line_spacing_mode": 2}
        )
        assert "line_spacing" in result["modified"]
        assert "line_spacing_mode" in result["modified"]
        obj = mock_scribus._doc.objects[name]
        assert obj["line_spacing"] == 14
        assert obj["line_spacing_mode"] == 2

    def test_columns(self):
        _create_doc()
        text = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50})
        name = text["name"]
        result = cmd_modify_object({"name": name, "columns": 3, "column_gap": 4})
        assert "columns" in result["modified"]
        assert "column_gap" in result["modified"]
        obj = mock_scribus._doc.objects[name]
        assert obj["columns"] == 3
        assert obj["column_gap"] == 4


class TestCmdOpenDocument:
    def test_empty_doc(self, tmp_path):
        p = _make_path(tmp_path, "test.sla")
        result = cmd_open_document({"file_path": p})
        assert result["file_path"] == p
        assert result["page_count"] == 1
        assert len(result["objects"]) == 0
        assert mock_scribus._doc is not None

    def test_closes_existing_first(self, tmp_path):
        _create_doc()
        assert mock_scribus._doc is not None
        p = _make_path(tmp_path, "other.sla")
        result = cmd_open_document({"file_path": p})
        assert result["file_path"] == p
        assert mock_scribus._doc is not None

    def test_no_prior_doc(self, tmp_path):
        # No doc exists — should open without error
        assert mock_scribus._doc is None
        p = _make_path(tmp_path, "new.sla")
        result = cmd_open_document({"file_path": p})
        assert result["page_count"] == 1

    def test_pre_registered_document(self, tmp_path):
        p = _make_path(tmp_path, "layout.sla")
        mock_scribus._register_mock_document(p, {
            "size": (245, 290),
            "margins": (20, 15, 17, 20),
            "num_pages": 2,
            "objects": [
                {
                    "name": "title_frame", "type": 4, "page": 1,
                    "x": 20, "y": 20, "w": 200, "h": 40, "text": "Hello",
                },
                {"name": "logo", "type": 2, "page": 1, "x": 50, "y": 80, "w": 100, "h": 100},
            ],
        })
        result = cmd_open_document({"file_path": p})
        assert result["page_count"] == 2
        assert len(result["objects"]) == 2
        assert result["objects"][0]["name"] == "title_frame"
        assert result["objects"][1]["name"] == "logo"
        # Verify the objects are accessible
        assert mock_scribus._doc.objects["title_frame"]["text"] == "Hello"


class TestCmdGetObjectProperties:
    def test_text_frame(self):
        _create_doc()
        frame = cmd_place_text({
            "x": 10, "y": 20, "w": 180, "h": 50,
            "text": "Hello World", "font": "Arial Regular",
            "font_size": 14, "color": "Black",
        })
        result = cmd_get_object_properties({"name": frame["name"]})
        assert result["type"] == "text"
        assert result["x"] == 10
        assert result["y"] == 20
        assert result["w"] == 180
        assert result["h"] == 50
        assert result["text"] == "Hello World"
        assert result["font"] == "Arial Regular"
        assert result["font_size"] == 14
        assert result["text_color"] == "Black"

    def test_image_frame(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        frame = cmd_place_image({"x": 5, "y": 10, "w": 100, "h": 80, "file_path": p})
        result = cmd_get_object_properties({"name": frame["name"]})
        assert result["type"] == "image"
        assert result["x"] == 5
        assert result["y"] == 10
        assert "fill_color" in result
        assert "line_color" in result

    def test_shape_with_colors(self):
        _create_doc()
        shape = cmd_draw_shape({
            "shape": "rectangle", "x": 0, "y": 0, "w": 50, "h": 50,
            "fill_color": "Red", "line_color": "Blue", "line_width": 2.0,
        })
        result = cmd_get_object_properties({"name": shape["name"]})
        assert result["type"] == "shape"
        assert result["fill_color"] == "Red"
        assert result["line_color"] == "Blue"
        assert result["line_width"] == 2.0

    def test_line(self):
        _create_doc()
        line = cmd_draw_shape({"shape": "line", "x1": 0, "y1": 0, "x2": 100, "y2": 200})
        result = cmd_get_object_properties({"name": line["name"]})
        assert result["type"] == "line"
        assert "line_color" in result
        assert "line_width" in result
        # Lines should not have fill_color
        assert "fill_color" not in result

    def test_object_not_found(self):
        _create_doc()
        with pytest.raises(ValueError, match="Object not found"):
            cmd_get_object_properties({"name": "nonexistent"})

    def test_rotation(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        cmd_modify_object({"name": frame["name"], "rotation": 45})
        result = cmd_get_object_properties({"name": frame["name"]})
        assert result["rotation"] == 45

    def test_columns(self):
        _create_doc()
        frame = cmd_place_text({
            "x": 0, "y": 0, "w": 100, "h": 50,
            "columns": 3, "column_gap": 5,
        })
        result = cmd_get_object_properties({"name": frame["name"]})
        assert result["columns"] == 3
        assert result["column_gap"] == 5


class TestCmdDeleteObject:
    def test_delete_text_frame(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50, "text": "Delete me"})
        name = frame["name"]
        result = cmd_delete_object({"name": name})
        assert result["deleted"] is True
        assert result["name"] == name
        assert name not in mock_scribus._doc.objects
        assert all(item["name"] != name for item in mock_scribus._doc.items)

    def test_delete_shape(self):
        _create_doc()
        shape = cmd_draw_shape({"shape": "rectangle"})
        name = shape["name"]
        cmd_delete_object({"name": name})
        assert name not in mock_scribus._doc.objects

    def test_nonexistent_raises(self):
        _create_doc()
        with pytest.raises(ValueError, match="Object not found"):
            cmd_delete_object({"name": "ghost"})

    def test_delete_one_of_many(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        f2 = cmd_place_text({"x": 60, "y": 0, "w": 50, "h": 50})
        f3 = cmd_draw_shape({"shape": "rectangle"})
        cmd_delete_object({"name": f2["name"]})
        assert f1["name"] in mock_scribus._doc.objects
        assert f2["name"] not in mock_scribus._doc.objects
        assert f3["name"] in mock_scribus._doc.objects
        assert len(mock_scribus._doc.items) == 2


class TestCmdAddPage:
    def test_add_one(self):
        _create_doc()
        result = cmd_add_page({})
        assert result["added"] == 1
        assert result["total_pages"] == 2

    def test_add_multiple(self):
        _create_doc()
        result = cmd_add_page({"count": 3})
        assert result["added"] == 3
        assert result["total_pages"] == 4

    def test_returns_counts(self):
        _create_doc(pages=2)
        result = cmd_add_page({"count": 2})
        assert result["total_pages"] == 4


class TestCmdCreateParagraphStyle:
    def test_basic(self):
        _create_doc()
        result = cmd_create_paragraph_style(
            {"name": "Body", "font": "DejaVu Serif", "font_size": 9.5}
        )
        assert result["name"] == "Body"

    def test_name_only(self):
        _create_doc()
        result = cmd_create_paragraph_style({"name": "Minimal"})
        assert result["name"] == "Minimal"

    def test_full_options(self):
        _create_doc()
        result = cmd_create_paragraph_style({
            "name": "Heading",
            "font": "Arial Bold",
            "font_size": 24,
            "line_spacing": 28,
            "line_spacing_mode": 0,
            "alignment": "center",
            "first_indent": 0,
            "space_above": 12,
            "space_below": 6,
            "drop_cap": True,
            "drop_cap_lines": 3,
            "char_style": "HeadingChar",
        })
        assert result["name"] == "Heading"


class TestCmdCreateCharStyle:
    def test_basic(self):
        _create_doc()
        result = cmd_create_char_style({"name": "Emphasis", "font": "Arial Italic"})
        assert result["name"] == "Emphasis"

    def test_name_only(self):
        _create_doc()
        result = cmd_create_char_style({"name": "Minimal"})
        assert result["name"] == "Minimal"

    def test_full_options(self):
        _create_doc()
        result = cmd_create_char_style({
            "name": "SmallCaps",
            "font": "Arial Regular",
            "font_size": 10,
            "fill_color": "Black",
            "features": "smallcaps",
            "tracking": 50,
        })
        assert result["name"] == "SmallCaps"


class TestCmdExportPdf:
    def test_basic(self):
        _create_doc()
        result = cmd_export_pdf({"file_path": "/tmp/out.pdf"})
        assert result["file_path"] == "/tmp/out.pdf"
        assert mock_scribus._last_pdf is not None
        assert mock_scribus._last_pdf.file == "/tmp/out.pdf"

    def test_screen_quality(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "quality": "screen"})
        assert mock_scribus._last_pdf.quality == 2
        assert mock_scribus._last_pdf.resolution == 150

    def test_pdf_version(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "pdf_version": "1.4"})
        assert mock_scribus._last_pdf.version == 14

    def test_pdf_x4(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "pdf_version": "x-4"})
        assert mock_scribus._last_pdf.version == 10

    def test_pages_list(self):
        _create_doc(pages=3)
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "pages": [1, 3]})
        assert mock_scribus._last_pdf.pages == [1, 3]

    def test_crop_marks(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "crop_marks": True})
        assert mock_scribus._last_pdf.cropMarks is True

    def test_bleed_marks(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "bleed_marks": True})
        assert mock_scribus._last_pdf.bleedMarks is True

    def test_registration_marks(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "registration_marks": True})
        assert mock_scribus._last_pdf.registrationMarks is True

    def test_color_marks(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "color_marks": True})
        assert mock_scribus._last_pdf.colorMarks is True

    def test_mark_dimensions(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "mark_length": 20, "mark_offset": 5})
        assert mock_scribus._last_pdf.markLength == 20
        assert mock_scribus._last_pdf.markOffset == 5

    def test_output_profile(self):
        _create_doc()
        cmd_export_pdf({
            "file_path": "/tmp/out.pdf",
            "output_profile": "ISOcoated_v2_300_eci",
            "embed_profiles": True,
        })
        assert mock_scribus._last_pdf.outputProfile == "ISOcoated_v2_300_eci"
        assert mock_scribus._last_pdf.embedProfiles is True

    def test_font_embedding_outline(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "font_embedding": "outline"})
        assert mock_scribus._last_pdf.fontEmbedding == 1

    def test_custom_resolution(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "quality": "screen", "resolution": 600})
        assert mock_scribus._last_pdf.resolution == 600

    def test_info_string(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "info": "Test document"})
        assert mock_scribus._last_pdf.info == "Test document"

    def test_use_doc_bleeds(self):
        _create_doc()
        cmd_export_pdf({"file_path": "/tmp/out.pdf", "use_doc_bleeds": True})
        assert mock_scribus._last_pdf.useDocBleeds is True


class TestCmdGetDocumentInfo:
    def test_empty_doc(self):
        _create_doc()
        result = cmd_get_document_info({})
        assert result["page_count"] == 1
        assert len(result["objects"]) == 0
        assert "Black" in result["colors"]

    def test_with_objects(self):
        _create_doc()
        cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50, "text": "Hi"})
        cmd_draw_shape({"shape": "rectangle"})
        result = cmd_get_document_info({})
        assert len(result["objects"]) == 2

    def test_colors(self):
        _create_doc()
        cmd_define_color({"name": "MyColor", "mode": "rgb", "r": 255, "g": 0, "b": 0})
        result = cmd_get_document_info({})
        assert "MyColor" in result["colors"]

    def test_margins_in_info(self):
        _create_doc(margins=15)
        result = cmd_get_document_info({})
        assert "margins" in result
        assert result["margins"]["left"] == 15

    def test_master_pages_in_info(self):
        _create_doc()
        cmd_create_master_page({"name": "LeftPage"})
        result = cmd_get_document_info({})
        assert "LeftPage" in result["master_pages"]

    def test_paragraph_styles_in_info(self):
        _create_doc()
        cmd_create_paragraph_style({"name": "Body"})
        result = cmd_get_document_info({})
        assert "Body" in result["paragraph_styles"]

    def test_char_styles_in_info(self):
        _create_doc()
        cmd_create_char_style({"name": "Bold"})
        result = cmd_get_document_info({})
        assert "Bold" in result["char_styles"]


class TestCmdLinkTextFrames:
    def test_link(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        f2 = cmd_place_text({"x": 0, "y": 60, "w": 50, "h": 50})
        result = cmd_link_text_frames({"from_frame": f1["name"], "to_frame": f2["name"]})
        assert result["from_frame"] == f1["name"]
        assert result["to_frame"] == f2["name"]
        assert (f1["name"], f2["name"]) in mock_scribus._doc.linked_frames


class TestCmdUnlinkTextFrames:
    def test_unlink(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        f2 = cmd_place_text({"x": 0, "y": 60, "w": 50, "h": 50})
        cmd_link_text_frames({"from_frame": f1["name"], "to_frame": f2["name"]})
        result = cmd_unlink_text_frames({"frame": f1["name"]})
        assert result["frame"] == f1["name"]
        assert len(mock_scribus._doc.linked_frames) == 0


class TestCmdSetGuides:
    def test_horizontal(self):
        _create_doc()
        result = cmd_set_guides({"horizontal": [50, 100]})
        assert result["horizontal"] == [50, 100]
        assert mock_scribus._doc.h_guides[1] == [50, 100]

    def test_empty_guides(self):
        _create_doc()
        cmd_set_guides({"horizontal": []})
        assert mock_scribus._doc.h_guides[1] == []

    def test_vertical(self):
        _create_doc()
        result = cmd_set_guides({"vertical": [30, 60]})
        assert result["vertical"] == [30, 60]
        assert mock_scribus._doc.v_guides[1] == [30, 60]

    def test_both_with_page(self):
        _create_doc(pages=2)
        cmd_set_guides({"horizontal": [50], "vertical": [30], "page": 2})
        assert mock_scribus._doc.h_guides[2] == [50]
        assert mock_scribus._doc.v_guides[2] == [30]


class TestCmdMasterPages:
    def test_create(self):
        _create_doc()
        result = cmd_create_master_page({"name": "LeftPage"})
        assert result["name"] == "LeftPage"
        assert "LeftPage" in mock_scribus._doc.master_pages

    def test_edit_and_close(self):
        _create_doc()
        cmd_create_master_page({"name": "RightPage"})
        result = cmd_edit_master_page({"name": "RightPage"})
        assert result["name"] == "RightPage"
        assert mock_scribus._doc.editing_master == "RightPage"
        cmd_close_master_page({})
        assert mock_scribus._doc.editing_master is None

    def test_apply(self):
        _create_doc(pages=2)
        cmd_create_master_page({"name": "LeftPage"})
        result = cmd_apply_master_page({"master_page": "LeftPage", "page": 2})
        assert result["master_page"] == "LeftPage"
        assert result["page"] == 2
        assert mock_scribus._doc.applied_masters[2] == "LeftPage"

    def test_list(self):
        _create_doc()
        cmd_create_master_page({"name": "A"})
        cmd_create_master_page({"name": "B"})
        result = cmd_list_master_pages({})
        assert "A" in result["master_pages"]
        assert "B" in result["master_pages"]


class TestCmdRunScript:
    def test_returns_result(self):
        _create_doc()
        result = cmd_run_script({"code": "result = 42"})
        assert result["result"] == 42

    def test_none_result(self):
        _create_doc()
        result = cmd_run_script({"code": "x = 1"})
        assert result["result"] is None

    def test_non_serializable_becomes_string(self):
        result = cmd_run_script({"code": "result = object()"})
        assert isinstance(result["result"], str)


class TestCmdSaveDocument:
    def test_with_path(self):
        _create_doc()
        result = cmd_save_document({"file_path": "/tmp/doc.sla"})
        assert result["saved"] is True
        assert mock_scribus._saved_path == "/tmp/doc.sla"

    def test_without_path(self):
        _create_doc()
        result = cmd_save_document({})
        assert result["saved"] is True
        assert mock_scribus._saved_path is True


class TestCmdShutdown:
    def test_exits_cleanly(self):
        _create_doc()
        with pytest.raises(SystemExit) as exc_info:
            cmd_shutdown({})
        assert exc_info.value.code == 0

    def test_handles_no_document(self):
        # No doc created — should still exit cleanly
        with pytest.raises(SystemExit) as exc_info:
            cmd_shutdown({})
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


class TestMainLoop:
    def _run_main(self, input_lines):
        """Run main() with given stdin lines, return captured protocol output."""
        from scribus_mcp import bridge

        stdin_data = "\n".join(input_lines) + "\n"
        old_real_stdin = bridge._real_stdin
        bridge._real_stdin = io.StringIO(stdin_data)

        captured = []
        original_send = bridge._send

        def capture_send(obj):
            captured.append(obj)

        bridge._send = capture_send
        try:
            main()
        except (SystemExit, StopIteration):
            pass
        finally:
            bridge._real_stdin = old_real_stdin
            bridge._send = original_send

        return captured

    def test_ready_sentinel(self):
        output = self._run_main([])
        assert output[0] == {"ready": True}

    def test_dispatches_command(self):
        _create_doc()
        cmd = json.dumps({"command": "add_page", "params": {"count": 1}})
        output = self._run_main([cmd])
        # First is ready, second is the response
        assert output[1]["ok"] is True
        assert output[1]["result"]["added"] == 1

    def test_unknown_command_error(self):
        cmd = json.dumps({"command": "fly_to_moon", "params": {}})
        output = self._run_main([cmd])
        assert output[1]["ok"] is False
        assert "Unknown command" in output[1]["error"]

    def test_invalid_json(self):
        output = self._run_main(["this is not json"])
        assert output[1]["ok"] is False
        assert "Invalid JSON" in output[1]["error"]


class TestCommandDispatch:
    def test_all_handlers_registered(self):
        expected = {
            "create_document",
            "open_document",
            "define_color",
            "place_text",
            "place_image",
            "draw_shape",
            "modify_object",
            "get_object_properties",
            "delete_object",
            "add_page",
            "export_pdf",
            "get_document_info",
            "run_script",
            "save_document",
            "shutdown",
            "set_baseline_grid",
            "create_paragraph_style",
            "create_char_style",
            "link_text_frames",
            "unlink_text_frames",
            "set_guides",
            "create_master_page",
            "edit_master_page",
            "close_master_page",
            "apply_master_page",
            "list_master_pages",
            "edit_text",
            "get_text_info",
            "manage_layers",
            "organize_objects",
            "create_table",
            "modify_table_structure",
            "set_table_content",
            "style_table",
            "control_image",
            "delete_page",
            "get_font_names",
            "duplicate_objects",
            "place_svg",
        }
        assert set(COMMANDS.keys()) == expected


# ---------------------------------------------------------------------------
# Phase A: Extended modify_object + get_object_properties
# ---------------------------------------------------------------------------


class TestCmdModifyObjectExtended:
    def test_corner_radius(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        result = cmd_modify_object({"name": name, "corner_radius": 5.0})
        assert "corner_radius" in result["modified"]
        assert mock_scribus._doc.objects[name]["corner_radius"] == 5.0

    def test_text_flow_mode(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        result = cmd_modify_object({"name": name, "text_flow_mode": 2})
        assert "text_flow_mode" in result["modified"]
        assert mock_scribus._doc.objects[name]["text_flow_mode"] == 2

    def test_fill_transparency(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        result = cmd_modify_object({"name": name, "fill_transparency": 0.5})
        assert "fill_transparency" in result["modified"]
        assert mock_scribus._doc.objects[name]["fill_transparency"] == 0.5

    def test_line_style(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        result = cmd_modify_object({"name": name, "line_style": 3})
        assert "line_style" in result["modified"]
        assert mock_scribus._doc.objects[name]["line_style"] == 3


class TestCmdGetObjectPropertiesExtended:
    def test_returns_corner_radius(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        cmd_modify_object({"name": name, "corner_radius": 10.0})
        result = cmd_get_object_properties({"name": name})
        assert result["corner_radius"] == 10.0

    def test_returns_text_flow_mode(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        cmd_modify_object({"name": name, "text_flow_mode": 1})
        result = cmd_get_object_properties({"name": name})
        assert result["text_flow_mode"] == 1

    def test_returns_fill_transparency(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        name = rect["name"]
        cmd_modify_object({"name": name, "fill_transparency": 0.75})
        result = cmd_get_object_properties({"name": name})
        assert result["fill_transparency"] == 0.75

    def test_defaults_zero(self):
        _create_doc()
        rect = cmd_draw_shape({"shape": "rectangle"})
        result = cmd_get_object_properties({"name": rect["name"]})
        assert result["corner_radius"] == 0
        assert result["text_flow_mode"] == 0
        assert result["fill_transparency"] == 0.0


# ---------------------------------------------------------------------------
# Phase B: Text Operations
# ---------------------------------------------------------------------------


class TestCmdEditText:
    def test_insert_append(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        name = frame["name"]
        result = cmd_edit_text({
            "name": name, "action": "insert", "text": " World", "position": -1,
        })
        assert result["action"] == "insert"
        assert mock_scribus._doc.objects[name]["text"] == "Hello World"

    def test_insert_at_position(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hllo"})
        name = frame["name"]
        cmd_edit_text({"name": name, "action": "insert", "text": "e", "position": 1})
        assert mock_scribus._doc.objects[name]["text"] == "Hello"

    def test_apply_char_style(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        name = frame["name"]
        result = cmd_edit_text({
            "name": name, "action": "apply_char_style",
            "start": 0, "count": 5, "style": "Bold",
        })
        assert result["action"] == "apply_char_style"
        assert mock_scribus._doc.objects[name]["char_style"] == "Bold"

    def test_apply_para_style(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        name = frame["name"]
        cmd_edit_text({
            "name": name, "action": "apply_para_style",
            "start": 0, "count": 5, "style": "Body",
        })
        assert mock_scribus._doc.objects[name]["para_style"] == "Body"

    def test_hyphenate(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        name = frame["name"]
        cmd_edit_text({"name": name, "action": "hyphenate"})
        assert mock_scribus._doc.objects[name]["hyphenated"] is True

    def test_dehyphenate(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        name = frame["name"]
        cmd_edit_text({"name": name, "action": "hyphenate"})
        cmd_edit_text({"name": name, "action": "dehyphenate"})
        assert mock_scribus._doc.objects[name]["hyphenated"] is False

    def test_unknown_action_raises(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50})
        with pytest.raises(ValueError, match="Unknown edit_text action"):
            cmd_edit_text({"name": frame["name"], "action": "fly"})


class TestCmdGetTextInfo:
    def test_basic(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        result = cmd_get_text_info({"name": frame["name"]})
        assert result["length"] == 5
        assert result["overflow"] == 0
        assert result["lines"] == 1

    def test_with_refresh(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 100, "h": 50, "text": "Hello"})
        result = cmd_get_text_info({"name": frame["name"], "refresh_layout": True})
        assert result["length"] == 5


# ---------------------------------------------------------------------------
# Phase C: Layers + Grouping/Z-order
# ---------------------------------------------------------------------------


class TestCmdManageLayers:
    def test_create(self):
        _create_doc()
        result = cmd_manage_layers({"action": "create", "layer": "Text"})
        assert result["layer"] == "Text"
        assert "Text" in mock_scribus.getLayers()

    def test_delete(self):
        _create_doc()
        cmd_manage_layers({"action": "create", "layer": "Temp"})
        cmd_manage_layers({"action": "delete", "layer": "Temp"})
        assert "Temp" not in mock_scribus.getLayers()

    def test_list(self):
        _create_doc()
        cmd_manage_layers({"action": "create", "layer": "Images"})
        result = cmd_manage_layers({"action": "list"})
        assert "Images" in result["layers"]

    def test_get_set_active(self):
        _create_doc()
        cmd_manage_layers({"action": "create", "layer": "Top"})
        cmd_manage_layers({"action": "set_active", "layer": "Top"})
        result = cmd_manage_layers({"action": "get_active"})
        assert result["layer"] == "Top"

    def test_send_to_layer(self):
        _create_doc()
        cmd_manage_layers({"action": "create", "layer": "Images"})
        frame = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        cmd_manage_layers({
            "action": "send_to_layer", "layer": "Images", "name": frame["name"],
        })
        assert mock_scribus._doc.objects[frame["name"]]["layer"] == "Images"

    def test_set_properties(self):
        _create_doc()
        cmd_manage_layers({"action": "create", "layer": "Guide"})
        result = cmd_manage_layers({
            "action": "set_properties", "layer": "Guide",
            "visible": False, "locked": True, "printable": False,
        })
        assert "visible" in result["modified"]
        assert "locked" in result["modified"]
        assert "printable" in result["modified"]

    def test_get_properties(self):
        _create_doc()
        cmd_manage_layers({"action": "create", "layer": "Guide"})
        cmd_manage_layers({
            "action": "set_properties", "layer": "Guide",
            "visible": False, "locked": True,
        })
        result = cmd_manage_layers({"action": "get_properties", "layer": "Guide"})
        assert result["visible"] is False
        assert result["locked"] is True
        assert result["printable"] is True  # default

    def test_unknown_action_raises(self):
        _create_doc()
        with pytest.raises(ValueError, match="Unknown manage_layers action"):
            cmd_manage_layers({"action": "fly"})


class TestCmdOrganizeObjects:
    def test_group(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        f2 = cmd_place_text({"x": 60, "y": 0, "w": 50, "h": 50})
        result = cmd_organize_objects({
            "action": "group", "names": [f1["name"], f2["name"]],
        })
        assert "group_name" in result
        assert result["group_name"] in mock_scribus._doc.objects

    def test_ungroup(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        f2 = cmd_place_text({"x": 60, "y": 0, "w": 50, "h": 50})
        result = cmd_organize_objects({
            "action": "group", "names": [f1["name"], f2["name"]],
        })
        group_name = result["group_name"]
        cmd_organize_objects({"action": "ungroup", "name": group_name})
        assert group_name not in mock_scribus._doc.objects

    def test_move_to_front(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        result = cmd_organize_objects({
            "action": "move_to_front", "name": frame["name"],
        })
        assert result["action"] == "move_to_front"

    def test_move_to_back(self):
        _create_doc()
        frame = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        result = cmd_organize_objects({
            "action": "move_to_back", "name": frame["name"],
        })
        assert result["action"] == "move_to_back"

    def test_unknown_action_raises(self):
        _create_doc()
        with pytest.raises(ValueError, match="Unknown organize_objects action"):
            cmd_organize_objects({"action": "fly"})


# ---------------------------------------------------------------------------
# Phase D: Tables
# ---------------------------------------------------------------------------


class TestCmdCreateTable:
    def test_basic(self):
        _create_doc()
        result = cmd_create_table({"x": 10, "y": 20, "w": 180, "h": 100, "rows": 3, "columns": 4})
        assert "name" in result
        assert result["rows"] == 3
        assert result["columns"] == 4
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["rows"] == 3
        assert obj["cols"] == 4

    def test_with_page(self):
        _create_doc(pages=2)
        cmd_create_table({
            "x": 0, "y": 0, "w": 100, "h": 100,
            "rows": 2, "columns": 2, "page": 2,
        })
        assert mock_scribus._doc.current_page == 2


class TestCmdModifyTableStructure:
    def test_insert_rows(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        cmd_modify_table_structure({
            "name": table["name"], "action": "insert_rows", "index": 1, "count": 2,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert obj["rows"] == 4

    def test_insert_columns(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        cmd_modify_table_structure({
            "name": table["name"], "action": "insert_columns", "index": 1, "count": 1,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert obj["cols"] == 3

    def test_remove_rows(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 4, "columns": 2})
        cmd_modify_table_structure({
            "name": table["name"], "action": "remove_rows", "index": 1, "count": 2,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert obj["rows"] == 2

    def test_remove_columns(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 4})
        cmd_modify_table_structure({
            "name": table["name"], "action": "remove_columns", "index": 0, "count": 1,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert obj["cols"] == 3

    def test_resize_row(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        cmd_modify_table_structure({
            "name": table["name"], "action": "resize_row", "index": 0, "size": 30,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert obj["row_heights"][0] == 30

    def test_resize_column(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        cmd_modify_table_structure({
            "name": table["name"], "action": "resize_column", "index": 1, "size": 60,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert obj["col_widths"][1] == 60

    def test_merge_cells(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 3, "columns": 3})
        cmd_modify_table_structure({
            "name": table["name"], "action": "merge_cells",
            "row": 0, "col": 0, "num_rows": 2, "num_cols": 2,
        })
        obj = mock_scribus._doc.objects[table["name"]]
        assert len(obj["merged_cells"]) == 1

    def test_get_size(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 3, "columns": 5})
        result = cmd_modify_table_structure({
            "name": table["name"], "action": "get_size",
        })
        assert result["rows"] == 3
        assert result["columns"] == 5

    def test_unknown_action_raises(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        with pytest.raises(ValueError, match="Unknown modify_table_structure action"):
            cmd_modify_table_structure({"name": table["name"], "action": "fly"})


class TestCmdSetTableContent:
    def test_write_cells(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        result = cmd_set_table_content({
            "name": name,
            "cells": [
                {"row": 0, "col": 0, "text": "A"},
                {"row": 0, "col": 1, "text": "B"},
                {"row": 1, "col": 0, "text": "C"},
            ],
        })
        assert result["cells_written"] == 3
        obj = mock_scribus._doc.objects[name]
        assert obj["cells"][(0, 0)]["text"] == "A"
        assert obj["cells"][(0, 1)]["text"] == "B"
        assert obj["cells"][(1, 0)]["text"] == "C"

    def test_read_cell(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        cmd_set_table_content({
            "name": name, "cells": [{"row": 0, "col": 0, "text": "Hello"}],
        })
        result = cmd_set_table_content({
            "name": name, "get_cell": {"row": 0, "col": 0},
        })
        assert result["text"] == "Hello"


class TestCmdStyleTable:
    def test_table_fill_color(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        cmd_style_table({"name": name, "table_fill_color": "White"})
        assert mock_scribus._doc.objects[name]["table_fill_color"] == "White"

    def test_cell_fill_color(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        cmd_style_table({
            "name": name,
            "cells": [{"row": 0, "col": 0, "fill_color": "Red"}],
        })
        obj = mock_scribus._doc.objects[name]
        assert obj["cells"][(0, 0)]["props"]["fill_color"] == "Red"

    def test_cell_borders(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        cmd_style_table({
            "name": name,
            "cells": [{
                "row": 0, "col": 0,
                "border_top": {"width": 1.0, "color": "Black"},
                "border_bottom": {"width": 0.5, "color": "Gray"},
            }],
        })
        obj = mock_scribus._doc.objects[name]
        props = obj["cells"][(0, 0)]["props"]
        assert props["border_top"]["width"] == 1.0
        assert props["border_bottom"]["color"] == "Gray"

    def test_cell_padding(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        cmd_style_table({
            "name": name,
            "cells": [{
                "row": 0, "col": 0,
                "padding_top": 2.0, "padding_left": 3.0,
            }],
        })
        obj = mock_scribus._doc.objects[name]
        props = obj["cells"][(0, 0)]["props"]
        assert props["padding_top"] == 2.0
        assert props["padding_left"] == 3.0

    def test_table_style(self):
        _create_doc()
        table = cmd_create_table({"x": 0, "y": 0, "w": 100, "h": 100, "rows": 2, "columns": 2})
        name = table["name"]
        cmd_style_table({"name": name, "table_style": "BasicGrid"})
        assert mock_scribus._doc.objects[name]["table_style"] == "BasicGrid"


# ---------------------------------------------------------------------------
# Phase E: Image Control + Misc Standalone Tools
# ---------------------------------------------------------------------------


class TestCmdControlImage:
    def test_get(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        img = cmd_place_image({"x": 0, "y": 0, "w": 100, "h": 100, "file_path": p})
        result = cmd_control_image({"name": img["name"], "action": "get"})
        assert result["offset_x"] == 0.0
        assert result["scale_x"] == 1.0

    def test_set_offset(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        img = cmd_place_image({"x": 0, "y": 0, "w": 100, "h": 100, "file_path": p})
        cmd_control_image({
            "name": img["name"], "action": "set_offset",
            "offset_x": 10, "offset_y": 20,
        })
        obj = mock_scribus._doc.objects[img["name"]]
        assert obj["image_offset_x"] == 10
        assert obj["image_offset_y"] == 20

    def test_set_scale(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        img = cmd_place_image({"x": 0, "y": 0, "w": 100, "h": 100, "file_path": p})
        cmd_control_image({
            "name": img["name"], "action": "set_scale",
            "scale_x": 0.5, "scale_y": 0.5,
        })
        obj = mock_scribus._doc.objects[img["name"]]
        assert obj["image_scale_x"] == 0.5

    def test_fit_frame_to_image(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        img = cmd_place_image({"x": 0, "y": 0, "w": 100, "h": 100, "file_path": p})
        result = cmd_control_image({
            "name": img["name"], "action": "fit_frame_to_image",
        })
        assert result["action"] == "fit_frame_to_image"

    def test_unknown_action_raises(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "img.png")
        img = cmd_place_image({"x": 0, "y": 0, "w": 100, "h": 100, "file_path": p})
        with pytest.raises(ValueError, match="Unknown control_image action"):
            cmd_control_image({"name": img["name"], "action": "fly"})


class TestCmdDeletePage:
    def test_basic(self):
        _create_doc(pages=3)
        result = cmd_delete_page({"page": 2})
        assert result["total_pages"] == 2

    def test_invalid_page_raises(self):
        _create_doc(pages=1)
        with pytest.raises(ValueError, match="Invalid page number"):
            cmd_delete_page({"page": 5})


class TestCmdGetFontNames:
    def test_returns_fonts(self):
        result = cmd_get_font_names({})
        assert "fonts" in result
        assert len(result["fonts"]) > 0
        assert "Arial Regular" in result["fonts"]


class TestCmdDuplicateObjects:
    def test_basic(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50, "text": "Hello"})
        result = cmd_duplicate_objects({"names": [f1["name"]]})
        assert len(result["new_names"]) == 1
        new_name = result["new_names"][0]
        assert new_name in mock_scribus._doc.objects
        assert mock_scribus._doc.objects[new_name]["text"] == "Hello"

    def test_multiple(self):
        _create_doc()
        f1 = cmd_place_text({"x": 0, "y": 0, "w": 50, "h": 50})
        f2 = cmd_draw_shape({"shape": "rectangle"})
        result = cmd_duplicate_objects({"names": [f1["name"], f2["name"]]})
        assert len(result["new_names"]) == 2


class TestCmdPlaceSvg:
    def test_basic(self, tmp_path):
        _create_doc()
        p = _make_path(tmp_path, "icon.svg")
        result = cmd_place_svg({"file_path": p, "x": 10, "y": 20})
        assert "name" in result
        assert result["file_path"] == p
        obj = mock_scribus._doc.objects[result["name"]]
        assert obj["svg_path"] == p
        assert obj["x"] == 10
        assert obj["y"] == 20

    def test_with_page(self, tmp_path):
        _create_doc(pages=2)
        p = _make_path(tmp_path, "icon.svg")
        cmd_place_svg({"file_path": p, "x": 0, "y": 0, "page": 2})
        assert mock_scribus._doc.current_page == 2


class TestFileValidation:
    def test_place_image_missing_file_raises(self, tmp_path):
        _create_doc()
        missing = str(tmp_path / "does_not_exist.png")
        with pytest.raises(ValueError, match="File not found"):
            cmd_place_image({"x": 0, "y": 0, "w": 100, "h": 100, "file_path": missing})

    def test_place_svg_missing_file_raises(self, tmp_path):
        _create_doc()
        missing = str(tmp_path / "does_not_exist.svg")
        with pytest.raises(ValueError, match="File not found"):
            cmd_place_svg({"file_path": missing, "x": 0, "y": 0})

    def test_open_document_missing_file_raises(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.sla")
        with pytest.raises(ValueError, match="File not found"):
            cmd_open_document({"file_path": missing})

    def test_require_file_ok(self, tmp_path):
        from scribus_mcp.bridge import _require_file
        p = _make_path(tmp_path, "ok.png")
        assert _require_file(p) == p
