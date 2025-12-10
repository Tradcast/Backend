from storage.firestore_client import FirestoreManager
import asyncio
import time


# Comprehensive Test Suite with Cleanup
async def run_tests():
    """Run comprehensive tests for all FirestoreManager methods"""
    print("=" * 80)
    print("STARTING FIRESTORE MANAGER TESTS")
    print("=" * 80)
    
    firestore_manager = FirestoreManager()
    test_fid = "test_user_123"
    test_fid_2 = "test_user_456"
    
    # Track created users for cleanup
    created_users = [test_fid, test_fid_2]
    
    try:
        # TEST 1: Initialize User
        print("\n[TEST 1] Initializing user...")
        user_data = await firestore_manager.initiate_user(
            fid=test_fid,
            username="test_user",
            wallet="0xTEST123",
            is_banned=True
        )
        print(f"✅ User initialized successfully!")
        print(f"   - FID: {test_fid}")
        print(f"   - Username: test_user")
        print(f"   - Invitation Key: {user_data['invitation_key']}")
        print(f"   - Is Banned: True")
        
        # TEST 2: Get User
        print("\n[TEST 2] Getting user data...")
        user = await firestore_manager.get_user(test_fid)
        if user:
            print(f"✅ User retrieved successfully!")
            print(f"   - Energy: {user['energy']}")
            print(f"   - Streak Days: {user['streak_days']}")
            print(f"   - Total Games: {user['total_games']}")
        else:
            print("❌ Failed to retrieve user")
        
        # TEST 3: Update User (dynamic update)
        print("\n[TEST 3] Testing dynamic update (username + wallet)...")
        success = await firestore_manager.update_user(test_fid, {
            "username": "updated_username",
            "wallet": "0xNEW_WALLET"
        })
        if success:
            user = await firestore_manager.get_user(test_fid)
            print(f"✅ User updated successfully!")
            print(f"   - New Username: {user['username']}")
            print(f"   - New Wallet: {user['wallet']}")
        else:
            print("❌ Failed to update user")
        
        # TEST 4: Reduce Energy
        print("\n[TEST 4] Testing energy reduction...")
        before_user = await firestore_manager.get_user(test_fid)
        before_energy = before_user['energy']
        
        success = await firestore_manager.reduce_energy(test_fid)
        if success:
            after_user = await firestore_manager.get_user(test_fid)
            after_energy = after_user['energy']
            print(f"✅ Energy reduced successfully!")
            print(f"   - Before: {before_energy}")
            print(f"   - After: {after_energy}")
            print(f"   - Difference: {before_energy - after_energy}")
        else:
            print("❌ Failed to reduce energy")
        
        # TEST 5: Increment Streak Days
        print("\n[TEST 5] Testing streak days increment...")
        before_user = await firestore_manager.get_user(test_fid)
        before_streak = before_user['streak_days']
        
        success = await firestore_manager.increment_streak_days(test_fid)
        if success:
            after_user = await firestore_manager.get_user(test_fid)
            after_streak = after_user['streak_days']
            print(f"✅ Streak days incremented successfully!")
            print(f"   - Before: {before_streak}")
            print(f"   - After: {after_streak}")
        else:
            print("❌ Failed to increment streak days")
        
        # TEST 6: Reset Streak Days
        print("\n[TEST 6] Testing streak days reset...")
        success = await firestore_manager.reset_streak_days(test_fid)
        if success:
            user = await firestore_manager.get_user(test_fid)
            print(f"✅ Streak days reset successfully!")
            print(f"   - Current Streak Days: {user['streak_days']}")
        else:
            print("❌ Failed to reset streak days")
        
        # TEST 7: Update Last Online
        print("\n[TEST 7] Testing last_online update...")
        success = await firestore_manager.make_last_online_now(test_fid)
        if success:
            user = await firestore_manager.get_user(test_fid)
            print(f"✅ Last online updated successfully!")
            print(f"   - Last Online: {user['last_online']}")
        else:
            print("❌ Failed to update last online")
        
        # TEST 8: Add Total Game
        print("\n[TEST 8] Testing total games increment...")
        before_user = await firestore_manager.get_user(test_fid)
        before_games = before_user['total_games']
        
        success = await firestore_manager.add_total_game(test_fid)
        if success:
            after_user = await firestore_manager.get_user(test_fid)
            after_games = after_user['total_games']
            print(f"✅ Total games incremented successfully!")
            print(f"   - Before: {before_games}")
            print(f"   - After: {after_games}")
        else:
            print("❌ Failed to increment total games")
        
        # TEST 9: Add Game Session
        print("\n[TEST 9] Testing add game session...")
        trade_env_id = "trade_env_001"
        actions = [
            {"action": "buy", "time": 10},
            {"action": "sell", "time": 25},
            {"action": "buy", "time": 40}
        ]
        
        success = await firestore_manager.add_game_session(test_fid, trade_env_id, actions)
        if success:
            print(f"✅ Game session added successfully!")
            print(f"   - Trade Env ID: {trade_env_id}")
            print(f"   - Actions Count: {len(actions)}")
        else:
            print("❌ Failed to add game session")
        
        # TEST 10: Get Game Sessions
        print("\n[TEST 10] Testing get game sessions...")
        sessions = await firestore_manager.get_game_sessions(test_fid)
        if sessions is not None:
            print(f"✅ Game sessions retrieved successfully!")
            print(f"   - Total Sessions: {len(sessions)}")
            print(f"   - Session IDs: {sessions}")
        else:
            print("❌ Failed to get game sessions")
        
        # TEST 11: Get Trade Decisions
        print("\n[TEST 11] Testing get trade decisions...")
        decisions = await firestore_manager.get_trade_decisions(trade_env_id)
        if decisions:
            print(f"✅ Trade decisions retrieved successfully!")
            print(f"   - Trade Env ID: {decisions['trade_env_id']}")
            print(f"   - Actions: {decisions['actions']}")
        else:
            print("❌ Failed to get trade decisions")
        
        # TEST 12: Add Multiple Game Sessions
        print("\n[TEST 12] Testing multiple game sessions...")
        for i in range(2, 4):
            trade_id = f"trade_env_00{i}"
            test_actions = [{"action": "buy", "time": i * 10}]
            success = await firestore_manager.add_game_session(test_fid, trade_id, test_actions)
            if success:
                await firestore_manager.add_total_game(test_fid)
        
        sessions = await firestore_manager.get_game_sessions(test_fid)
        user = await firestore_manager.get_user(test_fid)
        print(f"✅ Multiple game sessions added!")
        print(f"   - Total Sessions in Array: {len(sessions)}")
        print(f"   - Total Games Counter: {user['total_games']}")
        
        # TEST 13: Update Multiple Fields at Once
        print("\n[TEST 13] Testing bulk field update...")
        success = await firestore_manager.update_user(test_fid, {
            "total_profit": 1500,
            "total_PnL": 250,
            "invited_key": "ABC12"
        })
        if success:
            user = await firestore_manager.get_user(test_fid)
            print(f"✅ Multiple fields updated successfully!")
            print(f"   - Total Profit: {user['total_profit']}")
            print(f"   - Total PnL: {user['total_PnL']}")
            print(f"   - Invited Key: {user['invited_key']}")
        else:
            print("❌ Failed to update multiple fields")
        
        # TEST 14: Test Unique Invitation Keys
        print("\n[TEST 14] Testing unique invitation keys...")
        user_data_2 = await firestore_manager.initiate_user(
            fid=test_fid_2,
            username="test_user_2",
            is_banned=False
        )
        user_1 = await firestore_manager.get_user(test_fid)
        user_2 = await firestore_manager.get_user(test_fid_2)
        
        if user_1['invitation_key'] != user_2['invitation_key']:
            print(f"✅ Invitation keys are unique!")
            print(f"   - User 1 Key: {user_1['invitation_key']}")
            print(f"   - User 2 Key: {user_2['invitation_key']}")
        else:
            print("❌ Invitation keys are not unique (collision detected)")
        
        # TEST 15: Final User State
        print("\n[TEST 15] Final user state check...")
        final_user = await firestore_manager.get_user(test_fid)
        print(f"✅ Final user state:")
        print(f"   - Username: {final_user['username']}")
        print(f"   - Wallet: {final_user['wallet']}")
        print(f"   - Total Games: {final_user['total_games']}")
        print(f"   - Energy: {final_user['energy']}")
        print(f"   - Streak Days: {final_user['streak_days']}")
        print(f"   - Total Profit: {final_user['total_profit']}")
        print(f"   - Total PnL: {final_user['total_PnL']}")
        print(f"   - Invitation Key: {final_user['invitation_key']}")
        print(f"   - Invited Key: {final_user['invited_key']}")
        print(f"   - Is Banned: {final_user['is_banned']}")
        
        print("\n" + "=" * 80)
        print("ALL TESTS COMPLETED SUCCESSFULLY! ✅")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # CLEANUP: Delete all test users
        print("\n" + "=" * 80)
        print("CLEANING UP TEST DATA...")
        print("=" * 80)
        
        cleanup_results = await firestore_manager.delete_multiple_users(created_users)
        
        for fid, success in cleanup_results.items():
            if success:
                print(f"✅ Deleted user: {fid}")
            else:
                print(f"❌ Failed to delete user: {fid}")
        
        print("🧹 Cleanup completed!")


# Concurrent Test for Single User
async def concurrent_test_single_user():
    """Test concurrent operations on a single user (stress test)"""
    print("\n" + "=" * 80)
    print("CONCURRENT TEST - SINGLE USER (5 CONCURRENT OPERATIONS)")
    print("=" * 80)
    
    firestore_manager = FirestoreManager()
    test_fid = "concurrent_test_user"
    
    try:
        # Initialize user first
        await firestore_manager.initiate_user(
            fid=test_fid,
            username="concurrent_user",
            wallet="0xCONCURRENT"
        )
        
        print("\n[Starting 5 concurrent operations on same user...]")
        
        # Run 5 operations concurrently on the same user
        tasks = [
            firestore_manager.reduce_energy(test_fid),
            firestore_manager.increment_streak_days(test_fid),
            firestore_manager.add_total_game(test_fid),
            firestore_manager.make_last_online_now(test_fid),
            firestore_manager.update_user(test_fid, {"total_profit": 100})
        ]
        
        results = await asyncio.gather(*tasks)
        
        if all(results):
            print("✅ All 5 concurrent operations completed successfully!")
        else:
            print(f"⚠️  Some operations failed: {results}")
        
        # Check final state
        user = await firestore_manager.get_user(test_fid)
        print(f"\nFinal state after concurrent operations:")
        print(f"   - Energy: {user['energy']} (should be 9)")
        print(f"   - Streak Days: {user['streak_days']} (should be 2)")
        print(f"   - Total Games: {user['total_games']} (should be 1)")
        print(f"   - Total Profit: {user['total_profit']} (should be 100)")
    
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up {test_fid}...")
        await firestore_manager.delete_user(test_fid)
        print("✅ Cleanup completed!")


# Concurrent Test for Multiple Users
async def concurrent_test_multiple_users(num_users: int = 5):
    """Test concurrent user creation and operations"""
    print("\n" + "=" * 80)
    print(f"CONCURRENT TEST - {num_users} USERS (PARALLEL OPERATIONS)")
    print("=" * 80)
    
    firestore_manager = FirestoreManager()
    created_fids = []
    
    print(f"\n[Creating {num_users} users concurrently...]")
    
    try:
        # Create multiple users concurrently
        async def create_and_test_user(user_id: int):
            fid = f"concurrent_user_{user_id}_{int(time.time())}"
            created_fids.append(fid)
            
            # Initialize user
            user_data = await firestore_manager.initiate_user(
                fid=fid,
                username=f"user_{user_id}",
                wallet=f"0xWALLET_{user_id}"
            )
            
            # Perform operations
            await firestore_manager.reduce_energy(fid)
            await firestore_manager.add_total_game(fid)
            await firestore_manager.increment_streak_days(fid)
            
            # Add game session
            trade_env_id = f"trade_env_user_{user_id}_{int(time.time())}"
            actions = [
                {"action": "buy", "time": user_id * 10},
                {"action": "sell", "time": user_id * 20}
            ]
            await firestore_manager.add_game_session(fid, trade_env_id, actions)
            
            # Get final state
            final_user = await firestore_manager.get_user(fid)
            
            return {
                "fid": fid,
                "invitation_key": user_data["invitation_key"],
                "energy": final_user["energy"],
                "total_games": final_user["total_games"],
                "streak_days": final_user["streak_days"]
            }
        
        # Run all user creations and operations concurrently
        tasks = [create_and_test_user(i) for i in range(1, num_users + 1)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check results
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = [r for r in results if isinstance(r, Exception)]
        
        print(f"\n✅ Successfully created and tested {len(successful)}/{num_users} users")
        if failed:
            print(f"❌ Failed operations: {len(failed)}")
            for err in failed:
                print(f"   Error: {err}")
        
        # Verify unique invitation keys
        invitation_keys = [r["invitation_key"] for r in successful]
        unique_keys = set(invitation_keys)
        
        if len(unique_keys) == len(invitation_keys):
            print(f"✅ All {len(invitation_keys)} invitation keys are unique!")
        else:
            print(f"❌ Key collision detected! {len(invitation_keys)} keys, {len(unique_keys)} unique")
        
        # Display sample results
        print(f"\nSample user states:")
        for result in successful[:3]:
            print(f"   - {result['fid']}: Energy={result['energy']}, "
                  f"Games={result['total_games']}, Streak={result['streak_days']}, "
                  f"Key={result['invitation_key']}")
    
    finally:
        # Cleanup all created users
        print(f"\n🧹 Cleaning up {len(created_fids)} test users...")
        cleanup_results = await firestore_manager.delete_multiple_users(created_fids)
        successful_deletes = sum(1 for success in cleanup_results.values() if success)
        print(f"✅ Deleted {successful_deletes}/{len(created_fids)} users")


# Heavy Load Test
async def heavy_load_test():
    """Test heavy concurrent load with multiple operations"""
    print("\n" + "=" * 80)
    print("HEAVY LOAD TEST - 10 USERS WITH MULTIPLE OPERATIONS EACH")
    print("=" * 80)
    
    firestore_manager = FirestoreManager()
    num_users = 10
    created_fids = []
    
    print(f"\n[Creating {num_users} users with 5 operations each = {num_users * 5} total operations...]")
    
    try:
        async def user_workflow(user_id: int):
            fid = f"load_test_user_{user_id}_{int(time.time())}"
            created_fids.append(fid)
            
            try:
                # 1. Create user
                await firestore_manager.initiate_user(
                    fid=fid,
                    username=f"load_user_{user_id}",
                    wallet=f"0xLOAD_{user_id}"
                )
                
                # 2-6. Multiple concurrent operations per user
                operations = [
                    firestore_manager.reduce_energy(fid),
                    firestore_manager.reduce_energy(fid),
                    firestore_manager.add_total_game(fid),
                    firestore_manager.increment_streak_days(fid),
                    firestore_manager.update_user(fid, {"total_profit": user_id * 100})
                ]
                
                await asyncio.gather(*operations)
                
                # 7. Add game sessions
                for session_num in range(2):
                    trade_id = f"trade_{user_id}_{session_num}_{int(time.time())}"
                    actions = [{"action": "buy", "time": session_num * 10}]
                    await firestore_manager.add_game_session(fid, trade_id, actions)
                
                # Get final state
                user = await firestore_manager.get_user(fid)
                sessions = await firestore_manager.get_game_sessions(fid)
                
                return {
                    "fid": fid,
                    "success": True,
                    "energy": user["energy"],
                    "total_games": user["total_games"],
                    "streak_days": user["streak_days"],
                    "sessions_count": len(sessions),
                    "total_profit": user["total_profit"]
                }
                
            except Exception as e:
                return {
                    "fid": fid,
                    "success": False,
                    "error": str(e)
                }
        
        # Run all workflows concurrently
        start_time = time.time()
        
        tasks = [user_workflow(i) for i in range(1, num_users + 1)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Analyze results
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        print(f"\n{'='*80}")
        print(f"RESULTS:")
        print(f"{'='*80}")
        print(f"✅ Successful: {len(successful)}/{num_users}")
        print(f"❌ Failed: {len(failed)}/{num_users}")
        print(f"⏱️  Total time: {duration:.2f} seconds")
        print(f"📊 Operations per second: {(num_users * 7) / duration:.2f}")
        
        if failed:
            print(f"\nFailed operations:")
            for fail in failed:
                print(f"   - {fail['fid']}: {fail['error']}")
        
        if successful:
            print(f"\nSample successful results:")
            for result in successful[:5]:
                print(f"   - {result['fid']}: Energy={result['energy']}, "
                      f"Games={result['total_games']}, Streak={result['streak_days']}, "
                      f"Sessions={result['sessions_count']}, Profit={result['total_profit']}")
    
    finally:
        # Cleanup all created users
        print(f"\n🧹 Cleaning up {len(created_fids)} test users...")
        cleanup_results = await firestore_manager.delete_multiple_users(created_fids)
        successful_deletes = sum(1 for success in cleanup_results.values() if success)
        print(f"✅ Deleted {successful_deletes}/{len(created_fids)} users")


# Master Test Runner
async def run_all_tests():
    """Run all test suites"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "FIRESTORE MANAGER TEST SUITE" + " "*30 + "║")
    print("╚" + "="*78 + "╝")
    
    # Run sequential comprehensive test
    await run_tests()
    
    # Run concurrent tests
    await concurrent_test_single_user()
    await concurrent_test_multiple_users(num_users=5)
    await concurrent_test_multiple_users(num_users=10)
    await heavy_load_test()
    
    print("\n" + "="*80)
    print("🎉 ALL TEST SUITES COMPLETED!")
    print("="*80)


# Run tests
if __name__ == '__main__':
    import asyncio
    
    asyncio.run(run_all_tests())

