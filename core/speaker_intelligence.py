def calculate_talk_time(segments):

    stats = {}

    for seg in segments:

        speaker = seg.get("speaker", "Unknown")

        duration = (
            seg.get("end", 0)
            - seg.get("start", 0)
        )

        stats[speaker] = (
            stats.get(speaker, 0)
            + duration
        )

    return stats


def calculate_participation(stats):

    total = sum(stats.values())

    if total == 0:
        return {}

    return {
        speaker: round(
            (time / total) * 100,
            1
        )
        for speaker, time in stats.items()
    }


def get_top_speaker(stats):

    if not stats:
        return None

    return max(
        stats,
        key=stats.get
    )