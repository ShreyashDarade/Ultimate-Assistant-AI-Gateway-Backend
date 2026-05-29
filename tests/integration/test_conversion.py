"""Integration tests for conversions."""

import pytest


@pytest.mark.skip(reason="Requires provider API key for full integration test")
async def test_text_to_image_conversion(client, auth_headers):
    """Test text→image conversion through the API."""
    resp = await client.post(
        "/v1/conversions",
        json={
            "input": "a beautiful sunset over mountains",
            "input_modality": "text",
            "output_modality": "image",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "output" in data
    assert data["output_modality"] == "image"
