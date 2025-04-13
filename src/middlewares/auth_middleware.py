from functools import wraps
from flask import request, jsonify

def credit_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(request, 'user', None)
        if user and user.freeCredits <= 0:
            return jsonify({"error": "You have no more credits left"}), 403
        return f(*args, **kwargs)
    return decorated