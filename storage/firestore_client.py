from google.cloud import firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from datetime import datetime, timedelta
import string, time, asyncio, random
from typing import Optional, Dict, Any, List


class FirestoreManager:
    def __init__(self):
        """Initialize async Firestore client"""
        self.db: AsyncClient = firestore.AsyncClient(project="miniapp-479712")

        self.users_collection = "users"
        self.trade_decisions_collection = "trade_decisions"
    
    def _generate_invitation_key(self, length: int = 6) -> str:
        """Generate a unique random invitation key"""
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    
    async def _is_invitation_key_unique(self, key: str) -> bool:
        """Check if invitation key is unique"""
        users_ref = self.db.collection(self.users_collection)
        query = users_ref.where("invitation_key", "==", key).limit(1)
        docs = await query.get()
        return len(docs) == 0
    
    async def _generate_unique_invitation_key(self) -> str:
        """Generate a unique invitation key"""
        while True:
            key = self._generate_invitation_key()
            if await self._is_invitation_key_unique(key):
                return key
    
    async def initiate_user(self, fid: str, username: str = "", wallet: str = "", is_banned=False) -> Dict[str, Any]:
        """
        Initialize a new user with default values
        
        Args:
            fid: User's FID (unique identifier)
            username: Optional username
            wallet: Optional wallet address
            
        Returns:
            User data dictionary
        """
        invitation_key = await self._generate_unique_invitation_key()
        
        user_data = {
            "username": username,
            "wallet": wallet,
            "total_games": 0,
            "last_online": firestore.SERVER_TIMESTAMP,
            "total_profit": 0,
            "total_PnL": 0,
            "energy": 10,
            "streak_days": 1,
            "invitation_key": invitation_key,
            "invited_key": "",
            "is_banned": is_banned
        }
        
        # Save to Firestore
        await self.db.collection(self.users_collection).document(fid).set(user_data)
        
        return user_data
    
    async def get_user(self, fid: str) -> Optional[Dict[str, Any]]:
        """
        Get user data by FID
        
        Args:
            fid: User's FID
            
        Returns:
            User data dictionary or None if not found
        """
        doc_ref = self.db.collection(self.users_collection).document(fid)
        doc = await doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        return None
    
    async def update_user(self, fid: str, updates: Dict[str, Any]) -> bool:
        """
        Dynamic update method for user fields
        
        Args:
            fid: User's FID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.db.collection(self.users_collection).document(fid)
            await doc_ref.update(updates)
            return True
        except Exception as e:
            print(f"Error updating user {fid}: {e}")
            return False
    
    async def reduce_energy(self, fid: str) -> bool:
        """
        Reduce user's energy by 1
        
        Args:
            fid: User's FID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.db.collection(self.users_collection).document(fid)
            snapshot = await doc_ref.get()
            print(doc_ref, snapshot)
            if not snapshot.exists:
                return False
            
            data = snapshot.to_dict() or {}
            print(data)
            energy = data.get("energy", 0)
            if energy <= 0:
                return False

            await doc_ref.update({"energy": energy - 1})
            return True

        except Exception as e:
            print(f"Error reducing energy for {fid}: {e}")
            return False
    
    async def reset_streak_days(self, fid: str) -> bool:
        """
        Reset streak days to 1
        
        Args:
            fid: User's FID
            
        Returns:
            True if successful, False otherwise
        """
        return await self.update_user(fid, {"streak_days": 1})
    
    async def increment_streak_days(self, fid: str) -> bool:
        """
        Add 1 to streak days
        
        Args:
            fid: User's FID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.db.collection(self.users_collection).document(fid)
            await doc_ref.update({
                "streak_days": firestore.Increment(1)
            })
            return True
        except Exception as e:
            print(f"Error incrementing streak days for {fid}: {e}")
            return False
    
    async def make_last_online_now(self, fid: str) -> bool:
        """
        Update last_online to current server time
        
        Args:
            fid: User's FID
            
        Returns:
            True if successful, False otherwise
        """
        return await self.update_user(fid, {"last_online": firestore.SERVER_TIMESTAMP})
    
    async def add_total_game(self, fid: str) -> bool:
        """
        Increment total_games by 1
        
        Args:
            fid: User's FID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            doc_ref = self.db.collection(self.users_collection).document(fid)
            await doc_ref.update({
                "total_games": firestore.Increment(1)
            })
            return True
        except Exception as e:
            print(f"Error incrementing total games for {fid}: {e}")
            return False
    
    async def add_game_session(
        self, 
        fid: str, 
        trade_env_id: str, 
        actions: List[Dict[str, Any]]
    ) -> bool:
        """
        Add a game session with trade decisions
        
        Args:
            fid: User's FID
            trade_env_id: Trade environment ID
            actions: List of actions [{"action": "buy", "time": 10}, ...]
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create the trade_decisions document with fid included
            trade_decisions_data = {
                "fid": fid,
                "trade_env_id": trade_env_id,
                "actions": actions,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            
            await self.db.collection(self.trade_decisions_collection).document(trade_env_id).set(
                trade_decisions_data
            )
            
            return True
        except Exception as e:
            print(f"Error adding game session for {fid}: {e}")
            return False
    
    async def get_game_sessions(self, fid: str) -> Optional[List[str]]:
        """
        Get all game session IDs for a user by querying trade_decisions
        
        Args:
            fid: User's FID
            
        Returns:
            List of game session IDs (trade_env_ids) or None
        """
        try:
            query = self.db.collection(self.trade_decisions_collection).where("fid", "==", fid)
            docs = await query.get()
            
            if docs:
                return [doc.id for doc in docs]
            return []
        except Exception as e:
            print(f"Error getting game sessions for {fid}: {e}")
            return None
    
    async def get_trade_decisions(self, trade_env_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trade decisions for a specific game session
        
        Args:
            trade_env_id: Trade environment ID
            
        Returns:
            Trade decisions data or None
        """
        doc_ref = self.db.collection(self.trade_decisions_collection).document(trade_env_id)
        doc = await doc_ref.get()
        
        if doc.exists:
            return doc.to_dict()
        return None

    async def delete_user(self, fid: str) -> bool:
        """
        Delete a user and all associated data

        Args:
            fid: User's FID

        Returns:
            True if successful, False otherwise
        """
        try:
            # 1. Get all game sessions for this user
            game_sessions = await self.get_game_sessions(fid)

            # 2. Delete all trade decisions for this user's sessions
            if game_sessions:
                for trade_env_id in game_sessions:
                    await self.db.collection(self.trade_decisions_collection).document(trade_env_id).delete()

            # 3. Delete the user document
            await self.db.collection(self.users_collection).document(fid).delete()

            return True
        except Exception as e:
            print(f"Error deleting user {fid}: {e}")
            return False

    async def delete_multiple_users(self, fids: List[str]) -> Dict[str, bool]:
        """
        Delete multiple users concurrently

        Args:
            fids: List of user FIDs to delete

        Returns:
            Dictionary mapping FID to success status
        """
        async def delete_single(fid: str) -> tuple:
            success = await self.delete_user(fid)
            return (fid, success)

        tasks = [delete_single(fid) for fid in fids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert to dictionary
        result_dict = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            fid, success = result
            result_dict[fid] = success

        return result_dict

    async def save_game_session_result(
            self,
            fid: str,
            trade_env_id: str,
            actions: List[Dict[str, Any]],
            final_pnl: float,
            final_profit: float
    ) -> bool:
        """
        Save game session results and update user stats atomically

        Args:
            fid: User's FID
            trade_env_id: Unique game session ID
            actions: List of trade actions with timestamps
            final_pnl: Final PnL for this session
            final_profit: Final profit for this session

        Returns:
            True if successful, False otherwise
        """
        try:
            # 1. Save trade decisions with fid included
            trade_decisions_data = {
                "fid": fid,
                "trade_env_id": trade_env_id,
                "actions": actions,
                "final_pnl": final_pnl,
                "final_profit": final_profit,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            await self.db.collection(self.trade_decisions_collection).document(trade_env_id).set(
                trade_decisions_data
            )

            # 2. Update user totals
            user_ref = self.db.collection(self.users_collection).document(fid)
            await user_ref.update({
                "total_games": firestore.Increment(1),
                "total_profit": firestore.Increment(final_profit),
                "total_PnL": firestore.Increment(final_pnl),
                "last_online": firestore.SERVER_TIMESTAMP
            })

            return True
        except Exception as e:
            print(f"Error saving game session result for {fid}: {e}")
            return False

    async def get_leaderboard(self, fid: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get leaderboard based on total_profit from users collection
        
        Args:
            fid: User's FID to mark in leaderboard
            top_n: Number of top users to return (default 10)
            
        Returns:
            List of leaderboard entries with format:
            [{"username": str, "total_profit": float, "the_user": bool, "rank": int}, ...]
        """
        try:
            # Get top N users ordered by total_profit
            query = self.db.collection(self.users_collection).order_by(
                "total_profit", direction=firestore.Query.DESCENDING
            ).limit(top_n)
            docs = await query.get()
            
            # Get the requesting user's data
            user_doc = await self.get_user(fid)
            user_username = user_doc.get("username", "Unknown") if user_doc else "Unknown"
            user_profit = user_doc.get("total_profit", 0) if user_doc else 0
            
            # Build leaderboard
            leaderboard = []
            user_in_top = False
            user_rank = None
            
            for idx, doc in enumerate(docs, start=1):
                data = doc.to_dict()
                doc_fid = doc.id
                
                entry = {
                    "username": data.get("username", "Unknown"),
                    "total_profit": data.get("total_profit", 0),
                    "the_user": doc_fid == fid,
                    "rank": idx
                }
                
                if doc_fid == fid:
                    user_in_top = True
                    user_rank = idx
                
                leaderboard.append(entry)
            
            # If user is not in top N, add them as 11th entry
            if not user_in_top:
                # Find user's actual rank
                all_users_query = self.db.collection(self.users_collection).order_by(
                    "total_profit", direction=firestore.Query.DESCENDING
                )
                all_docs = await all_users_query.get()
                
                user_rank = None
                for idx, doc in enumerate(all_docs, start=1):
                    if doc.id == fid:
                        user_rank = idx
                        break
                
                # Add user's entry
                leaderboard.append({
                    "username": user_username,
                    "total_profit": user_profit,
                    "the_user": True,
                    "rank": user_rank if user_rank else len(all_docs) + 1
                })
            
            return leaderboard
            
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []

    async def get_weekly_leaderboard(self, fid: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get weekly leaderboard based on final_profit from trade_decisions collection
        Filters for games created in the last 7 days
        
        Args:
            fid: User's FID to mark in leaderboard
            top_n: Number of top users to return (default 10)
            
        Returns:
            List of leaderboard entries with format:
            [{"username": str, "final_profit": float, "the_user": bool, "rank": int}, ...]
        """
        try:
            # Calculate timestamp for 1 week ago
            one_week_ago = datetime.now() - timedelta(days=7)
            
            # Get all trade decisions from last week
            query = self.db.collection(self.trade_decisions_collection).where(
                "created_at", ">=", one_week_ago
            )
            docs = await query.get()
            
            # Aggregate profits by user
            user_profits = {}
            for doc in docs:
                data = doc.to_dict()
                user_fid = data.get("fid")
                final_profit = data.get("final_profit", 0)
                
                if user_fid:
                    if user_fid not in user_profits:
                        user_profits[user_fid] = 0
                    user_profits[user_fid] += final_profit
            
            # Sort users by total weekly profit
            sorted_users = sorted(
                user_profits.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # Get usernames for all users
            leaderboard = []
            user_in_top = False
            user_rank = None
            
            for idx, (user_fid, profit) in enumerate(sorted_users[:top_n], start=1):
                user_doc = await self.get_user(user_fid)
                username = user_doc.get("username", "Unknown") if user_doc else "Unknown"
                
                entry = {
                    "username": username,
                    "final_profit": profit,
                    "the_user": user_fid == fid,
                    "rank": idx
                }
                
                if user_fid == fid:
                    user_in_top = True
                    user_rank = idx
                
                leaderboard.append(entry)
            
            # If user is not in top N, add them
            if not user_in_top:
                user_profit = user_profits.get(fid, 0)
                user_doc = await self.get_user(fid)
                username = user_doc.get("username", "Unknown") if user_doc else "Unknown"
                
                # Find user's rank
                for idx, (user_fid, _) in enumerate(sorted_users, start=1):
                    if user_fid == fid:
                        user_rank = idx
                        break
                
                if user_rank is None:
                    user_rank = len(sorted_users) + 1
                
                leaderboard.append({
                    "username": username,
                    "final_profit": user_profit,
                    "the_user": True,
                    "rank": user_rank
                })
            
            return leaderboard
            
        except Exception as e:
            print(f"Error getting weekly leaderboard: {e}")
            return []

    
    async def get_latest_trades(self, fid: str, number: int = 4) -> List[Dict[str, Any]]:
        """
        Get the latest N trades for a specific user
    
        Args:
            fid: User's FID
            number: Number of latest trades to retrieve (default 4)
    
        Returns:
            List of trade decision documents ordered by created_at (newest first)
            Each entry contains: trade_env_id, actions, final_pnl, final_profit, created_at
        """
        try:
            # Query trade_decisions collection filtered by fid
            query = self.db.collection(self.trade_decisions_collection).where(
                "fid", "==", fid
            ).order_by(
                "created_at", direction=firestore.Query.DESCENDING
            ).limit(number)
    
            docs = await query.get()
    
            # Build list of trade data
            trades = []
            for doc in docs:
                data = doc.to_dict()
                trades.append({
                    "trade_env_id": doc.id,
                    "actions": data.get("actions", []),
                    "final_pnl": data.get("final_pnl", 0),
                    "final_profit": data.get("final_profit", 0),
                    "created_at": data.get("created_at")
                })
    
            return trades
    
        except Exception as e:
            print(f"Error getting latest trades for {fid}: {e}")
            return []


async def main():
    firestore_manager = FirestoreManager()
    
    # Test user initialization
    print("=== Testing User Initialization ===")
    await firestore_manager.initiate_user('user1', username='Alice', wallet='wallet1')
    await firestore_manager.initiate_user('user2', username='Bob', wallet='wallet2')
    await firestore_manager.initiate_user('user3', username='Charlie', wallet='wallet3')
    await firestore_manager.initiate_user('user4', username='David', wallet='wallet4')
    await firestore_manager.initiate_user('user5', username='Eve', wallet='wallet5')
    
    # Add some game sessions with different profits
    print("\n=== Testing Game Session Results ===")
    await firestore_manager.save_game_session_result(
        'user1', 'game1', [{"action": "buy", "time": 10}], 100, 150
    )
    await firestore_manager.save_game_session_result(
        'user2', 'game2', [{"action": "sell", "time": 20}], 200, 300
    )
    await firestore_manager.save_game_session_result(
        'user3', 'game3', [{"action": "buy", "time": 15}], 150, 200
    )
    await firestore_manager.save_game_session_result(
        'user4', 'game4', [{"action": "sell", "time": 25}], 50, 75
    )
    await firestore_manager.save_game_session_result(
        'user5', 'game5', [{"action": "buy", "time": 30}], 300, 500
    )
    
    # Add more games for weekly leaderboard test
    await firestore_manager.save_game_session_result(
        'user1', 'game6', [{"action": "buy", "time": 10}], 50, 100
    )
    await firestore_manager.save_game_session_result(
        'user2', 'game7', [{"action": "sell", "time": 20}], 100, 150
    )
    
    await asyncio.sleep(2)  # Wait for writes to complete
    
    # Test all-time leaderboard
    print("\n=== Testing All-Time Leaderboard ===")
    print("Leaderboard for user3 (should be in top 10):")
    leaderboard = await firestore_manager.get_leaderboard('user3', top_n=3)
    for entry in leaderboard:
        print(f"  Rank {entry['rank']}: {entry['username']} - ${entry['total_profit']:.2f} {'<-- YOU' if entry['the_user'] else ''}")
    
    print("\nLeaderboard for user4 (lower ranked):")
    leaderboard = await firestore_manager.get_leaderboard('devol', top_n=3)
    print(leaderboard)
    for entry in leaderboard:
        print(f"  Rank {entry['rank']}: {entry['username']} - ${entry['total_profit']:.2f} {'<-- YOU' if entry['the_user'] else ''}")
    
    # Test weekly leaderboard
    print("\n=== Testing Weekly Leaderboard ===")
    print("Weekly leaderboard for user1:")
    weekly_leaderboard = await firestore_manager.get_weekly_leaderboard('user1', top_n=10)
    print(weekly_leaderboard)
    for entry in weekly_leaderboard:
        print(f"  Rank {entry['rank']}: {entry['username']} - ${entry['final_profit']:.2f} {'<-- YOU' if entry['the_user'] else ''}")
    
    print("\nWeekly leaderboard for user4:")
    weekly_leaderboard = await firestore_manager.get_weekly_leaderboard('user4', top_n=10)
    for entry in weekly_leaderboard:
        print(f"  Rank {entry['rank']}: {entry['username']} - ${entry['final_profit']:.2f} {'<-- YOU' if entry['the_user'] else ''}")
    
    # Cleanup
    print("\n=== Cleaning Up Test Data ===")
    await firestore_manager.delete_multiple_users(['user1', 'user2', 'user3', 'user4', 'user5'])
    print("Cleanup complete!")


if __name__ == "__main__":
    asyncio.run(main())
