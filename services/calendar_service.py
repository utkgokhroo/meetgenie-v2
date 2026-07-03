from datetime import datetime, timedelta

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_calendar_service(token):
    """
    Build a Google Calendar service from the OAuth token.
    """

    credentials = Credentials(
        token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=token["client_id"],
        client_secret=token["client_secret"],
        scopes=SCOPES,
    )

    return build("calendar", "v3", credentials=credentials)


def create_calendar_events(events, token):

    service = get_calendar_service(token)

    created = []

    for event in events:

        try:

            start = datetime.strptime(
                f"{event['date']} {event['time']}",
                "%Y-%m-%d %H:%M",
            )

            end = start + timedelta(
                minutes=event.get("duration_minutes", 60)
            )

            body = {
                "summary": event["title"],
                "description": event.get("description", ""),

                "start": {
                    "dateTime": start.isoformat(),
                    "timeZone": "Asia/Kolkata",
                },

                "end": {
                    "dateTime": end.isoformat(),
                    "timeZone": "Asia/Kolkata",
                },

                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {
                            "method": "popup",
                            "minutes": event.get(
                                "reminder_minutes", 30
                            ),
                        },
                        {
                            "method": "email",
                            "minutes": 60,
                        },
                    ],
                },
            }

            created_event = (
                service.events()
                .insert(calendarId="primary", body=body)
                .execute()
            )

            created.append(created_event)

        except Exception as e:
            print(e)

    return created