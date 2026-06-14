from pixelator.config import CropConfig
from pixelator.gui.preview import fit_rect, preview_to_source_crop, source_to_preview_crop


def test_fit_rect_letterboxes_source_inside_widget():
    rect = fit_rect(source_size=(1920, 1080), widget_size=(800, 600))

    assert rect == (0, 75, 800, 450)


def test_source_to_preview_crop_maps_coordinates():
    crop = CropConfig(x=100, y=50, width=400, height=300)

    result = source_to_preview_crop(crop, source_size=(1000, 500), widget_size=(500, 500))

    assert result == (50, 150, 200, 150)


def test_preview_to_source_crop_clamps_to_source():
    result = preview_to_source_crop(
        preview_rect=(-20, 100, 700, 500),
        source_size=(1000, 500),
        widget_size=(500, 500),
    )

    assert result == CropConfig(x=0, y=0, width=1000, height=500)
