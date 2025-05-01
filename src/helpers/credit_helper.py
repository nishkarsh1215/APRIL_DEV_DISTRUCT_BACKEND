import datetime
from infra.db.models import RefreshTracker, User

def check_and_refresh_credits():
    """
    Check if it's time to refresh user credits (first day of the month).
    If so, refresh all users' credits based on their plan.
    
    This function should be called on any endpoint access.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today = now.date()
    
    # Get or create the refresh tracker
    tracker = RefreshTracker.objects.first()
    if not tracker:
        tracker = RefreshTracker()
        tracker.save()
    
    # If we have a last refresh date and it's in the current month, no refresh needed
    if tracker.last_refresh_date:
        last_refresh = tracker.last_refresh_date
        if last_refresh.year == today.year and last_refresh.month == today.month:
            return False  # Already refreshed this month
    
    # Check if it's the first day of the month or if we've never refreshed before
    if today.day == 1 or not tracker.last_refresh_date:
        # Find all users and reset their credits based on plan
        users = User.objects()
        refresh_count = 0
        
        for user in users:
            if user.plan == "free":
                user.freeCredits = 1000000
            elif user.plan == "Basic":
                user.freeCredits = 10000000
            elif user.plan == "Pro":
                user.freeCredits = 25000000
            elif user.plan == "Ultimate":
                user.freeCredits = 75000000
            
            user.save()
            refresh_count += 1
        
        # Update the last refresh date
        tracker.last_refresh_date = today
        tracker.save()
        
        print(f"Refreshed credits for {refresh_count} users at {now}")
        return True
    
    return False
