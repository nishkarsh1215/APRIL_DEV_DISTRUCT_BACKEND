import os
import jwt
import requests
from datetime import datetime, timedelta, timezone
from flask import current_app, url_for, render_template

def render_email_template(template_name, **context):
    """Render email template with Jinja2."""
    return render_template(f"emails/{template_name}", **context)


def generate_email_verification_token(user_id):
    """Generate a short-lived token (1 hour) for email verification."""
    payload = {
        'exp': datetime.now(timezone.utc) + timedelta(hours=1),
        'iat': datetime.now(timezone.utc),
        'sub': str(user_id),
        'purpose': 'emailVerification'
    }
    secret = current_app.config.get('JWT_SECRET')
    return jwt.encode(payload, str(secret), algorithm='HS256')

def send_verification_email(user):
    """Send an email with a verification link using Resend."""
    token = generate_email_verification_token(user.id)
    FRONTEND_URL = current_app.config.get("FRONTEND_URL", "https://devdistruct.com")
    verify_url = f"{FRONTEND_URL}/auth/verify/{token}"
    
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    if not RESEND_API_KEY:
        current_app.logger.warning("Missing RESEND_API_KEY env variable")

     # Render HTML and text versions
    html_content = render_email_template(
        "verify_email.html",
        verification_link=verify_url,
        physical_address="India",
        company_name="Dev Distruct",
        logo_url="https://firebasestorage.googleapis.com/v0/b/startek-45163.appspot.com/o/devdistruct_logo-removebg-preview.png?alt=media&token=c2f2dfbd-968c-4933-a5a2-9c1ec5abcd1c",
        company_tagline="Dev Distruct is an AI-powered SaaS tool where images transform into functional websites",
        privacy_policy="https://devdistruct.com/",
        unsubscribe_link="https://devdistruct.com/",
        twitter_url="https://devdistruct.com/",
        linkedin_url="https://devdistruct.com/",
        github_url="https://devdistruct.com/"
    )

    text_content = render_email_template(
        "verify_email.txt",
        verification_link=verify_url,
        company_name="Dev Distruct",
        privacy_policy="https://devdistruct.com/",
        unsubscribe_link="https://devdistruct.com/"
    )

    # ...send email with requests.post
    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": "onboarding@pawandai.tech",
            "to": [user.email],
            "subject": "Verify Your Email - Dev Distruct",
            "html": html_content,
            "text": text_content
        }
    )

def send_password_reset_email(user_email, token):
    """Send password reset email"""
    reset_url = url_for('auth_reset_password', token=token, _external=True)

    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    if not RESEND_API_KEY:
        current_app.logger.warning("Missing RESEND_API_KEY env variable")

    # Render HTML and text versions
    html_content = render_email_template(
        "reset_password.html",
        reset_link=reset_url,
        company_name="Dev Distruct",
        logo_url="https://firebasestorage.googleapis.com/v0/b/startek-45163.appspot.com/o/devdistruct_logo-removebg-preview.png?alt=media&token=c2f2dfbd-968c-4933-a5a2-9c1ec5abcd1c",
        company_tagline="Dev Distruct is an AI-powered SaaS tool where images transform into functional websites",
        support_url="https://devdistruct.com/"
    )
    
    text_content = render_email_template(
        "reset_password.txt",
        reset_link=reset_url,
        company_name="Dev Distruct",
        support_url="https://devdistruct.com/"
    )

    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": "onboarding@pawandai.tech",
            "to": [user_email],
            "subject": "Reset Password - Dev Distruct",
            "html": html_content,
            "text": text_content
        }
    )

def send_user_feedback(user_email, feedback_body):
    """
    Send feedback from a user to the developers/maintainers via Resend.
    """
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    if not RESEND_API_KEY:
        current_app.logger.warning("Missing RESEND_API_KEY env variable")

    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        json={
            "from": "onboarding@pawandai.tech",
            "to": ["paw1awasthi@gmail.com"],
            "subject": "User Feedback",
            "html": f"<p>{feedback_body} email: {user_email}</p>",
            "text": feedback_body + " email: " + user_email
        }
    )
