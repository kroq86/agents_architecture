"""Gherkin layer for one scenario (see `features/health.feature`)."""

import pytest
from pytest_bdd import parsers, scenario, then, when

from app.main import create_app


@pytest.mark.bdd
@scenario("health.feature", "healthz returns ok")
def test_healthz_gherkin():
    """Living-doc hook: scenario steps are implemented below."""


@when(parsers.parse('the client requests "{path}"'), target_fixture="response")
def request_path(path):
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    return client.get(path)


@then(parsers.parse("the response status code is {code:d}"))
def assert_status(response, code):
    assert response.status_code == code


@then(parsers.parse('the response JSON status is "{status}"'))
def assert_json_status(response, status):
    assert response.json()["status"] == status
