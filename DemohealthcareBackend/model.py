from pydantic import BaseModel,EmailStr
from typing import Optional

class User(BaseModel):
    username:str
    email:EmailStr
    password:str
    message: Optional[str] = None
    friends: list[str] = []
    city: str
    state: str
    country: str
    zipcode: str
    date_of_birth: str
    gender: str
    address: str
    phone_number: str
    profile_picture:Optional[str] = None


class Login(BaseModel):
    email:EmailStr
    password:str


class Payment(BaseModel):
    user_id: Optional[str] = None
    amount: int
    full_name: str
    email: EmailStr
    address: str

class Appointment(BaseModel):
    name: str
    email: EmailStr
    phone: str
    date: str
    time: str
    type: str
    description: Optional[str] = None


class AppointmentRequest(BaseModel):
    user_id: str

class Upcoming(BaseModel):
    user_id: str
    appointment_id: str

class Prescription1(BaseModel):
    user_id: str
    appointment_id: str
    prescription: str


class RewardPoint(BaseModel):
    user_id: str
    reward_point: int

class ContactForm(BaseModel):
    name: str
    email: EmailStr
    message: str