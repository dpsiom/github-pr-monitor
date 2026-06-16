# ADR 0001: Architecture Pattern

## Status

Accepted

## Context

The app needs responsive UI updates while fetching PRs and executing review actions.

## Decision

- Use a layered MVVM/MVC hybrid approach:
  - UI views in src/ui
  - Services for business logic and orchestration
  - API gateway layer for GitHub abstraction
- Use observer pattern through NotificationService.
- Use asyncio for non-blocking API calls with a background thread for Tkinter compatibility.

## Consequences

- Easier unit testing of services and gateway.
- Clear separation of concerns.
- Thread and event-loop boundary requires care for UI updates.
