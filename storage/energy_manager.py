import asyncio
from datetime import datetime
from typing import List, Dict, Any


class EnergyManager:
    def __init__(self, firestore_manager):
        """
        Initialize Energy Manager
        
        Args:
            firestore_manager: Instance of FirestoreManager
        """
        self.fm = firestore_manager
        self.max_energy = 10
        self.energy_increment = 1
    
    async def reenergize_user(self, fid: str) -> bool:
        """
        Re-energize a single user if energy < max_energy
        
        Args:
            fid: User's FID
            
        Returns:
            True if user was re-energized, False otherwise
        """
        try:
            user = await self.fm.get_user(fid)
            if not user:
                return False
            
            current_energy = user.get("energy", 0)
            
            # Only re-energize if below max
            if current_energy < self.max_energy:
                new_energy = min(current_energy + self.energy_increment, self.max_energy)
                await self.fm.update_user(fid, {"energy": new_energy})
                print(f"Re-energized {fid}: {current_energy} -> {new_energy}")
                return True
            
            return False
            
        except Exception as e:
            print(f"Error re-energizing user {fid}: {e}")
            return False
    
    async def reenergize_all_users(self) -> Dict[str, Any]:
        """
        Re-energize all users who have energy < max_energy
        
        Returns:
            Dictionary with stats about re-energization
        """
        try:
            # Query users with energy < max_energy
            query = self.fm.db.collection(self.fm.users_collection).where(
                "energy", "<", self.max_energy
            )
            docs = await query.get()
            
            stats = {
                "timestamp": datetime.now().isoformat(),
                "total_users_checked": len(docs),
                "users_reenergized": 0,
                "errors": 0
            }
            
            # Re-energize each user concurrently
            tasks = []
            for doc in docs:
                fid = doc.id
                tasks.append(self.reenergize_user(fid))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successes and errors
            for result in results:
                if isinstance(result, Exception):
                    stats["errors"] += 1
                elif result:
                    stats["users_reenergized"] += 1
            
            print(f"Re-energization complete: {stats}")
            return stats
            
        except Exception as e:
            print(f"Error in reenergize_all_users: {e}")
            return {"error": str(e)}
    
    def _get_next_quarter_hour(self) -> int:
        """
        Calculate seconds until next quarter hour (0, 15, 30, or 45 minutes)
        
        Returns:
            Number of seconds to wait
        """
        now = datetime.now()
        current_minute = now.minute
        current_second = now.second
        
        # Find next quarter hour
        quarter_hours = [0, 15, 30, 45]
        next_quarter = None
        
        for quarter in quarter_hours:
            if current_minute < quarter:
                next_quarter = quarter
                break
        
        # If no quarter found in current hour, next is 0 of next hour
        if next_quarter is None:
            minutes_to_wait = 60 - current_minute
            seconds_to_wait = minutes_to_wait * 60 - current_second
        else:
            minutes_to_wait = next_quarter - current_minute
            seconds_to_wait = minutes_to_wait * 60 - current_second
        
        return seconds_to_wait
    
    async def start_reenergization_loop(self):
        """
        Start infinite loop that re-energizes users at 0, 15, 30, and 45 minutes of each hour
        """
        print("Starting re-energization loop (every quarter hour: :00, :15, :30, :45)...")
        
        while True:
            try:
                # Wait until next quarter hour
                wait_seconds = self._get_next_quarter_hour()
                next_time = datetime.now()
                next_time = next_time.replace(second=0, microsecond=0)
                next_minute = (next_time.minute // 15 + 1) * 15
                if next_minute == 60:
                    next_minute = 0
                
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Waiting {wait_seconds} seconds until next cycle...")
                await asyncio.sleep(wait_seconds)
                
                # Run re-energization
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running re-energization cycle...")
                await self.reenergize_all_users()
                
            except Exception as e:
                print(f"Error in re-energization loop: {e}")
                # Wait a bit before retrying to avoid rapid failures
                await asyncio.sleep(60)


# Usage example
async def main():

    from firestore_client import FirestoreManager
    
    # Initialize managers
    firestore_manager = FirestoreManager()
    energy_manager = EnergyManager(firestore_manager)
    
    # Option 1: Run once
    print("Running single re-energization cycle:")
    #await energy_manager.reenergize_all_users()
    
    # Option 2: Start infinite loop (for production)
    await energy_manager.start_reenergization_loop()


# For running as a standalone script
if __name__ == "__main__":
    asyncio.run(main())
