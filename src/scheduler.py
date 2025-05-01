import datetime
from infra.db.models import User

def refresh_user_credits():
    """
    Reset user credits based on their plan. This function should be called monthly.
    """
    # Find all users that need credit refresh
    users = User.objects()
    
    # Set credits based on plan
    for user in users:
        if user.plan == "free":
            user.freeCredits = 1000000
        elif user.plan == "Basic":
            user.freeCredits = 10000000
        elif user.plan == "Pro":
            user.freeCredits = 25000000
        elif user.plan == "Ultimate":
            user.freeCredits = 75000000
        
        # Save the updated user
        user.save()
    
    print(f"Refreshed credits for {len(users)} users at {datetime.datetime.now()}")
    return len(users)

if __name__ == "__main__":
    # This allows running the script directly for testing or manual refresh
    refresh_user_credits()
