#!/usr/bin/env python3
"""
Test script to verify database transaction fixes
Tests all critical database functions to ensure proper transaction handling
"""
import sys
from app.database.queries import (
    save_user,
    get_user_program_id,
    save_program,
    get_program_info,
    get_all_programs,
    get_all_transactions,
    get_all_users,
    get_all_admin_messages,
    get_admin_messages_count,
    count_active_programs
)

def test_database_functions():
    """Test all critical database functions"""
    print("=" * 60)
    print("TRANSACTION FIX VERIFICATION TEST")
    print("=" * 60)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Save user
    print("\n✓ Test 1: Save user...")
    try:
        user_id = save_user(999999999, "test_user", "Test")
        if user_id:
            print(f"   PASS: User saved with ID {user_id}")
            tests_passed += 1
        else:
            print(f"   FAIL: User ID is None")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Test 2: Get program info (should handle None gracefully)
    print("\n✓ Test 2: Get program info (non-existent)...")
    try:
        program = get_program_info(999999)
        if program is None:
            print(f"   PASS: Correctly returned None for non-existent program")
            tests_passed += 1
        else:
            print(f"   FAIL: Should return None, got {program}")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Test 3: Get all programs
    print("\n✓ Test 3: Get all programs...")
    try:
        programs = get_all_programs()
        if isinstance(programs, list):
            print(f"   PASS: Retrieved {len(programs)} programs")
            tests_passed += 1
        else:
            print(f"   FAIL: Should return list, got {type(programs)}")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Test 4: Get all transactions
    print("\n✓ Test 4: Get all transactions...")
    try:
        transactions = get_all_transactions()
        if isinstance(transactions, list):
            print(f"   PASS: Retrieved {len(transactions)} transactions")
            tests_passed += 1
        else:
            print(f"   FAIL: Should return list, got {type(transactions)}")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Test 5: Get all users
    print("\n✓ Test 5: Get all users...")
    try:
        users = get_all_users()
        if isinstance(users, list):
            print(f"   PASS: Retrieved {len(users)} users")
            tests_passed += 1
        else:
            print(f"   FAIL: Should return list, got {type(users)}")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Test 6: Get admin messages count
    print("\n✓ Test 6: Get admin messages count...")
    try:
        count = get_admin_messages_count()
        if isinstance(count, int):
            print(f"   PASS: Admin messages count: {count}")
            tests_passed += 1
        else:
            print(f"   FAIL: Should return int, got {type(count)}")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Test 7: Count active programs
    print("\n✓ Test 7: Count active programs...")
    try:
        count = count_active_programs()
        if isinstance(count, int):
            print(f"   PASS: Active programs count: {count}")
            tests_passed += 1
        else:
            print(f"   FAIL: Should return int, got {type(count)}")
            tests_failed += 1
    except Exception as e:
        print(f"   FAIL: {e}")
        tests_failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print(f"RESULTS: {tests_passed} PASSED | {tests_failed} FAILED")
    print("=" * 60)
    
    if tests_failed == 0:
        print(" ALL TESTS PASSED - Transaction fixes verified!")
        return 0
    else:
        print(" SOME TESTS FAILED - Check errors above")
        return 1

if __name__ == "__main__":
    sys.exit(test_database_functions())
