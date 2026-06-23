"""Public service for the community module.

This is the ONLY surface other modules may depend on (AGENTS.md).
Never import another module's internal files or query its tables directly —
cross-module side effects go through the event bus in app/platform/events.
"""


class CommunityService:
    # TODO(community): implement per Tara-Project-Documentation.md section 4
    ...
