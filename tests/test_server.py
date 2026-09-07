"""Tests for the MCP server tool functions."""

from unittest.mock import MagicMock, patch

import pytest

import scribus_mcp.server as server_module
from scribus_mcp.server import (
    add_page,
    apply_master_page,
    close_master_page,
    control_image,
    create_char_style,
    create_document,
    create_master_page,
    create_paragraph_style,
    create_table,
    define_color,
    delete_object,
    delete_page,
    draw_shape,
    duplicate_objects,
    edit_master_page,
    edit_text,
    export_pdf,
    get_document_info,
    get_font_names,
    get_object_properties,
    get_text_info,
    link_text_frames,
    list_master_pages,
    manage_layers,
    modify_object,
    modify_table_structure,
    open_document,
    organize_objects,
    place_image,
    place_svg,
    place_text,
    run_script,
    set_baseline_grid,
    set_guides,
    set_table_content,
    style_table,
    unlink_text_frames,
)


@pytest.fixture(autouse=True)
def mock_client():
    """Replace the global client with a mock for all tests.

    Sets SCRIBUS_SAVE_INTERVAL=0 (legacy mode) so existing tests that
    assert save_document.assert_called_once() keep passing.
    """
    mock = MagicMock()
    mock.send_command.return_value = {}
    mock.save_document.return_value = None

    saved_interval = server_module._SAVE_INTERVAL
    server_module._SAVE_INTERVAL = 0

    with (
        patch.object(server_module, "_client", mock),
        patch.object(server_module, "_get_client", return_value=mock),
    ):
        yield mock

    server_module._SAVE_INTERVAL = saved_interval


class TestCreateDocument:
    def test_defaults(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 210,
            "height": 297,
            "unit": "mm",
            "pages": 1,
        }
        result = create_document()
        assert "210x297mm" in result
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["margins"] == 20
        assert call_params["facing_pages"] is False

    def test_custom_params(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 100,
            "height": 200,
            "unit": "pt",
            "pages": 3,
        }
        result = create_document(width=100, height=200, unit="pt", pages=3)
        assert "100x200pt" in result
        assert "3 page(s)" in result

    def test_asymmetric_margins(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 245,
            "height": 290,
            "unit": "mm",
            "pages": 1,
        }
        create_document(
            width=245, height=290, margin_top=17, margin_bottom=20,
            margin_left=20, margin_right=15
        )
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["margin_top"] == 17
        assert call_params["margin_bottom"] == 20
        assert call_params["margin_left"] == 20
        assert call_params["margin_right"] == 15

    def test_facing_pages(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 245,
            "height": 290,
            "unit": "mm",
            "pages": 4,
        }
        create_document(width=245, height=290, facing_pages=True, pages=4)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["facing_pages"] is True

    def test_first_page_left(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 210,
            "height": 297,
            "unit": "mm",
            "pages": 1,
        }
        create_document(facing_pages=True, first_page_left=True)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["first_page_left"] is True

    def test_bleeds(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 245,
            "height": 290,
            "unit": "mm",
            "pages": 1,
        }
        create_document(bleed_top=3, bleed_bottom=3, bleed_left=3, bleed_right=3)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["bleed_top"] == 3
        assert call_params["bleed_right"] == 3


class TestDefineColor:
    def test_cmyk(self, mock_client):
        mock_client.send_command.return_value = {"name": "MyRed", "mode": "cmyk"}
        result = define_color("MyRed", mode="cmyk", c=0, m=100, y=100, k=0)
        assert "CMYK" in result
        assert "MyRed" in result

    def test_rgb(self, mock_client):
        mock_client.send_command.return_value = {"name": "Blue", "mode": "rgb"}
        result = define_color("Blue", mode="rgb", r=0, g=0, b=255)
        assert "RGB" in result


class TestPlaceText:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_1"}
        result = place_text(10, 20, 100, 50, text="Hello")
        assert "text_1" in result
        assert "Hello" in result

    def test_with_styling(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_2"}
        place_text(
            10,
            20,
            100,
            50,
            text="Styled",
            font="Arial Regular",
            font_size=14,
            color="Black",
            alignment="center",
        )
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["font"] == "Arial Regular"
        assert call_params["font_size"] == 14
        assert call_params["alignment"] == "center"

    def test_line_spacing_and_columns(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_3"}
        place_text(
            0, 0, 100, 50,
            line_spacing=13, line_spacing_mode=0,
            columns=2, column_gap=5,
        )
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["line_spacing"] == 13
        assert call_params["line_spacing_mode"] == 0
        assert call_params["columns"] == 2
        assert call_params["column_gap"] == 5

    def test_paragraph_style(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_4"}
        place_text(0, 0, 100, 50, style="Body")
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["style"] == "Body"


class TestPlaceImage:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"name": "img_1"}
        result = place_image(10, 20, 100, 100, "/path/to/image.png")
        assert "img_1" in result
        assert "/path/to/image.png" in result


class TestDrawShape:
    def test_rectangle(self, mock_client):
        mock_client.send_command.return_value = {"name": "rect_1", "shape": "rectangle"}
        result = draw_shape("rectangle", x=10, y=20, w=100, h=50)
        assert "rectangle" in result

    def test_line(self, mock_client):
        mock_client.send_command.return_value = {"name": "line_1", "shape": "line"}
        result = draw_shape("line", x1=0, y1=0, x2=100, y2=100)
        assert "line" in result


class TestModifyObject:
    def test_position(self, mock_client):
        mock_client.send_command.return_value = {"name": "obj_1", "modified": ["position"]}
        result = modify_object("obj_1", x=50, y=60)
        assert "position" in result

    def test_only_sends_non_none(self, mock_client):
        mock_client.send_command.return_value = {"name": "obj_1", "modified": ["fill_color"]}
        modify_object("obj_1", fill_color="Red")
        call_params = mock_client.send_command.call_args[0][1]
        assert "x" not in call_params
        assert "fill_color" in call_params

    def test_line_spacing_and_columns(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "obj_1",
            "modified": ["line_spacing", "columns"],
        }
        modify_object("obj_1", line_spacing=14, columns=3)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["line_spacing"] == 14
        assert call_params["columns"] == 3


class TestAddPage:
    def test_default(self, mock_client):
        mock_client.send_command.return_value = {"added": 1, "total_pages": 2}
        result = add_page()
        assert "1 page(s)" in result
        assert "2 pages" in result


class TestSetBaselineGrid:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"grid": 13, "offset": 0}
        result = set_baseline_grid(13)
        assert "13" in result
        mock_client.send_command.assert_called_once_with(
            "set_baseline_grid", {"grid": 13, "offset": 0}
        )


class TestCreateParagraphStyle:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"name": "Body"}
        result = create_paragraph_style("Body", font="DejaVu Serif", font_size=9.5)
        assert "Body" in result
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["font"] == "DejaVu Serif"
        assert call_params["font_size"] == 9.5

    def test_only_sends_non_none(self, mock_client):
        mock_client.send_command.return_value = {"name": "Body"}
        create_paragraph_style("Body", alignment="justify")
        call_params = mock_client.send_command.call_args[0][1]
        assert "font" not in call_params
        assert call_params["alignment"] == "justify"


class TestCreateCharStyle:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"name": "Emphasis"}
        result = create_char_style("Emphasis", font="Arial Italic")
        assert "Emphasis" in result


class TestLinkTextFrames:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"from_frame": "t1", "to_frame": "t2"}
        result = link_text_frames("t1", "t2")
        assert "t1" in result
        assert "t2" in result


class TestUnlinkTextFrames:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"frame": "t1"}
        result = unlink_text_frames("t1")
        assert "t1" in result


class TestSetGuides:
    def test_horizontal(self, mock_client):
        mock_client.send_command.return_value = {"horizontal": [50, 100], "vertical": None}
        result = set_guides(horizontal=[50, 100])
        assert "2 horizontal" in result


class TestMasterPages:
    def test_create(self, mock_client):
        mock_client.send_command.return_value = {"name": "LeftPage"}
        result = create_master_page("LeftPage")
        assert "LeftPage" in result

    def test_edit(self, mock_client):
        mock_client.send_command.return_value = {"name": "LeftPage"}
        result = edit_master_page("LeftPage")
        assert "LeftPage" in result

    def test_close(self, mock_client):
        mock_client.send_command.return_value = {}
        result = close_master_page()
        assert "Closed" in result

    def test_apply(self, mock_client):
        mock_client.send_command.return_value = {"master_page": "LeftPage", "page": 2}
        result = apply_master_page("LeftPage", 2)
        assert "LeftPage" in result
        assert "2" in result

    def test_list(self, mock_client):
        mock_client.send_command.return_value = {"master_pages": ["A", "B"]}
        result = list_master_pages()
        assert "A" in result
        assert "B" in result

    def test_list_empty(self, mock_client):
        mock_client.send_command.return_value = {"master_pages": []}
        result = list_master_pages()
        assert "No master pages" in result


class TestExportPdf:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"file_path": "/tmp/out.pdf"}
        result = export_pdf("/tmp/out.pdf")
        assert "/tmp/out.pdf" in result


class TestGetDocumentInfo:
    def test_output_format(self, mock_client):
        mock_client.send_command.return_value = {
            "page_count": 2,
            "pages": [
                {"number": 1, "width": 210, "height": 297},
                {"number": 2, "width": 210, "height": 297},
            ],
            "objects": [
                {"name": "text_1", "type": 4, "page": 1},
            ],
            "colors": ["Black", "White", "MyRed"],
            "margins": {"left": 20, "right": 20, "top": 20, "bottom": 20},
            "master_pages": [],
            "paragraph_styles": [],
            "char_styles": [],
        }
        result = get_document_info()
        assert "2 page(s)" in result
        assert "text_1" in result
        assert "MyRed" in result

    def test_margins_display(self, mock_client):
        mock_client.send_command.return_value = {
            "page_count": 1,
            "pages": [],
            "objects": [],
            "colors": [],
            "margins": {"left": 20, "right": 15, "top": 17, "bottom": 20},
            "master_pages": ["LeftPage"],
            "paragraph_styles": ["Body"],
            "char_styles": ["Bold"],
        }
        result = get_document_info()
        assert "top=17" in result
        assert "LeftPage" in result
        assert "Body" in result
        assert "Bold" in result


class TestRunScript:
    def test_with_result(self, mock_client, monkeypatch):
        monkeypatch.setenv("SCRIBUS_ALLOW_SCRIPT", "1")
        mock_client.send_command.return_value = {"result": 42}
        result = run_script("result = 21 * 2")
        assert "42" in result

    def test_without_result(self, mock_client, monkeypatch):
        monkeypatch.setenv("SCRIBUS_ALLOW_SCRIPT", "1")
        mock_client.send_command.return_value = {"result": None}
        result = run_script("scribus.gotoPage(1)")
        assert "successfully" in result

    def test_disabled_by_default(self, mock_client, monkeypatch):
        monkeypatch.delenv("SCRIBUS_ALLOW_SCRIPT", raising=False)
        with pytest.raises(RuntimeError, match="SCRIBUS_ALLOW_SCRIPT"):
            run_script("result = 1")
        mock_client.send_command.assert_not_called()


class TestOpenDocument:
    def test_basic_open(self, mock_client):
        mock_client.send_command.return_value = {
            "file_path": "/tmp/layout.sla",
            "page_count": 2,
            "pages": [
                {"number": 1, "width": 210, "height": 297},
                {"number": 2, "width": 210, "height": 297},
            ],
            "objects": [
                {"name": "text_1", "type": 4, "page": 1},
            ],
        }
        result = open_document("/tmp/layout.sla")
        assert "2 page(s)" in result
        assert "text_1" in result
        mock_client.send_command.assert_called_once_with(
            "open_document", {"file_path": "/tmp/layout.sla"}
        )

    def test_empty_doc(self, mock_client):
        mock_client.send_command.return_value = {
            "file_path": "/tmp/empty.sla",
            "page_count": 1,
            "pages": [{"number": 1, "width": 210, "height": 297}],
            "objects": [],
        }
        result = open_document("/tmp/empty.sla")
        assert "1 page(s)" in result
        assert "Objects" not in result

    def test_does_not_auto_save(self, mock_client):
        mock_client.send_command.return_value = {
            "file_path": "/tmp/doc.sla",
            "page_count": 1,
            "pages": [],
            "objects": [],
        }
        open_document("/tmp/doc.sla")
        mock_client.save_document.assert_not_called()


class TestGetObjectProperties:
    def test_text_frame(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "text_1",
            "type": "text",
            "x": 10,
            "y": 20,
            "w": 180,
            "h": 50,
            "rotation": 0,
            "text": "Hello World",
            "font": "Arial Regular",
            "font_size": 14,
            "text_color": "Black",
            "fill_color": "None",
            "line_color": "Black",
            "line_width": 1.0,
            "columns": 1,
            "column_gap": 0,
        }
        result = get_object_properties("text_1")
        assert "text_1" in result
        assert "text" in result
        assert "Hello World" in result
        mock_client.send_command.assert_called_once_with(
            "get_object_properties", {"name": "text_1"}
        )

    def test_does_not_auto_save(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "obj_1",
            "type": "shape",
            "x": 0, "y": 0, "w": 50, "h": 50,
            "rotation": 0,
            "fill_color": "Red",
            "line_color": "Black",
            "line_width": 1.0,
        }
        get_object_properties("obj_1")
        mock_client.save_document.assert_not_called()


class TestDeleteObject:
    def test_basic_delete(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_1", "deleted": True}
        result = delete_object("text_1")
        assert "Deleted" in result
        assert "text_1" in result
        mock_client.send_command.assert_called_once_with(
            "delete_object", {"name": "text_1"}
        )

    def test_auto_saves(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_1", "deleted": True}
        delete_object("text_1")
        mock_client.save_document.assert_called_once()


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------


class TestCreateDocumentEdgeCases:
    def test_landscape_orientation(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 297,
            "height": 210,
            "unit": "mm",
            "pages": 1,
        }
        create_document(width=297, height=210, orientation=1)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["orientation"] == 1


class TestPlaceTextEdgeCases:
    def test_empty_text_no_preview(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_1"}
        result = place_text(0, 0, 100, 50, text="")
        assert "with text:" not in result

    def test_long_text_truncated(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_1"}
        long_text = "A" * 60
        result = place_text(0, 0, 100, 50, text=long_text)
        assert "..." in result


class TestDrawShapeEdgeCases:
    def test_ellipse_shape(self, mock_client):
        mock_client.send_command.return_value = {"name": "ellipse_1", "shape": "ellipse"}
        result = draw_shape("ellipse", x=10, y=20, w=50, h=50)
        assert "ellipse" in result

    def test_line_defaults(self, mock_client):
        mock_client.send_command.return_value = {"name": "line_1", "shape": "line"}
        draw_shape("line")
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["x1"] == 0
        assert call_params["y1"] == 0
        assert call_params["x2"] == 100
        assert call_params["y2"] == 100


class TestPlaceImageEdgeCases:
    def test_image_with_page(self, mock_client):
        mock_client.send_command.return_value = {"name": "img_1"}
        place_image(0, 0, 100, 100, "/img.png", page=3)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["page"] == 3


class TestExportPdfEdgeCases:
    def test_export_with_version_and_pages(self, mock_client):
        mock_client.send_command.return_value = {"file_path": "/tmp/out.pdf"}
        export_pdf("/tmp/out.pdf", pdf_version="1.4", pages=[1, 2])
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["pdf_version"] == "1.4"
        assert call_params["pages"] == [1, 2]

    def test_prepress_options(self, mock_client):
        mock_client.send_command.return_value = {"file_path": "/tmp/out.pdf"}
        export_pdf(
            "/tmp/out.pdf",
            pdf_version="x-4",
            crop_marks=True,
            bleed_marks=True,
            use_doc_bleeds=True,
            output_profile="ISOcoated_v2_300_eci",
            embed_profiles=True,
            info="Test",
            font_embedding="outline",
            resolution=600,
        )
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["pdf_version"] == "x-4"
        assert call_params["crop_marks"] is True
        assert call_params["bleed_marks"] is True
        assert call_params["output_profile"] == "ISOcoated_v2_300_eci"
        assert call_params["embed_profiles"] is True
        assert call_params["font_embedding"] == "outline"
        assert call_params["resolution"] == 600


class TestGetDocumentInfoEdgeCases:
    def test_empty_document_info(self, mock_client):
        mock_client.send_command.return_value = {
            "page_count": 1,
            "pages": [{"number": 1, "width": 210, "height": 297}],
            "objects": [],
            "colors": [],
            "margins": {},
            "master_pages": [],
            "paragraph_styles": [],
            "char_styles": [],
        }
        result = get_document_info()
        assert "1 page(s)" in result
        assert "Objects" not in result
        assert "Colors" not in result


class TestSaveAfterFailure:
    def test_save_after_failure_logged(self, mock_client):
        mock_client.send_command.return_value = {
            "width": 210,
            "height": 297,
            "unit": "mm",
            "pages": 1,
        }
        mock_client.save_document.side_effect = RuntimeError("save failed")
        # Should not propagate the save error
        result = create_document()
        assert "210x297mm" in result


class TestModifyObjectEdgeCases:
    def test_modify_empty_returns_nothing(self, mock_client):
        mock_client.send_command.return_value = {"name": "obj_1", "modified": []}
        result = modify_object("obj_1")
        assert "obj_1" in result


# ---------------------------------------------------------------------------
# Phase A: Extended modify_object + get_object_properties
# ---------------------------------------------------------------------------


class TestModifyObjectExtended:
    def test_corner_radius(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "modified": ["corner_radius"],
        }
        result = modify_object("rect_1", corner_radius=5.0)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["corner_radius"] == 5.0
        assert "corner_radius" in result

    def test_text_flow_mode(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "modified": ["text_flow_mode"],
        }
        modify_object("rect_1", text_flow_mode=2)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["text_flow_mode"] == 2

    def test_fill_transparency(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "modified": ["fill_transparency"],
        }
        modify_object("rect_1", fill_transparency=0.5)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["fill_transparency"] == 0.5

    def test_line_style(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "modified": ["line_style"],
        }
        modify_object("rect_1", line_style=3)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["line_style"] == 3


class TestGetObjectPropertiesExtended:
    def test_displays_corner_radius(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "type": "shape",
            "x": 0, "y": 0, "w": 50, "h": 50,
            "rotation": 0,
            "fill_color": "Red",
            "line_color": "Black",
            "line_width": 1.0,
            "corner_radius": 10.0,
            "text_flow_mode": 0,
            "fill_transparency": 0.0,
        }
        result = get_object_properties("rect_1")
        assert "Corner radius: 10.0" in result

    def test_displays_text_flow_mode(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "type": "shape",
            "x": 0, "y": 0, "w": 50, "h": 50,
            "rotation": 0,
            "fill_color": "Red",
            "line_color": "Black",
            "line_width": 1.0,
            "corner_radius": 0,
            "text_flow_mode": 2,
            "fill_transparency": 0.0,
        }
        result = get_object_properties("rect_1")
        assert "Text flow mode: 2" in result

    def test_displays_fill_transparency(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "rect_1",
            "type": "shape",
            "x": 0, "y": 0, "w": 50, "h": 50,
            "rotation": 0,
            "fill_color": "Red",
            "line_color": "Black",
            "line_width": 1.0,
            "corner_radius": 0,
            "text_flow_mode": 0,
            "fill_transparency": 0.75,
        }
        result = get_object_properties("rect_1")
        assert "Fill transparency: 0.75" in result


# ---------------------------------------------------------------------------
# Phase B: Text Operations
# ---------------------------------------------------------------------------


class TestEditText:
    def test_insert(self, mock_client):
        mock_client.send_command.return_value = {"name": "text_1", "action": "insert"}
        result = edit_text("text_1", "insert", text="Hello", position=-1)
        assert "insert" in result
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["text"] == "Hello"
        assert call_params["position"] == -1

    def test_apply_char_style(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "text_1", "action": "apply_char_style",
        }
        edit_text("text_1", "apply_char_style", start=0, count=5, style="Bold")
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["style"] == "Bold"
        assert call_params["start"] == 0

    def test_auto_saves(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "text_1", "action": "hyphenate",
        }
        edit_text("text_1", "hyphenate")
        mock_client.save_document.assert_called_once()


class TestGetTextInfo:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "text_1", "overflow": 0, "length": 42, "lines": 3,
        }
        result = get_text_info("text_1")
        assert "Characters: 42" in result
        assert "Lines: 3" in result
        assert "Overflow: 0" in result

    def test_refresh_layout(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "text_1", "overflow": 5, "length": 100, "lines": 8,
        }
        get_text_info("text_1", refresh_layout=True)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["refresh_layout"] is True

    def test_does_not_auto_save(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "text_1", "overflow": 0, "length": 5, "lines": 1,
        }
        get_text_info("text_1")
        mock_client.save_document.assert_not_called()


# ---------------------------------------------------------------------------
# Phase C: Layers + Grouping/Z-order
# ---------------------------------------------------------------------------


class TestManageLayers:
    def test_create(self, mock_client):
        mock_client.send_command.return_value = {"action": "create", "layer": "Text"}
        result = manage_layers("create", layer="Text")
        assert "completed" in result

    def test_list(self, mock_client):
        mock_client.send_command.return_value = {
            "action": "list", "layers": ["Background", "Text", "Images"],
        }
        result = manage_layers("list")
        assert "Background" in result
        assert "Text" in result

    def test_get_active(self, mock_client):
        mock_client.send_command.return_value = {"action": "get_active", "layer": "Text"}
        result = manage_layers("get_active")
        assert "Active layer: Text" in result

    def test_get_properties(self, mock_client):
        mock_client.send_command.return_value = {
            "action": "get_properties", "layer": "Guide",
            "visible": False, "locked": True, "printable": True,
        }
        result = manage_layers("get_properties", layer="Guide")
        assert "visible=False" in result
        assert "locked=True" in result

    def test_mutating_saves(self, mock_client):
        mock_client.send_command.return_value = {"action": "create", "layer": "X"}
        manage_layers("create", layer="X")
        mock_client.save_document.assert_called_once()

    def test_read_only_no_save(self, mock_client):
        mock_client.send_command.return_value = {
            "action": "list", "layers": ["Background"],
        }
        manage_layers("list")
        mock_client.save_document.assert_not_called()


class TestOrganizeObjects:
    def test_group(self, mock_client):
        mock_client.send_command.return_value = {
            "action": "group", "group_name": "group_1",
        }
        result = organize_objects("group", names=["t1", "t2"])
        assert "group_1" in result
        mock_client.save_document.assert_called_once()

    def test_ungroup(self, mock_client):
        mock_client.send_command.return_value = {
            "action": "ungroup", "name": "group_1",
        }
        result = organize_objects("ungroup", name="group_1")
        assert "Ungrouped" in result

    def test_move_to_front(self, mock_client):
        mock_client.send_command.return_value = {
            "action": "move_to_front", "name": "text_1",
        }
        result = organize_objects("move_to_front", name="text_1")
        assert "front" in result


# ---------------------------------------------------------------------------
# Phase D: Tables
# ---------------------------------------------------------------------------


class TestCreateTable:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "rows": 3, "columns": 4,
        }
        result = create_table(10, 20, 180, 100, 3, 4)
        assert "3x4" in result
        assert "table_1" in result

    def test_with_page(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "rows": 2, "columns": 2,
        }
        create_table(0, 0, 100, 100, 2, 2, page=2)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["page"] == 2


class TestModifyTableStructure:
    def test_insert_rows(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "action": "insert_rows",
        }
        result = modify_table_structure("table_1", "insert_rows", index=1, count=2)
        assert "insert_rows" in result

    def test_get_size(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "action": "get_size", "rows": 3, "columns": 5,
        }
        result = modify_table_structure("table_1", "get_size")
        assert "3 rows" in result
        assert "5 columns" in result

    def test_get_size_no_save(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "action": "get_size", "rows": 3, "columns": 5,
        }
        modify_table_structure("table_1", "get_size")
        mock_client.save_document.assert_not_called()

    def test_mutating_saves(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "action": "insert_rows",
        }
        modify_table_structure("table_1", "insert_rows", index=0, count=1)
        mock_client.save_document.assert_called_once()


class TestSetTableContent:
    def test_write(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "cells_written": 2,
        }
        result = set_table_content(
            "table_1",
            cells=[{"row": 0, "col": 0, "text": "A"}, {"row": 0, "col": 1, "text": "B"}],
        )
        assert "2 cell(s)" in result
        mock_client.save_document.assert_called_once()

    def test_read(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "row": 0, "col": 0, "text": "Hello",
        }
        result = set_table_content("table_1", get_cell={"row": 0, "col": 0})
        assert "Hello" in result


class TestStyleTable:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "cells_styled": 1,
        }
        result = style_table(
            "table_1",
            cells=[{"row": 0, "col": 0, "fill_color": "Red"}],
        )
        assert "1 cell(s)" in result
        mock_client.save_document.assert_called_once()

    def test_table_fill(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "table_1", "cells_styled": 0,
        }
        style_table("table_1", table_fill_color="White")
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["table_fill_color"] == "White"


# ---------------------------------------------------------------------------
# Phase E: Image Control + Misc Standalone Tools
# ---------------------------------------------------------------------------


class TestControlImage:
    def test_get(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "img_1",
            "offset_x": 5.0, "offset_y": 10.0,
            "scale_x": 0.5, "scale_y": 0.5,
        }
        result = control_image("img_1", action="get")
        assert "offset=(5.0, 10.0)" in result
        assert "scale=(0.5, 0.5)" in result

    def test_set_offset(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "img_1", "action": "set_offset",
        }
        result = control_image("img_1", action="set_offset", offset_x=10, offset_y=20)
        assert "set_offset" in result
        mock_client.save_document.assert_called_once()

    def test_get_no_save(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "img_1",
            "offset_x": 0, "offset_y": 0,
            "scale_x": 1, "scale_y": 1,
        }
        control_image("img_1")
        mock_client.save_document.assert_not_called()


class TestDeletePage:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {"page": 2, "total_pages": 2}
        result = delete_page(2)
        assert "Deleted page 2" in result
        assert "2 pages" in result
        mock_client.save_document.assert_called_once()


class TestGetFontNames:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {
            "fonts": ["Arial Regular", "Times New Roman"],
        }
        result = get_font_names()
        assert "Arial Regular" in result
        assert "2" in result


class TestDuplicateObjects:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {
            "original_names": ["text_1"],
            "new_names": ["dup_1"],
        }
        result = duplicate_objects(["text_1"])
        assert "dup_1" in result
        mock_client.save_document.assert_called_once()


class TestPlaceSvg:
    def test_basic(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "svg_1", "file_path": "/icon.svg",
        }
        result = place_svg("/icon.svg", 10, 20)
        assert "svg_1" in result
        assert "/icon.svg" in result
        mock_client.save_document.assert_called_once()

    def test_with_page(self, mock_client):
        mock_client.send_command.return_value = {
            "name": "svg_1", "file_path": "/icon.svg",
        }
        place_svg("/icon.svg", 0, 0, page=3)
        call_params = mock_client.send_command.call_args[0][1]
        assert call_params["page"] == 3


# ---------------------------------------------------------------------------
# Deferred auto-save tests
# ---------------------------------------------------------------------------


class TestDeferredSave:
    """Tests for the _mark_dirty / _flush_save / _ensure_saved system."""

    def test_mark_dirty_defers_save(self, mock_client):
        """In deferred mode, _mark_dirty should NOT call save_document immediately."""
        saved_interval = server_module._SAVE_INTERVAL
        server_module._SAVE_INTERVAL = 30
        try:
            mock_client.save_document.reset_mock()
            server_module._dirty = False
            server_module._save_timer = None

            server_module._mark_dirty()

            mock_client.save_document.assert_not_called()
            assert server_module._dirty is True
        finally:
            # Clean up timer
            if server_module._save_timer is not None:
                server_module._save_timer.cancel()
                server_module._save_timer = None
            server_module._dirty = False
            server_module._SAVE_INTERVAL = saved_interval

    def test_ensure_saved_forces_save(self, mock_client):
        """_ensure_saved should immediately save when dirty."""
        saved_interval = server_module._SAVE_INTERVAL
        server_module._SAVE_INTERVAL = 30
        try:
            mock_client.save_document.reset_mock()
            server_module._dirty = True
            server_module._save_timer = None

            server_module._ensure_saved()

            mock_client.save_document.assert_called_once()
            assert server_module._dirty is False
        finally:
            server_module._SAVE_INTERVAL = saved_interval

    def test_ensure_saved_noop_when_clean(self, mock_client):
        """_ensure_saved should not save when there are no pending changes."""
        saved_interval = server_module._SAVE_INTERVAL
        server_module._SAVE_INTERVAL = 30
        try:
            mock_client.save_document.reset_mock()
            server_module._dirty = False
            server_module._save_timer = None

            server_module._ensure_saved()

            mock_client.save_document.assert_not_called()
        finally:
            server_module._SAVE_INTERVAL = saved_interval

    def test_legacy_mode_saves_immediately(self, mock_client):
        """With SAVE_INTERVAL=0, _mark_dirty should save immediately."""
        saved_interval = server_module._SAVE_INTERVAL
        server_module._SAVE_INTERVAL = 0
        try:
            mock_client.save_document.reset_mock()

            server_module._mark_dirty()

            mock_client.save_document.assert_called_once()
        finally:
            server_module._SAVE_INTERVAL = saved_interval

    def test_export_pdf_forces_save_first(self, mock_client):
        """export_pdf should call _ensure_saved before exporting."""
        saved_interval = server_module._SAVE_INTERVAL
        server_module._SAVE_INTERVAL = 30
        try:
            server_module._dirty = True
            server_module._save_timer = None
            mock_client.save_document.reset_mock()
            mock_client.send_command.return_value = {"file_path": "/tmp/out.pdf"}

            export_pdf("/tmp/out.pdf")

            mock_client.save_document.assert_called_once()
            assert server_module._dirty is False
        finally:
            server_module._SAVE_INTERVAL = saved_interval

    def test_flush_save_resets_dirty(self, mock_client):
        """_flush_save should save and clear the dirty flag."""
        saved_interval = server_module._SAVE_INTERVAL
        server_module._SAVE_INTERVAL = 30
        try:
            mock_client.save_document.reset_mock()
            server_module._dirty = True
            server_module._save_timer = None

            server_module._flush_save()

            mock_client.save_document.assert_called_once()
            assert server_module._dirty is False
        finally:
            server_module._SAVE_INTERVAL = saved_interval
