name: Bug report
description: Create a report to help us improve Match Intel
title: '[BUG] '
labels: ['bug']
assignees: ''

body:
  - type: textarea
    id: description
    attributes:
      label: Bug Description
      description: A clear and concise description of what the bug is.
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior.
      placeholder: |
        1. Run stage '...'
        2. Execute command '...'
        3. See error
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What you expected to happen.
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Relevant Logs & Traceback
      description: Paste relevant log output or error tracebacks here.
      render: shell

  - type: dropdown
    id: component
    attributes:
      label: Component Affected
      options:
        - Stage 1 Fixtures
        - Stage 2 Enrichment (SearXNG / Exa)
        - Stage 3 AI Match Analysis (Mac Mini Service)
        - Stage 4 Top-up
        - Stage 5 Jinja2 Briefing Compilation
        - Stage 6 SMTP Email Dispatch
        - PostgreSQL Database Schema
        - Other
    validations:
      required: true
