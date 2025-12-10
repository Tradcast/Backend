from google.cloud import firestore
from google.cloud.firestore_v1.async_client import AsyncClient
from datetime import datetime
import string, time, asyncio, random
from typing import Optional, Dict, Any, List
from configs.config import firestore_project_name


class FirestoreManager:
    def __init__(self):
        """Initialize async Firestore client"""
        self.db: AsyncClient = firestore.AsyncClient(project=firestore_project_name)

        self.users_collection = "users"
        self.game_sessions_collection = "game_sessions"
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
        
        # Also initialize empty game_sessions array for this user
        await self.db.collection(self.game_sessions_collection).document(fid).set({
            "game_sessions": []
        })
        
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
            # 1. Add game_session to the user's game_sessions array
            game_sessions_ref = self.db.collection(self.game_sessions_collection).document(fid)
            await game_sessions_ref.update({
                "game_sessions": firestore.ArrayUnion([trade_env_id])
            })
            
            # 2. Create the trade_decisions document
            trade_decisions_data = {
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
        Get all game session IDs for a user
        
        Args:
            fid: User's FID
            
        Returns:
            List of game session IDs or None
        """
        doc_ref = self.db.collection(self.game_sessions_collection).document(fid)
        doc = await doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            return data.get("game_sessions", [])
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

            # 3. Delete the game_sessions document
            await self.db.collection(self.game_sessions_collection).document(fid).delete()

            # 4. Delete the user document
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
            # 1. Add game session to user's session array
            game_sessions_ref = self.db.collection(self.game_sessions_collection).document(fid)
            await game_sessions_ref.update({
                "game_sessions": firestore.ArrayUnion([trade_env_id])
            })

            # 2. Save trade decisions
            trade_decisions_data = {
                "trade_env_id": trade_env_id,
                "actions": actions,
                "final_pnl": final_pnl,
                "final_profit": final_profit,
                "created_at": firestore.SERVER_TIMESTAMP
            }
            await self.db.collection(self.trade_decisions_collection).document(trade_env_id).set(
                trade_decisions_data
            )

            # 3. Update user totals
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


async def main():
    firestore_manager = FirestoreManager()
    await firestore_manager.initiate_user('123123')
    await firestore_manager.initiate_user('123124')
    await firestore_manager.delete_user('123123')
    await asyncio.sleep(1)      

if __name__ == "__main__":
    asyncio.run(main())
