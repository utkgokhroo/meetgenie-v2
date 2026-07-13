from services.calendar_extractor import extract_calendar_events

transcript = """
Let's schedule a client demo on July 15 at 3 PM.
It will last for 90 minutes.
Please remind everyone 15 minutes before.
"""

events = extract_calendar_events(transcript)

print("\nExtracted Events:\n")

for event in events:
    print(event)