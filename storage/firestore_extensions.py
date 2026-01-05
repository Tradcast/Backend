from google.cloud import firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from datetime import datetime, timezone
import asyncio
from typing import Optional, Dict, Any, List
from threading import Thread
import time


class FirestoreThreads:
    """Background thread manager for Firestore operations"""
    
    def __init__(self, firestore_manager):
        """
        Initialize the thread manager
        
        Args:
            firestore_manager: Instance of FirestoreManager
        """
        self.firestore_manager = firestore_manager
        self.db = firestore_manager.db
        self.running = False
        self.energy_thread = None
    
    def start(self):
        """Start all background threads"""
        self.running = True
        self.energy_thread = Thread(target=self._run_energy_regeneration, daemon=True)
        self.energy_thread.start()
        print("FirestoreThreads started")
    
    def stop(self):
        """Stop all background threads"""
        self.running = False
        if self.energy_thread:
            self.energy_thread.join(timeout=5)
        print("FirestoreThreads stopped")
    
    def check_status(self):
        print(self.running)

    def _run_energy_regeneration(self):
        """Run energy regeneration in a thread"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self._energy_regeneration_loop())
        finally:
            loop.close()
    
    async def _energy_regeneration_loop(self):
        """Main loop for energy regeneration"""
        while self.running:
            try:
                # Wait until the start of the next hour
                # await self._wait_until_next_hour()
                await asyncio.sleep(10)
                if not self.running:
                    break
                print('reenergy') 
                # Regenerate energy for all users
                await self._regenerate_energy_for_all_users()
                
            except Exception as e:
                print(f"Error in energy regeneration loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def _wait_until_next_hour(self):
        """Wait until the start of the next hour"""
        now = datetime.now(timezone.utc)
        
        # Calculate seconds until next hour
        next_hour = now.replace(minute=0, second=0, microsecond=0)
        next_hour = next_hour.replace(hour=now.hour + 1)
        
        seconds_to_wait = (next_hour - now).total_seconds()
        
        print(f"Waiting {seconds_to_wait:.0f} seconds until next hour ({next_hour})")
        
        # Sleep in chunks to allow for graceful shutdown
        while seconds_to_wait > 0 and self.running:
            sleep_time = min(seconds_to_wait, 60)  # Check every minute
            await asyncio.sleep(sleep_time)
            seconds_to_wait -= sleep_time
    
    async def _regenerate_energy_for_all_users(self):
        """Regenerate energy for all users with energy < 10"""
        try:
            print(f"Starting energy regeneration at {datetime.now(timezone.utc)}")
            
            # Query all users with energy < 10
            users_ref = self.db.collection(self.firestore_manager.users_collection)
            query = users_ref.where("energy", "<", 10)
            
            docs = await query.get()
            
            if not docs:
                print("No users need energy regeneration")
                return
            
            # Update all users in batches (Firestore allows 500 ops per batch)
            batch = self.db.batch()
            batch_count = 0
            total_updated = 0
            
            for doc in docs:
                data = doc.to_dict()
                current_energy = data.get("energy", 0)
                
                # Only increment if energy is less than 10
                if current_energy < 10:
                    doc_ref = users_ref.document(doc.id)
                    batch.update(doc_ref, {
                        "energy": min(current_energy + 1, 10)  # Cap at 10
                    })
                    batch_count += 1
                    total_updated += 1
                
                # Commit batch if we've reached 500 operations
                if batch_count >= 500:
                    await batch.commit()
                    batch = self.db.batch()
                    batch_count = 0
            
            # Commit remaining operations
            if batch_count > 0:
                await batch.commit()
            
            print(f"Energy regeneration complete. Updated {total_updated} users")
            
        except Exception as e:
            print(f"Error regenerating energy: {e}")


class LeaderboardManager:
    """Manager for leaderboard operations"""
    
    def __init__(self, db: AsyncClient):
        self.db = db
        self.users_collection = "users"
        self.weekly_leaderboard_collection = "weekly_leaderboards"
    
    async def get_all_time_leaderboard(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all-time leaderboard based on total_profit
        NOTE: Requires Firestore index on 'total_profit' (descending)
        
        Args:
            limit: Number of top users to return
            
        Returns:
            List of user data sorted by total_profit
        """
        users_ref = self.db.collection(self.users_collection)
        query = users_ref.order_by("total_profit", direction=firestore.Query.DESCENDING).limit(limit)
        
        docs = await query.get()
        
        leaderboard = []
        for rank, doc in enumerate(docs, start=1):
            data = doc.to_dict()
            leaderboard.append({
                "rank": rank,
                "fid": doc.id,
                "username": data.get("username", ""),
                "total_profit": data.get("total_profit", 0),
                "total_games": data.get("total_games", 0)
            })
        
        return leaderboard
    
    async def get_weekly_leaderboard(
        self, 
        week_start: datetime, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get weekly leaderboard for a specific week
        
        Args:
            week_start: Start of the week (Monday 00:00 UTC)
            limit: Number of top users to return
            
        Returns:
            List of user data sorted by weekly profit
        """
        # Format week identifier (e.g., "2025-W50")
        week_id = week_start.strftime("%Y-W%U")
        
        doc_ref = self.db.collection(self.weekly_leaderboard_collection).document(week_id)
        doc = await doc_ref.get()
        
        if not doc.exists:
            return []
        
        data = doc.to_dict()
        user_scores = data.get("user_scores", {})
        
        # Sort by profit and create leaderboard
        sorted_users = sorted(
            user_scores.items(), 
            key=lambda x: x[1].get("profit", 0), 
            reverse=True
        )[:limit]
        
        leaderboard = []
        for rank, (fid, user_data) in enumerate(sorted_users, start=1):
            leaderboard.append({
                "rank": rank,
                "fid": fid,
                "username": user_data.get("username", ""),
                "weekly_profit": user_data.get("profit", 0),
                "games_played": user_data.get("games", 0)
            })
        
        return leaderboard
    
    async def update_weekly_leaderboard(
        self, 
        fid: str, 
        username: str,
        session_profit: float,
        session_time: datetime
    ):
        """
        Update weekly leaderboard with new game session result
        
        Args:
            fid: User's FID
            username: User's username
            session_profit: Profit from this session
            session_time: When the session occurred
        """
        # Determine week identifier
        week_id = session_time.strftime("%Y-W%U")
        
        doc_ref = self.db.collection(self.weekly_leaderboard_collection).document(week_id)
        
        # Update using Firestore's increment
        await doc_ref.set({
            f"user_scores.{fid}.profit": firestore.Increment(session_profit),
            f"user_scores.{fid}.games": firestore.Increment(1),
            f"user_scores.{fid}.username": username,
            f"user_scores.{fid}.last_updated": firestore.SERVER_TIMESTAMP
        }, merge=True)
    
    async def get_user_weekly_rank(self, fid: str, week_start: datetime) -> Optional[Dict[str, Any]]:
        """
        Get a specific user's rank and stats for a week
        
        Args:
            fid: User's FID
            week_start: Start of the week
            
        Returns:
            User's rank and stats or None
        """
        leaderboard = await self.get_weekly_leaderboard(week_start, limit=1000)
        
        for entry in leaderboard:
            if entry["fid"] == fid:
                return entry
        
        return None


# IMPORTANT: To enable efficient leaderboard queries, create these Firestore indexes:
# 
# 1. For all-time leaderboard:
#    Collection: users
#    Fields: total_profit (Descending)
#
# 2. In Firebase Console, go to:
#    Firestore Database > Indexes > Create Index
#    
# Or use the Firebase CLI:
# {
#   "indexes": [
#     {
#       "collectionGroup": "users",
#       "queryScope": "COLLECTION",
#       "fields": [
#         {"fieldPath": "total_profit", "order": "DESCENDING"}
#       ]
#     }
#   ]
# }

class GiveawayHandler:
    """Extension class for FirestoreManager with time-based game activity checks"""

    def __init__(self, firestore_manager):
        """
        Initialize with an existing FirestoreManager instance

        Args:
            firestore_manager: Instance of FirestoreManager
        """
        self.fm = firestore_manager

        # Global configuration - 48 hour period
        # Start: December 22, 2025 at 1:00 PM (13:00)
        # End: December 24, 2025 at 12:00 AM (00:00)
        self.start_time = datetime(2025, 12, 22, 13, 0, 0, tzinfo=timezone.utc)
        self.end_time = datetime(2025, 12, 25, 23, 59, 0, tzinfo=timezone.utc)

    async def check_user_played_minimum_games(
        self,
        fid: str,
        minimum_games: int = 3,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if a user has played at least the minimum number of games
        within the specified time period

        Args:
            fid: User's FID
            minimum_games: Minimum number of games required (default 3)
            start_time: Optional custom start time (uses global if not provided)
            end_time: Optional custom end time (uses global if not provided)

        Returns:
            True if user played >= minimum_games, False otherwise
        """
        try:
            # Use provided times or fall back to global configuration
            query_start = start_time or self.start_time
            query_end = end_time or self.end_time

            # Query trade_decisions collection with time filters and fid filter
            query = self.fm.db.collection(self.fm.trade_decisions_collection)\
                .where("fid", "==", fid)\
                .where("created_at", ">=", query_start)\
                .where("created_at", "<", query_end)

            docs = await query.get()
            for d in docs:
                print(d)

            # Check if user has played at least minimum_games times
            game_count = len(docs)
            print(game_count)
            return game_count >= minimum_games

        except Exception as e:
            print(f"Error checking user game activity for {fid}: {e}")
            return False

    async def get_user_game_count_in_period(
        self,
        fid: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        Get the number of games a user played in the specified period

        Args:
            fid: User's FID
            start_time: Optional custom start time (uses global if not provided)
            end_time: Optional custom end time (uses global if not provided)

        Returns:
            Number of games played in the period
        """
        try:
            query_start = start_time or self.start_time
            query_end = end_time or self.end_time

            query = self.fm.db.collection(self.fm.trade_decisions_collection)\
                .where("fid", "==", fid)\
                .where("created_at", ">=", query_start)\
                .where("created_at", "<", query_end)

            docs = await query.get()

            return len(docs)

        except Exception as e:
            print(f"Error getting game count for {fid}: {e}")
            return 0



# Updated FirestoreManager methods for new game session structure:
class FirestoreManagerExtended:
    """Extended methods for the new game session structure"""
    
    async def save_game_session_with_leaderboard(
        self,
        firestore_manager,
        leaderboard_manager: LeaderboardManager,
        fid: str,
        username: str,
        trade_env_id: str,
        actions: List[Dict[str, Any]],
        final_pnl: float,
        final_profit: float
    ) -> bool:
        """
        Save game session with new structure and update leaderboards
        
        Args:
            firestore_manager: FirestoreManager instance
            leaderboard_manager: LeaderboardManager instance
            fid: User's FID
            username: User's username
            trade_env_id: Unique game session ID
            actions: List of trade actions
            final_pnl: Final PnL
            final_profit: Final profit
            
        Returns:
            True if successful
        """
        try:
            session_time = datetime.now(timezone.utc)
            
            # 1. Create session object
            session_data = {
                "session_id": trade_env_id,
                "session_time": session_time,
                "session_total_profit": final_profit,
                "session_pnl": final_pnl,
                "actions": actions
            }
            
            # 2. Add to user's game_sessions array
            game_sessions_ref = firestore_manager.db.collection(
                firestore_manager.game_sessions_collection
            ).document(fid)
            
            await game_sessions_ref.set({
                "game_sessions": firestore.ArrayUnion([session_data])
            }, merge=True)
            
            # 3. Save trade decisions (for detailed history)
            trade_decisions_data = {
                "trade_env_id": trade_env_id,
                "fid": fid,
                "actions": actions,
                "final_pnl": final_pnl,
                "final_profit": final_profit,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            await firestore_manager.db.collection(
                firestore_manager.trade_decisions_collection
            ).document(trade_env_id).set(trade_decisions_data)
            
            # 4. Update user totals
            user_ref = firestore_manager.db.collection(
                firestore_manager.users_collection
            ).document(fid)
            await user_ref.update({
                "total_games": firestore.Increment(1),
                "total_profit": firestore.Increment(final_profit),
                "total_PnL": firestore.Increment(final_pnl),
                "last_online": firestore.SERVER_TIMESTAMP
            })
            
            # 5. Update weekly leaderboard
            await leaderboard_manager.update_weekly_leaderboard(
                fid, username, final_profit, session_time
            )
            
            return True
            
        except Exception as e:
            print(f"Error saving game session: {e}")
            return False



from datetime import datetime, timezone
from typing import Optional
import asyncio

class GiveawayHandler:
    """Extension class for FirestoreManager with time-based game activity checks"""
    def __init__(self, firestore_manager):
        """
        Initialize with an existing FirestoreManager instance
        Args:
            firestore_manager: Instance of FirestoreManager
        """
        self.fm = firestore_manager
        # Global configuration - 48 hour period
        # Start: December 22, 2025 at 1:00 PM (13:00)
        # End: December 24, 2025 at 12:00 AM (00:00)
        self.start_time = datetime(2025, 12, 22, 13, 0, 0, tzinfo=timezone.utc)
        self.end_time = datetime(2025, 12, 25, 23, 59, 0, tzinfo=timezone.utc)

    async def check_user_played_minimum_games(
        self,
        fid: str,
        minimum_games: int = 3,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> bool:
        """
        Check if a user has played at least the minimum number of games
        within the specified time period
        Args:
            fid: User's FID
            minimum_games: Minimum number of games required (default 3)
            start_time: Optional custom start time (uses global if not provided)
            end_time: Optional custom end time (uses global if not provided)
        Returns:
            True if user played >= minimum_games, False otherwise
        """
        try:
            query_start = start_time or self.start_time
            query_end = end_time or self.end_time

            query = self.fm.db.collection(self.fm.trade_decisions_collection)\
                .where("fid", "==", fid)\
                .where("created_at", ">=", query_start)\
                .where("created_at", "<", query_end)

            docs = await query.get()

            for d in docs:
                print(d)

            game_count = len(docs)
            print(game_count)
            return game_count >= minimum_games
        except Exception as e:
            print(f"Error checking user game activity for {fid}: {e}")
            return False

    async def get_user_game_count_in_period(
        self,
        fid: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> int:
        """
        Get the number of games a user played in the specified period
        Args:
            fid: User's FID
            start_time: Optional custom start time (uses global if not provided)
            end_time: Optional custom end time (uses global if not provided)
        Returns:
            Number of games played in the period
        """
        try:
            query_start = start_time or self.start_time
            query_end = end_time or self.end_time

            query = self.fm.db.collection(self.fm.trade_decisions_collection)\
                .where("fid", "==", fid)\
                .where("created_at", ">=", query_start)\
                .where("created_at", "<", query_end)

            docs = await query.get()
            return len(docs)
        except Exception as e:
            print(f"Error getting game count for {fid}: {e}")
            return 0



from datetime import datetime, timezone
from typing import Optional
import asyncio


class GiveawayParticipantCounter:
    """Class to count and display users who qualified for giveaway by playing games"""

    def __init__(self, firestore_manager):
        """
        Initialize with an existing FirestoreManager instance
        Args:
            firestore_manager: Instance of FirestoreManager
        """
        self.fm = firestore_manager
        self.trade_decisions_collection = "trade_decisions"
        
        # Giveaway period configuration
        self.start_time = datetime(2025, 12, 22, 13, 0, 0, tzinfo=timezone.utc)
        self.end_time = datetime(2025, 12, 25, 23, 59, 0, tzinfo=timezone.utc)
        self.minimum_games = 3

    async def get_all_game_records_in_period(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> list[dict]:
        """
        Get all game records within the specified time period
        Args:
            start_time: Optional custom start time (uses global if not provided)
            end_time: Optional custom end time (uses global if not provided)
        Returns:
            List of game record dictionaries
        """
        try:
            query_start = start_time or self.start_time
            query_end = end_time or self.end_time

            query = self.fm.db.collection(self.trade_decisions_collection)\
                .where("created_at", ">=", query_start)\
                .where("created_at", "<", query_end)

            docs = await query.get()
            
            records = []
            for doc in docs:
                data = doc.to_dict()
                records.append(data)
            
            return records
        except Exception as e:
            print(f"Error getting game records: {e}")
            return []

    async def count_qualified_participants(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        minimum_games: Optional[int] = None
    ) -> int:
        """
        Count users who played minimum required games
        Args:
            start_time: Optional custom start time
            end_time: Optional custom end time
            minimum_games: Optional custom minimum (default: 3)
        Returns:
            Number of qualified participants
        """
        participants = await self.get_qualified_participants(start_time, end_time, minimum_games)
        return len(participants)

    async def get_qualified_participants(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        minimum_games: Optional[int] = None
    ) -> list[dict]:
        """
        Get all users who qualified by playing minimum games
        Args:
            start_time: Optional custom start time
            end_time: Optional custom end time
            minimum_games: Optional custom minimum (default: 3)
        Returns:
            List of participant dicts with fid, username, and game_count
        """
        try:
            records = await self.get_all_game_records_in_period(start_time, end_time)
            min_games = minimum_games or self.minimum_games
            
            # Group by FID and count games
            user_games = {}
            for record in records:
                fid = record.get("fid")
                username = record.get("username", "Unknown")
                
                if fid:
                    if fid not in user_games:
                        user_games[fid] = {
                            "fid": fid,
                            "username": username,
                            "game_count": 0,
                            "games": []
                        }
                    user_games[fid]["game_count"] += 1
                    user_games[fid]["games"].append(record.get("created_at"))
            
            # Filter users who met minimum requirement
            qualified = [
                user_data for user_data in user_games.values()
                if user_data["game_count"] >= min_games
            ]
            
            return qualified
        except Exception as e:
            print(f"Error getting qualified participants: {e}")
            return []

    async def print_participants(
        self,
        sort_by: str = "game_count",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> None:
        """
        Print all qualified participants in a formatted table
        Args:
            sort_by: Field to sort by ('game_count', 'username', or 'fid')
            start_time: Optional custom start time
            end_time: Optional custom end time
        """
        participants = await self.get_qualified_participants(start_time, end_time)
        
        print("\n" + "=" * 80)
        print(f"GIVEAWAY QUALIFIED PARTICIPANTS ({len(participants)} total)")
        print(f"Period: {(start_time or self.start_time).strftime('%Y-%m-%d %H:%M')} to "
              f"{(end_time or self.end_time).strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"Minimum Games Required: {self.minimum_games}")
        print("=" * 80)
        
        if not participants:
            print("No qualified participants found.")
            return
        
        # Sort participants
        if sort_by == "username":
            participants.sort(key=lambda x: x.get("username", "").lower())
        elif sort_by == "fid":
            participants.sort(key=lambda x: x.get("fid", ""))
        else:  # Default to game_count (descending)
            participants.sort(key=lambda x: x.get("game_count", 0), reverse=True)
        
        # Print header
        print(f"{'#':<5} {'Username':<25} {'FID':<15} {'Games Played':<15}")
        print("-" * 80)
        
        # Print each participant
        for idx, p in enumerate(participants, 1):
            username = p.get("username", "N/A")
            fid = p.get("fid", "N/A")
            game_count = p.get("game_count", 0)
            
            print(f"{idx:<5} {username:<25} {fid:<15} {game_count:<15}")
        
        print("=" * 80 + "\n")

    async def print_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> None:
        """Print summary statistics of the giveaway"""
        participants = await self.get_qualified_participants(start_time, end_time)
        all_records = await self.get_all_game_records_in_period(start_time, end_time)
        
        total_games = len(all_records)
        qualified_count = len(participants)
        
        print("\n" + "=" * 60)
        print("GIVEAWAY SUMMARY")
        print("=" * 60)
        print(f"Period: {(start_time or self.start_time).strftime('%Y-%m-%d %H:%M')} to")
        print(f"        {(end_time or self.end_time).strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"Minimum Games Required: {self.minimum_games}")
        print("-" * 60)
        print(f"Total Games Played: {total_games}")
        print(f"Qualified Participants: {qualified_count}")
        
        if participants:
            game_counts = [p.get("game_count", 0) for p in participants]
            avg_games = sum(game_counts) / len(game_counts)
            max_games = max(game_counts)
            min_games = min(game_counts)
            
            print(f"Average Games per Participant: {avg_games:.1f}")
            print(f"Most Games by One User: {max_games}")
            print(f"Fewest Games (qualified): {min_games}")
            
            # Top players
            top_players = sorted(participants, key=lambda x: x.get("game_count", 0), reverse=True)[:5]
            print("\nTop 5 Most Active Players:")
            for i, player in enumerate(top_players, 1):
                print(f"  {i}. {player.get('username')} - {player.get('game_count')} games")
        
        print("=" * 60 + "\n")

    async def print_usernames_only(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> None:
        """Print just the usernames of qualified participants"""
        participants = await self.get_qualified_participants(start_time, end_time)
        usernames = [p.get("username") for p in participants if p.get("username")]
        usernames.sort()
        
        print("\n" + "=" * 50)
        print(f"QUALIFIED PARTICIPANT USERNAMES ({len(usernames)})")
        print("=" * 50)
        
        for username in usernames:
            print(f"  • {username}")
        
        print("=" * 50 + "\n")

    async def check_user_qualified(self, fid: str) -> tuple[bool, int]:
        """
        Check if a specific user qualified
        Args:
            fid: User's FID
        Returns:
            Tuple of (is_qualified, game_count)
        """
        participants = await self.get_qualified_participants()
        
        for p in participants:
            if p.get("fid") == fid:
                return (True, p.get("game_count", 0))
        
        # Check game count even if not qualified
        records = await self.get_all_game_records_in_period()
        user_count = sum(1 for r in records if r.get("fid") == fid)
        
        return (False, user_count)


# Example usage
async def demo():
    """Demo the GiveawayParticipantCounter"""
    # Note: Replace with your actual FirestoreManager
    from firestore_client import FirestoreManager
    
    fm = FirestoreManager()
    counter = GiveawayParticipantCounter(fm)
    
    # Get count
    count = await counter.count_qualified_participants()
    print(f"Total qualified participants: {count}")
    
    # Print all participants (sorted by most games)
    await counter.print_participants()
    
    # Print participants sorted by username
    await counter.print_participants(sort_by="username")
    
    # Print summary with statistics
    await counter.print_summary()
    
    # Print just usernames
    await counter.print_usernames_only()
    
    # Check if specific user qualified
    qualified, games = await counter.check_user_qualified("123")
    print(f"User 123 qualified: {qualified} ({games} games played)")


if __name__ == "__main__":
    asyncio.run(demo())


exit()

async def main():
    """Main function to test the thread manager and leaderboards"""
    print("Initializing Firestore managers...")
    
    # Initialize managers
    from storage.firestore_client import FirestoreManager  # Import your original FirestoreManager
    firestore_manager = FirestoreManager()
    firestore_threads = FirestoreThreads(firestore_manager)
    leaderboard_manager = LeaderboardManager(firestore_manager.db)
    extended_manager = FirestoreManagerExtended()
    
    try:
        # Start energy regeneration thread
        print("\n=== Starting Energy Regeneration Thread ===")
        firestore_threads.start()
        
        # Test: Create a test user
        print("\n=== Creating Test User ===")
        test_fid = "123"
        await firestore_manager.initiate_user(test_fid, username="TestPlayer", wallet="0x123")
        
        # Set energy to 5 for testing
        await firestore_manager.update_user(test_fid, {"energy": 5})
        user = await firestore_manager.get_user(test_fid)
        print(f"Test user created: {user}")
        
        # Test: Save a game session
        print("\n=== Saving Test Game Session ===")
        test_actions = [
            {"action": "buy", "time": 10, "price": 100},
            {"action": "sell", "time": 20, "price": 110}
        ]
        
        success = await extended_manager.save_game_session_with_leaderboard(
            firestore_manager,
            leaderboard_manager,
            fid=test_fid,
            username="TestPlayer",
            trade_env_id="session_001",
            actions=test_actions,
            final_pnl=10.0,
            final_profit=100.0
        )
        print(f"Game session saved: {success}")
        
        # Test: Get all-time leaderboard
        print("\n=== All-Time Leaderboard ===")
        all_time_board = await leaderboard_manager.get_all_time_leaderboard(limit=10)
        for entry in all_time_board:
            print(f"#{entry['rank']}: {entry['username']} - Profit: {entry['total_profit']}")
        
        # Test: Get weekly leaderboard
        print("\n=== Weekly Leaderboard ===")
        from datetime import timedelta
        today = datetime.now(timezone.utc)
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        
        weekly_board = await leaderboard_manager.get_weekly_leaderboard(week_start, limit=10)
        for entry in weekly_board:
            print(f"#{entry['rank']}: {entry['username']} - Weekly Profit: {entry['weekly_profit']}")
        
        # Keep the thread running for a bit to test energy regeneration
        print("\n=== Thread Running (Press Ctrl+C to stop) ===")
        print("Energy regeneration will occur at the start of each hour...")
        print("Current user energy:", (await firestore_manager.get_user(test_fid))["energy"])
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(60)  # Check every minute
            current_energy = (await firestore_manager.get_user(test_fid))["energy"]
            print(f"Current time: {datetime.now(timezone.utc)} | User energy: {current_energy}")
            
    except KeyboardInterrupt:
        print("\n\n=== Shutting Down ===")
    finally:
        # Clean up
        firestore_threads.stop()
        print("Threads stopped successfully")


if __name__ == "__main__":
    print("Starting Firestore Thread Manager...")
    asyncio.run(main())


# Usage Example with FastAPI:
"""
from fastapi import FastAPI, HTTPException
import asyncio

app = FastAPI()

# Initialize managers
firestore_manager = FirestoreManager()
firestore_threads = FirestoreThreads(firestore_manager)
leaderboard_manager = LeaderboardManager(firestore_manager.db)
extended_manager = FirestoreManagerExtended()

@app.on_event("startup")
async def startup_event():
    # Start energy regeneration thread
    firestore_threads.start()

@app.on_event("shutdown")
async def shutdown_event():
    # Stop threads gracefully
    firestore_threads.stop()

@app.get("/leaderboard/all-time")
async def get_all_time_leaderboard(limit: int = 100):
    return await leaderboard_manager.get_all_time_leaderboard(limit)

@app.get("/leaderboard/weekly")
async def get_weekly_leaderboard(limit: int = 100):
    from datetime import datetime, timedelta
    # Get current week's Monday
    today = datetime.now(timezone.utc)
    week_start = today - timedelta(days=today.weekday())
    week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    return await leaderboard_manager.get_weekly_leaderboard(week_start, limit)

@app.post("/game-session/complete")
async def complete_game_session(
    fid: str,
    username: str,
    trade_env_id: str,
    actions: List[Dict],
    final_pnl: float,
    final_profit: float
):
    success = await extended_manager.save_game_session_with_leaderboard(
        firestore_manager,
        leaderboard_manager,
        fid,
        username,
        trade_env_id,
        actions,
        final_pnl,
        final_profit
    )
    if success:
        return {"message": "Game session saved and leaderboards updated"}
    raise HTTPException(status_code=500, detail="Failed to save session")
"""
