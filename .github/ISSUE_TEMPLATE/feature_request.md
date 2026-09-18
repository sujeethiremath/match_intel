name: Feature request
description: Suggest an idea or enhancement for Match Intel
title: '[FEATURE] '
labels: ['enhancement']
assignees: ''

body:
  - type: textarea
    id: problem
    attributes:
      label: Is your feature request related to a problem?
      description: A clear description of what the problem or limitation is.
    validations:
      required: true

  - type: textarea
    id: solution
    attributes:
      label: Proposed Solution
      description: A clear description of what you want to happen or how the feature should work.
    validations:
      required: true

  - type: textarea
    id: alternatives
    attributes:
      label: Alternative Options
      description: Any alternative solutions or features you have considered.

  - type: textarea
    id: additional
    attributes:
      label: Additional Context
      description: Add any other context or screenshots about the feature request here.
