from fastapi import APIRouter
from storage.firestore_client import FirestoreManager
#from storage.firestore_extensions import GiveawayHandler
from utils.route_utils import handle_streak
from typing import Optional
from fastapi import Request

user_router = APIRouter()
firestore_manager = FirestoreManager()
#giveaway_handler = GiveawayHandler(firestore_manager)

@user_router.get("/home")
async def get_home(fid: int):
    fid_str = str(fid)
    user = await firestore_manager.get_user(fid_str)
    if not user:
        print("user not found")
        user = await firestore_manager.initiate_user(fid_str)
    
    # Apply streak logic
    await handle_streak(fid_str, user, firestore_manager)
    
    # Fetch user again after updates (important!)
    updated = await firestore_manager.get_user(fid_str)
    
    # Check if user is eligible for giveaway (played 3+ games in the period)
    giveaway_eligible = None #await giveaway_handler.check_user_played_minimum_games(fid_str)
    
    # Add giveaway eligibility to response
    updated["giveaway_eligible"] = giveaway_eligible
    
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

    # Apply streak logic
    await handle_streak(fid_str, user, firestore_manager)

    # Fetch user again after updates
    updated = await firestore_manager.get_user(fid_str)

    # Get latest trades and extend the response
    latest_trades = await firestore_manager.get_latest_trades(fid_str, number=4)
    print(latest_trades)
    updated["latest_trades"] = latest_trades

    return updated

@user_router.get("/leaderboard")
async def get_leaderboard(fid: int, top_n: int = 10):
    """
    Get all-time leaderboard based on total_profit
    
    Args:
        fid: User's FID to mark in leaderboard
        top_n: Number of top users to return (default 10)
    
    Returns:
        {
            "leaderboard": [
                {
                    "username": str,
                    "total_profit": float,
                    "the_user": bool,
                    "rank": int
                },
                ...
            ]
        }
    """
    fid_str = str(fid)
    
    # Ensure user exists
    user = await firestore_manager.get_user(fid_str)
    if not user:
        user = await firestore_manager.initiate_user(fid_str)
    
    # Get leaderboard
    leaderboard = await firestore_manager.get_leaderboard(fid_str, top_n=top_n)
    
    return {
        "leaderboard": leaderboard
    }

@user_router.get("/leaderboard/weekly")
async def get_weekly_leaderboard(fid: int, top_n: int = 10):
    """
    Get weekly leaderboard based on final_profit from last 7 days
    
    Args:
        fid: User's FID to mark in leaderboard
        top_n: Number of top users to return (default 10)
    
    Returns:
        {
            "leaderboard": [
                {
                    "username": str,
                    "final_profit": float,
                    "the_user": bool,
                    "rank": int
                },
                ...
            ]
        }
    """
    fid_str = str(fid)
    
    # Ensure user exists
    user = await firestore_manager.get_user(fid_str)
    if not user:
        user = await firestore_manager.initiate_user(fid_str)
    
    # Get weekly leaderboard
    leaderboard = await firestore_manager.get_weekly_leaderboard(fid_str, top_n=top_n)
    
    return {
        "leaderboard": leaderboard
    }


@user_router.get("/leaderboard/daily")
async def get_daily_leaderboard(fid: int, top_n: int = 5):
    """
    Get weekly leaderboard based on final_profit from last 7 days

    Args:
        fid: User's FID to mark in leaderboard
        top_n: Number of top users to return (default 10)

    Returns:
        {
            "leaderboard": [
                {
                    "username": str,
                    "final_profit": float,
                    "the_user": bool,
                    "rank": int
                },
                ...
            ]
        }
    """
    fid_str = str(fid)

    # Ensure user exists
    user = await firestore_manager.get_user(fid_str)
    if not user:
        user = await firestore_manager.initiate_user(fid_str)

    # Get weekly leaderboard
    leaderboard = await firestore_manager.get_daily_leaderboard(fid_str, top_n=top_n)

    return {
        "leaderboard": leaderboard
    }

