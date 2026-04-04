from argon2 import PasswordHasher
from dotenv import load_dotenv
import secrets
from htmlmessage import mainhtml
import os
import resend




ph = PasswordHasher()
def hashedpassword(password):
    hashed = ph.hash(password)
    return hashed

def verifyhash(hashedpassword,password):
    value = ph.verify(hashedpassword,password)
    return value




load_dotenv()





# Load the API key from your .env
resend.api_key = os.getenv("RESEND_API_KEY")
def send_test_email(receiver_email, subject, body):
    # 'onboarding@resend.dev' is a special test address they give you
    # Note: With this test address, you can only send emails to YOUR OWN email address (the one you used to sign up for Resend).
    params = {
        "from": "Acme <onboarding@resend.dev>",
        "to": [receiver_email],
        "subject": subject,
        "html": f"<p>{body}</p>",  # You can also use "text": body
    }
    try:
        email = resend.Emails.send(params)
        print("Email sent successfully!", email)
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def generate_otp():
    """ Generate a secure 6 digit code....."""
    return str(secrets.randbelow(1000000)).zfill(6)
