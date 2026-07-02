from calendar_extractor import extract_calendar_events

transcript = """
Let's schedule a Demo on July 15.

Client meeting Friday at 2 PM.

We should maybe meet someday.
"""

events = extract_calendar_events(transcript)

print(events)