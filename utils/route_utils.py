from datetime import datetime, timezone, timedelta
from google.cloud.firestore_v1 import SERVER_TIMESTAMP


async def handle_streak(fid: str, user, firestore_manager):
    now = datetime.now(timezone.utc)

    last_online = user.get("last_online")

    # First login or unresolved SERVER_TIMESTAMP
    if not last_online or last_online is SERVER_TIMESTAMP:
        await firestore_manager.reset_streak_days(fid)
        await firestore_manager.make_last_online_now(fid)
        return

    # Normal datetime
    last_date = last_online.date()
    today = now.date()
    yesterday = today - timedelta(days=1)

    if last_date == today:
        # already logged in today
        return

    elif last_date == yesterday:
        await firestore_manager.increment_streak_days(fid)

    else:
        await firestore_manager.reset_streak_days(fid)

    await firestore_manager.make_last_online_now(fid)

