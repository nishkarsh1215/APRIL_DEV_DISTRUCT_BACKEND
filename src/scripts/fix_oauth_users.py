#!/usr/bin/env python3
"""
Script to verify user accounts and fix issues with missing passwords.
"""
import sys
import os
import bcrypt

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.db.db_config import init_db
from infra.db.models import User

def check_users():
    """Check and report on user account status"""
    print("Initializing database connection...")
    init_db()
    
    # Get all users
    all_users = User.objects()
    
    # Statistics
    total_users = len(all_users)
    oauth_users = 0
    password_users = 0
    missing_password = 0
    
    print(f"\nFound {total_users} users in database")
    
    for user in all_users:
        if user.provider in ['github', 'google']:
            oauth_users += 1
            
            # OAuth users might be missing passwords
            if not user.password:
                missing_password += 1
                print(f"- OAuth user missing password: {user.email} (provider: {user.provider})")
        else:
            password_users += 1
            if not user.password:
                missing_password += 1
                print(f"- Email user missing password: {user.email}")
    
    print(f"\nUser Account Stats:")
    print(f"- Total users: {total_users}")
    print(f"- OAuth users: {oauth_users}")
    print(f"- Password users: {password_users}")
    print(f"- Users missing passwords: {missing_password}")
    
    # Ask to fix missing passwords
    if missing_password > 0:
        fix = input("\nDo you want to add placeholder passwords to OAuth users? (y/n): ")
        if fix.lower() == 'y':
            fix_missing_passwords()

def fix_missing_passwords():
    """Add placeholder passwords to OAuth users missing passwords"""
    # Find all OAuth users without passwords
    users_to_fix = User.objects(provider__in=['github', 'google'], password=None)
    
    fixed_count = 0
    for user in users_to_fix:
        # Generate a random secure password they can't use (30 chars)
        import secrets
        import string
        random_pw = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(30))
        hashed_pw = bcrypt.hashpw(random_pw.encode('utf-8'), bcrypt.gensalt())
        
        # Update user with the password
        user.update(password=hashed_pw.decode('utf-8'))
        fixed_count += 1
        print(f"Fixed user: {user.email}")
    
    print(f"\nFixed {fixed_count} users with missing passwords")
    
if __name__ == "__main__":
    check_users()
