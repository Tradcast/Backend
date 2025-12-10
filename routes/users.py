from fastapi import APIRouter
from storage.firestore_client import FirestoreManager
from utils.route_utils import handle_streak
from typing import Optional
from fastapi import Request

user_router = APIRouter()
firestore_manager = FirestoreManager()


@user_router.get("/home")
async def get_home(fid: int):
    fid_str = str(fid)

    user = await firestore_manager.get_user(fid_str)
    if not user:
        print("user not found")
        user = await firestore_manager.initiate_user(fid_str)

    # apply streak logic
    await handle_streak(fid_str, user, firestore_manager)

    # fetch user again after updates (important!)
    updated = await firestore_manager.get_user(fid_str)

    return updated


@user_router.get("/profile")
async def get_profile(
    fid: int,
    username: Optional[str] = "",
    wallet: Optional[str] = "",
):
    fid_str = str(fid)

    user = await firestore_manager.get_user(fid_str)
    if not user:
        print("user not found")
        user = await firestore_manager.initiate_user(fid_str, wallet=wallet, username=username)

    # apply streak logic
    await handle_streak(fid_str, user, firestore_manager)

    # fetch user again after updates
    updated = await firestore_manager.get_user(fid_str)

    # You can extend with trades etc. here:
    # latest_trades = ...
    # updated["trades"] = latest_trades

    return updated


@user_router.get("/leaderboard")
async def get_leaderboard(fid: int):
    # get leaderboard data
    # leaderboard = await firestore_manager.get_leaderboard()
    
    return {
        "user_loc": None,
        "top_10": [],
    }

