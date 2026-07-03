from services.calendar_extractor import extract_calendar_events

transcript = """
Today's meeting discussed the following:

Client Demo on July 15 at 3 PM.

Sprint Planning on Friday at 11 AM.

Final presentation on August 1.

Remember to invite everyone.
"""

events = extract_calendar_events(transcript)

print("\nExtracted Events:\n")

for event in events:
    print(event)