"""Parametrized table-style checks (pytest `parametrize`)."""

import pytest


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "expected_key"),
    [
        ("/healthz", "status"),
        ("/readyz", "status"),
    ],
)
def test_liveness_endpoints_return_status_json(client, path, expected_key):
    r = client.get(path)
    assert r.status_code == 200
    data = r.json()
    assert expected_key in data
