from argon2 import PasswordHasher
from dotenv import load_dotenv
import secrets
from htmlmessage import mainhtml
import os
import resend
from jose import jwt,JWTError
from datetime import datetime, timedelta





ph = PasswordHasher()
def hashedpassword(password):
    hashed = ph.hash(password)
    return hashed

def verifyhash(hashedpassword,password):
    value = ph.verify(hashedpassword,password)
    return value




load_dotenv()


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30

def access_token(data: dict, minutes: int = 5):
    payload = data.copy()
    payload["exp"]  = datetime.utcnow() + timedelta(minutes=minutes)

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def refresh_token(data: dict, minutes: int = 60):
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=minutes)

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
 
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
