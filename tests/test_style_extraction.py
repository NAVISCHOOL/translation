"""Tests for style extraction from original PDF."""
import pytest
import os
import json
from PIL import Image


def test_sample_block_color_returns_median_rgb():
    """3x3 grid sampling with background filtering."""
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    for x in range(20, 80):
        for y in range(10, 40):
            img.putpixel((x, y), (70, 70, 70))

    from src.translate_pipeline import sample_block_color
    bbox = (10, 5, 90, 45)
    r, g, b = sample_block_color(img, bbox)
    assert 50 <= r <= 90
    assert 50 <= g <= 90
    assert 50 <= b <= 90


def test_sample_block_color_all_background_returns_default():
    """If all sampled pixels are background, return default black."""
    img = Image.new("RGB", (100, 50), (255, 255, 255))
    from src.translate_pipeline import sample_block_color
    bbox = (0, 0, 100, 50)
    r, g, b = sample_block_color(img, bbox)
    assert (r, g, b) == (40, 40, 40)
