from fastapi import FastAPI,status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from astrapy import DataAPIClient 
from model import User, Login, Payment, Appointment,Upcoming,Prescription1,RewardPoint,AppointmentRequest, ContactForm
from utility import hashedpassword,verifyhash,send_test_email,mainhtml,generate_otp
import httpx
import uuid

app = FastAPI()

load_dotenv()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return JSONResponse(content={"message":"welcome to demohealthcare api!"})






# Initialize the client
Api_key= os.getenv("DB_KEY")
client = DataAPIClient(Api_key)
db = client.get_database_by_api_endpoint(
  "https://0a0c8492-98e6-4b38-a074-fac244e3aab8-us-east-2.apps.astra.datastax.com"
)

user_collection = db.create_collection("users")
appointment_collection = db.create_collection("appointments")
payment_collection = db.create_collection("payments")
new_appointment_collection = db.create_collection("new_appointment")

print(f"Connected to Astra DB: {db.list_collection_names()}")


@app.post("/register")
async def register(user: User):
    data = dict(user)
    print(data)
    data["password"] = hashedpassword(data['password'])
    user_id = user_collection.insert_one(data).inserted_id
    if user_id:
        return JSONResponse(content={"message":"user registered successfully","user_id":user_id}, status_code=status.HTTP_201_CREATED)

@app.post("/contact")
async def contact_us(form: ContactForm):
    # This will send an email using the established send_test_email using resend
    # The receiver will be the admin (in testing this needs to be the confirmed address)
    admin_email = "inyanggodstime63@gmail.com" 
    subject = f"New Contact Request from {form.name}"
    body = f"<b>Name:</b> {form.name}<br><b>Email:</b> {form.email}<br><br><b>Message:</b><br>{form.message}"
    success = send_test_email(admin_email, subject, body)
    if success:
        return JSONResponse(content={"message": "email sent successfully"}, status_code=status.HTTP_200_OK)
    else:
        return JSONResponse(content={"message": "failed to send email"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@app.post("/login")
async def login(login: Login):
    data = dict(login)
    print(data)
    # Correct filter: {"email": data["email"]} instead of {data["email"]}
    user = user_collection.find_one({"email": data["email"]})
    
    if user and verifyhash(user["password"], data["password"]):
        otp = generate_otp()
        send_test_email(data["email"], "Verify Your Email", f"Your OTP is {otp}")
        # Correct filter here too
        user_collection.update_one({"email": data["email"]}, {"$set": {"otp": otp}})
        return JSONResponse(content={"message": "user logged in successfully", "user_id": str(user["_id"])}, status_code=status.HTTP_200_OK)
    else:
        return JSONResponse(content={"message": "invalid email or password"}, status_code=status.HTTP_401_UNAUTHORIZED)



@app.post("/verify")
async def verify(token: str):
    data = user_collection.find_one({"_id": token})
    if data:
        user_collection.update_one({"_id": token},{"$set":{"verified":True}})
        return JSONResponse(content={"message":"user verified successfully"}, status_code=status.HTTP_200_OK)
    else:
        return JSONResponse(content={"message":"user not found"}, status_code=status.HTTP_404_NOT_FOUND)


@app.post("/verify_otp")
async def verify_otp(user: dict):
    print(f"Verifying OTP for user: {user.get('_id')}")
    main_user = user_collection.find_one({"_id": user["_id"]})
    
    if main_user and str(main_user.get("otp")) == str(user.get("otp")):
        # Success: Clear the OTP and return OK
        user_collection.update_one({"_id": user["_id"]}, {"$set": {"otp": ""}})
        return JSONResponse(content={"message": "user otp verified successfully"}, status_code=status.HTTP_200_OK)
    else:
        # Failure: Either user not found or OTP mismatch
        return JSONResponse(content={"message": "invalid verification code"}, status_code=status.HTTP_400_BAD_REQUEST)

@app.get("/active_users")
def active_users():
    count = user_collection.count_documents({"is_active":True})
    return JSONResponse(content={"message":"users count sucessfully","total active users":count},status_code=status.HTTP_200_OK)



@app.delete("/delete")
async def delete(email:str):
    user = user_collection.find_one({"email":email})
    if user:
        user_collection.delete_many({"email":email},{"$set":{"is_active":False}})
        return JSONResponse(content={"message":"user deleted sucessfully"},status_code=status.HTTP_200_OK)
    else:
        return JSONResponse(content={"message":"user not found"},status_code=status.HTTP_404_NOT_FOUND)



@app.post("/Paymentgateway")
async def paymentgateway(payment_data: Payment):
    print("DEBUG: Starting PaymentGateway...")
    try:
        # 1. Verify user exists in Astra DB (by ID or Email)
        print(f"DEBUG: Looking up user by ID: {payment_data.user_id} or Email: {payment_data.email}")
        user = None
        if payment_data.user_id:
            user = user_collection.find_one({"_id": payment_data.user_id})
        
        if not user:
            user = user_collection.find_one({"email": payment_data.email})

        if not user:
            print("DEBUG: User not found in DB.")
            return JSONResponse(content={"message": "User not found. Please register before making a payment."}, status_code=status.HTTP_404_NOT_FOUND)

        user_id = user["_id"]
        user_email = user["email"]
        print(f"DEBUG: User found: {user_email}. Creating pending payment record...")

        # 2. Call Flutterwave to initialize payment
        flw_secret_key = os.getenv("FLW_SECRET_KEY")
        flw_url = "https://api.flutterwave.com/v3/payments"
        
        headers = {
            "Authorization": f"Bearer {flw_secret_key}",
            "Content-Type": "application/json"
        }

        tx_ref = f"tx-{uuid.uuid4()}"
        
        # Store the pending payment in the database
        payment_collection.insert_one({
            "user_id": user_id,
            "email": user_email,
            "amount": payment_data.amount,
            "tx_ref": tx_ref,
            "status": "pending",
            "full_name": payment_data.full_name,
            "address": payment_data.address
        })
        print(f"DEBUG: Pending record created. Calling Flutterwave API...")

        payload = {
            "tx_ref": tx_ref,
            "amount": payment_data.amount,
            "currency": "USD", # Adjust based on your currency
            "redirect_url": f"http://localhost:5173/payment-success?user_id={user_id}&email={user_email}", 
            "customer": {
                "email": user_email,
                "name": payment_data.full_name,
                "address": payment_data.address
            },
            "customizations": {
                "title": "HealthCare Payment",
                "description": "Payment for healthcare services"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(flw_url, json=payload, headers=headers)
        
        data = response.json()
        print(f"DEBUG: Flutterwave Response Status: {response.status_code}")
        
        if response.status_code == 200 and data.get("status") == "success":
            payment_collection.update_one(
                {"tx_ref": tx_ref},
                {"$set": {"payment_url": data["data"]["link"]}}
            )
            print("DEBUG: Payment link generated successfully!")
            return JSONResponse(content={"payment_url": data["data"]["link"]}, status_code=status.HTTP_200_OK)
        else:
            print(f"DEBUG: Flutterwave Error: {data}")
            return JSONResponse(content={"message": data.get("message", "Payment initiation failed"), "details": data}, status_code=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"DEBUG: Exception in PaymentGateway: {str(e)}")
        return JSONResponse(content={"message": f"Internal gateway error: {str(e)}"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@app.get("/verify-payment")
async def verify_payment(transaction_id: str, user_id: str):
    print(f"DEBUG: Starting verification for TID: {transaction_id}, User: {user_id}")
    try:
        flw_secret_key = os.getenv("FLW_SECRET_KEY")
        verify_url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
        
        headers = {
            "Authorization": f"Bearer {flw_secret_key}"
        }

        print(f"DEBUG: Calling Flutterwave API: {verify_url}")
        async with httpx.AsyncClient() as client:
            response = await client.get(verify_url, headers=headers)
        
        data = response.json()
        print(f"DEBUG: Flutterwave Response: {data.get('status')}")
        
        if response.status_code == 200 and data.get("status") == "success":
            print(f"DEBUG: Payment successful. Updating collections...")
            # 1. Update user profile to set payment status
            user_collection.update_one(
                {"_id": user_id},
                {"$set": {"payment": True, "last_transaction_id": transaction_id}}
            )
            print(f"DEBUG: User collection updated.")
            
            # 2. Update the specific payment record in the payments collection
            # We use email or ID to find the pending payment
            payment_collection.update_one(
                {"user_id": user_id, "status": "pending"},
                {"$set": {"status": "success", "transaction_id": transaction_id}}
            )
            print(f"DEBUG: Payment collection updated to Success.")
            
            return JSONResponse(content={"message": "Payment verified and updated successfully"}, status_code=status.HTTP_200_OK)
        else:
            print(f"DEBUG: Transaction failed verification: {data.get('message')}")
            return JSONResponse(content={"message": "Transaction verification failed"}, status_code=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"DEBUG: Error during verification: {str(e)}")
        return JSONResponse(content={"message": f"Verification error: {str(e)}"}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@app.post("/appointment")
async def register_appointment(appointment: Appointment):
    data = dict(appointment)
    data["status"] = "Pending" # Default status
    print(data)
    appointment_id = appointment_collection.insert_one(data).inserted_id
    if appointment_id:
        return JSONResponse(content={"message":"appointment booked successfully","appointment_id":str(appointment_id)},status_code=status.HTTP_201_CREATED)
    else:
        return JSONResponse(content={"message":"appointment booking failed"},status_code=status.HTTP_400_BAD_REQUEST)

@app.post("/total_appointment")
async def total_appointment(request: AppointmentRequest):
    user_id = request.user_id

    main_user = user_collection.find_one({"_id": user_id})

    if not main_user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)

    new_total = main_user.get("total_appointment", 0) + 1

    user_collection.update_one(
        {"_id": user_id},
        {"$set": {"total_appointment": new_total}}
    )

    return JSONResponse(content={
        "message": "updated successfully",
        "total_appointment": new_total
    }, status_code=status.HTTP_200_OK)


@app.post("/upcoming_test")
async def upcoming_test(request: Upcoming):
    user_id = request.user_id
    appointment_id = request.appointment_id

    main_user = user_collection.find_one({"_id": user_id})

    if not main_user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)

    # update appointment record
    appointment_collection.update_one(
        {"_id": appointment_id},
        {"$set": {"status": "upcoming"}}
    )

    new_total = main_user.get("upcoming_test", 0) + 1

    user_collection.update_one(
        {"_id": user_id},
        {"$set": {"upcoming_test": new_total}}
    )

    return JSONResponse(content={
        "message": "updated successfully",
        "upcoming_test": new_total
    }, status_code=status.HTTP_200_OK)


@app.post("/prescription")
async def prescription_endpoint(request: Prescription1):
    user_id = request.user_id
    appointment_id = request.appointment_id

    main_user = user_collection.find_one({"_id": user_id})

    if not main_user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)

    # store prescription in appointment record
    appointment_collection.update_one(
        {"_id": appointment_id},
        {"$set": {"prescription": request.prescription}}
    )

    new_total = main_user.get("prescription", 0) + 1

    user_collection.update_one(
        {"_id": user_id},
        {"$set": {"prescription": new_total}}
    )

    return JSONResponse(content={
        "message": "prescription saved successfully",
        "prescription": new_total
    }, status_code=status.HTTP_200_OK)


@app.post("/reward_point")
async def reward_point_endpoint(request: RewardPoint):
    user_id = request.user_id

    main_user = user_collection.find_one({"_id": user_id})

    if not main_user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)

    new_count = main_user.get("reward_point", 0) + request.reward_point

    user_collection.update_one(
        {"_id": user_id},
        {"$set": {"reward_point": new_count}}
    )

    return JSONResponse(content={
        "message": "updated successfully",
        "reward_point": new_count
    }, status_code=status.HTTP_200_OK)


@app.post("/new_appointment")
async def new_appointment(request: AppointmentRequest):
    user_id = request.user_id

    main_user = user_collection.find_one({"_id": user_id})

    if not main_user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)

    new_total = main_user.get("new_appointment", 0) + 1

    user_collection.update_one(
        {"_id": user_id},
        {"$set": {"new_appointment": new_total}}
    )

    return JSONResponse(content={
        "message": "updated successfully",
        "new_appointment": new_total
    }, status_code=status.HTTP_200_OK)


@app.get("/dashboard_data/{user_id}")
async def get_dashboard_data(user_id: str):
    user = user_collection.find_one({"_id": user_id})
    if not user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)
        
    email = user.get("email")
    
    # fetch appointments by email
    appointments_cursor = appointment_collection.find({"email": email})
    appointments = list(appointments_cursor)
    
    formatted_appointments = []
    confirmed_count = 0
    pending_count = 0
    
    for apt in appointments:
        apt_status = apt.get("status", "Pending")
        # In case you have different statuses, just bucket them or exact match
        if apt_status.lower() == "confirmed":
            confirmed_count += 1
        else:
            pending_count += 1
            
        formatted_appointments.append({
            "id": str(apt.get("_id", "")),
            "doctor": apt.get("name", "Doctor"),
            "department": apt.get("type", "General"),
            "date": apt.get("date", ""),
            "time": apt.get("time", ""),
            "status": apt_status
        })
        
    stats = {
        "total_appointments": user.get("total_appointment", 0),
        "upcoming_tests": user.get("upcoming_test", 0),
        "prescriptions": user.get("prescription", 0),
        "reward_points": user.get("reward_point", 0),
        "new_appointments": user.get("new_appointment", 0),
        "confirmed_appointments": confirmed_count,
        "pending_appointments": pending_count,
    }
    
    return JSONResponse(content={"stats": stats, "appointments": formatted_appointments}, status_code=status.HTTP_200_OK)



@app.post("/logout")
async def logout(request: AppointmentRequest):
    user_id = request.user_id
    print("Logging out user_id:", user_id)
    # the user is found using _id, not email since frontend only supplies user_id
    user = user_collection.find_one({"_id": user_id})
    if not user:
        return JSONResponse(content={"message": "user not found"}, status_code=status.HTTP_404_NOT_FOUND)
    user_collection.update_one({"_id": user_id},{"$set":{"is_logged_in":False}})
    return JSONResponse(content={"message": "user logged out successfully"}, status_code=status.HTTP_200_OK)