Feature: API health
  Scenario: healthz returns ok
    When the client requests "/healthz"
    Then the response status code is 200
    And the response JSON status is "ok"
