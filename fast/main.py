# fastapi/main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List

from database import Base, engine, get_db
import models
import schemas

# Create tables added to the SQLAlchemy models without removing existing data.
Base.metadata.create_all(bind=engine)

# Initialize the FastAPI app
app = FastAPI(
    title="Novotel Booking API", 
    description="Backend API for the Novotel Conversational AI Agent"
)
@app.post("/roomsnew", response_model=schemas.RoomResponse)
def create_room(room:schemas.RoomCreate,db:Session=Depends(get_db)):
    existing=db.query(models.Rooms).filter(models.Rooms.room_number==room.room_number).first()
    if existing:
        return {"Room number already exists can't create this."}
    new_room=models.Rooms(
        room_number=room.room_number,
        room_type=room.room_type,
        price_per_night=room.price_per_night,
        is_pet_friendly=room.is_pet_friendly,
        status=room.status
    )
    db.add(new_room)
    db.commit()
    db.refresh(new_room)
    return new_room
# --- Endpoints ---
# TO check all available rooms
@app.get("/rooms", response_model=List[schemas.RoomResponse])
def get_availability(db: Session = Depends(get_db)):
    """
    Fetches all rooms that are currently marked as 'Available'.
    The AI will use this to answer questions like 'Do you have any rooms open?'
    """
    rooms = db.query(models.Rooms).filter(models.Rooms.status == "Available").all()
    return rooms

# Check rooms available for a certain period of time
from datetime import date
@app.get("/availability", response_model=List[schemas.RoomResponse])
def check_availability(check_in: date, check_out: date, db: Session = Depends(get_db)):
    booked_room_ids = db.query(models.Bookings.room_id).filter(
        models.Bookings.booking_status.in_(["Occupied","Confirmed"]),
        models.Bookings.check_in_date < check_out,
        models.Bookings.check_out_date > check_in
    ).subquery()

    rooms = db.query(models.Rooms).filter(
        models.Rooms.status == "Available",
        ~models.Rooms.id.in_(db.query(booked_room_ids.c.room_id))
    ).all()

    return rooms




# GET ALL GUESTS, if email is given get guest with email
@app.get("/guests", response_model=List[schemas.GuestResponse])
def get_guests(email:str | None = None, db:Session=Depends(get_db)):
    query=db.query(models.Guest)
    if email:
        query=query.filter(models.Guest.email==email)
    return query.all()

# CHECK FOR EXISTING GUEST OR CREATE NEW GUEST
@app.post("/guests", response_model=schemas.GuestResponse)
def create_guest(guest:schemas.GuestCreate, db:Session=Depends(get_db)):
    existing=db.query(models.Guest).filter(models.Guest.email==guest.email).first()
    if existing:
        return existing
    new_guest=models.Guest(
        name=guest.name,
        email=guest.email,
        loyalty_tier=guest.loyalty_tier
    )
    db.add(new_guest)
    db.commit()
    db.refresh(new_guest)
    return new_guest

@app.get("/availability/room", response_model=schemas.RoomResponse)
def find_available_room(check_in_date: date, check_out_date: date, room_type: str | None = None, db: Session = Depends(get_db)):
    # exclude rooms with overlapping bookings
    booked_room_ids=db.query(models.Bookings.room_id).filter(
        models.Bookings.booking_status == "Confirmed",
        models.Bookings.check_in_date < check_out_date,
        models.Bookings.check_out_date > check_in_date
    ).subquery()
    
    query = db.query(models.Rooms)
    if room_type:
        query = query.filter(models.Rooms.room_type == room_type)
    
    room = query.filter(models.Rooms.id.notin_(db.query(booked_room_ids.c.room_id))).first()
    if not room:
        raise HTTPException(status_code=404, detail="No available rooms for the requested dates.")
    return room

@app.post("/book", response_model=schemas.BookingResponse)
def create_booking(booking: schemas.BookingCreate, db: Session = Depends(get_db)):
    """
    Creates a new booking and changes the room status to 'Occupied'.
    The AI will send a strict JSON payload here after validating the user's dates.
    """
    # 1. Verify the room actually exists
    room = db.query(models.Rooms).filter(models.Rooms.id == booking.room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found.")
    
    # 2. Verify the room isn't already booked
    #if room.status != "Available":
        #raise HTTPException(status_code=400, detail="Room is currently occupied or under maintenance.")
    existing_booking = db.query(models.Bookings).filter(
    models.Bookings.room_id == booking.room_id,
    models.Bookings.booking_status.in_(["Confirmed", "Occupied"]),
    models.Bookings.check_in_date < booking.check_out_date,
    models.Bookings.check_out_date > booking.check_in_date
    ).first()

    if existing_booking:
        raise HTTPException(
            status_code=400,
            detail="Room is already booked for the requested dates."
        )
    # 3. Create the booking record
    new_booking = models.Bookings(
        guest_id=booking.guest_id,
        room_id=booking.room_id,
        check_in_date=booking.check_in_date,
        check_out_date=booking.check_out_date,
        special_requests=booking.special_requests,
        booking_status="Confirmed"
    )
    
    # 4. Mark the room as occupied
    #room.status = "Occupied"
    
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    return new_booking

from auth import (
    create_access_token, get_current_admin, hash_password, verify_password
)

@app.post("/admins", response_model=schemas.AdminResponse)

def create_admin(admin:schemas.AdminCreate, db:Session=Depends(get_db)):
    existing=db.query(models.Admins).filter(
        models.Admins.email == admin.email
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Admins email already exists."
        )
    new_admin=models.Admins(
        firstname=admin.firstname,
        lastname=admin.lastname,
        email=admin.email,
        password_hash=hash_password(admin.password),
        role="admin",
    )
    
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    
    return new_admin

@app.post("/auth/login", response_model=schemas.TokenResponse)

def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    admin=db.query(models.Admins).filter(
        models.Admins.email == credentials.username
    ).first()
    if not admin or not verify_password(credentials.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    
    token = create_access_token(admin)
    return {
        "access_token":token,
        "token_type":"bearer"
    }


@app.get("/bookings/{booking_id}/cancellation-check",response_model=schemas.BookingVerificationResponse)

def checking_booking_for_cancellation(booking_id:int, guest_name:str,db:Session=Depends(get_db)):
    booking=db.query(models.Bookings).join(models.Guest,models.Bookings.guest_id==models.Guest.id).filter(models.Bookings.id==booking_id).first()
    
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking was not found.")
    if booking.guest.name.casefold()!=guest_name.strip().casefold():
        raise HTTPException(
            status_code=403,
            detail="Guest name does not match the booking"
        )
    can_cancel = booking.booking_status == "Confirmed"

    return {
        "booking_id": booking.id,
        "guest_id": booking.guest_id,
        "guest_name": booking.guest.name,
        "room_id": booking.room_id,
        "check_in_date": booking.check_in_date,
        "check_out_date": booking.check_out_date,
        "booking_status": booking.booking_status,
        "can_cancel": can_cancel,
    }

@app.post("/cancellation-requests", response_model=schemas.CancellationRequestResponse)
def create_cancellation_request(request:schemas.CancellationCreate, db:Session=Depends(get_db)):
    booking=db.query(models.Bookings).join(
        models.Guest,
        models.Bookings.guest_id == models.Guest.id,
    ).filter(models.Bookings.id==request.booking_id).first()
    
    if booking is None:
        raise HTTPException(status_code=404,detail="Booking was not found.")
    if booking.guest.name.casefold()!=request.guest_name.strip().casefold():
        raise HTTPException(
            status_code=403,
            detail="Guest name does not match the booking."
        )
    if booking.booking_status!= "Confirmed":
        raise HTTPException(
            status_code=400,
            detail="Only confimed bookings can be cancelled."
        )
    pending_request=models.Cancellations(
        booking_id=booking.id,
        guest_id=booking.guest_id,
        room_id=booking.room_id,
        guest_name=booking.guest.name,
        cancellation_reason=request.cancellation_reason,
        status="PENDING"
    )
    db.add(pending_request)
    db.commit()
    db.refresh(pending_request)
    
    return pending_request

@app.get(
    "/admin/cancellation-requests",
    response_model=list[schemas.CancellationRequestResponse]
)
def list_pending_cancellations(
    admin: models.Admins = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return (
        db.query(models.Cancellations)
        .filter(models.Cancellations.status == "PENDING")
        .order_by(models.Cancellations.requested_at.asc())
        .all()
    )
    
from datetime import datetime   
@app.post(
    "/admin/cancellation-requests/{request_id}/decision",
    response_model=schemas.CancellationRequestResponse,
)
def decide_cancellation(
    request_id: int,
    decision: schemas.CancellationDecision,
    admin: models.Admins = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    cancellation = (
        db.query(models.Cancellations)
        .filter(models.Cancellations.id == request_id)
        .with_for_update()
        .first()
    )

    if cancellation is None:
        raise HTTPException(
            status_code=404,
            detail="Cancellation request was not found.",
        )

    if cancellation.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="This cancellation request was already decided.",
        )

    cancellation.admin_decided_by = admin.id
    cancellation.admin_note = decision.admin_note
    cancellation.decided_at = datetime.utcnow()

    if decision.decision == "rejected":
        cancellation.status = "REJECTED"
        db.commit()
        db.refresh(cancellation)
        return cancellation

    booking = (
        db.query(models.Bookings)
        .filter(models.Bookings.id == cancellation.booking_id)
        .with_for_update()
        .first()
    )

    if booking is None:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Booking was not found.",
        )

    if booking.booking_status != "Confirmed":
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Booking is no longer cancellable.",
        )

    booking.booking_status = "Cancelled"

    cancellation.status = "APPROVED"
    cancellation.cancelled_at = datetime.utcnow()

    db.commit()
    db.refresh(cancellation)

    return cancellation

import os
import sys
from fastapi import FastAPI
from chainlit.utils import mount_chainlit

# 1. Calculate the exact path to the project root folder (one level up from /fast)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Add both root and fast/ to Python's import path so no imports fail
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

app = FastAPI()

# --- Keep your existing FastAPI routes here ---
@app.get("/api/status")
def get_status():
    return {"status": "FastAPI backend is running"}

# 3. Point Chainlit to the exact absolute location of app.py at the root URL ("/")
CHAINLIT_TARGET = os.path.join(ROOT_DIR, "app.py")
mount_chainlit(app=app, target=CHAINLIT_TARGET, path="/")
