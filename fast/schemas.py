# fastapi/schemas.py
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional
from datetime import date, datetime

# --- Guest Schemas ---
class GuestBase(BaseModel):
    name: str
    email: EmailStr

class GuestCreate(GuestBase):
    loyalty_tier: Optional[str] = "Classic"

class GuestResponse(GuestBase):
    id: int
    loyalty_tier: str
    
    # This allows Pydantic to read data directly from SQLAlchemy objects
    model_config = ConfigDict(from_attributes=True)


# --- Room Schemas ---
class RoomBase(BaseModel):
    room_number: str
    room_type: str
    price_per_night: float
    is_pet_friendly: bool = False
    
class RoomCreate(RoomBase):
    status: Optional[str] = "Available"

class RoomResponse(RoomBase):
    id: int
    status: str

    model_config = ConfigDict(from_attributes=True)


# --- Booking Schemas ---
class BookingBase(BaseModel):
    check_in_date: date
    check_out_date: date
    special_requests: Optional[str] = None

class BookingCreate(BookingBase):
    guest_id: int
    room_id: int

class BookingResponse(BookingBase):
    id: int
    guest_id: int
    room_id: int
    booking_status: str

    model_config = ConfigDict(from_attributes=True)
class BookingVerificationResponse(BaseModel):
    booking_id: int
    guest_id: int
    guest_name: str
    room_id: int
    check_in_date: date
    check_out_date: date
    booking_status: str
    can_cancel: bool
#______ Admin ___
class AdminBase(BaseModel):
    firstname:str
    lastname:str
   

class AdminCreate(AdminBase):
    email: EmailStr
    password: str = Field(min_length=5)

class AdminResponse(AdminBase):
    id:int
    firstname:str
    lastname:str
    email: EmailStr
    role: str
    created_at: datetime

class CancellationCreate(BaseModel):
    booking_id: int
    guest_name: str
    cancellation_reason: str
    
    model_config = ConfigDict(from_attributes=True)

class CancellationRequestResponse(BaseModel):
    id: int
    booking_id: int
    guest_id: int
    room_id: int
    guest_name: str
    cancellation_reason: str
    status: str
    requested_at: datetime
    decided_at: Optional[datetime] = None
    admin_decided_by: Optional[int] = None
    admin_note: Optional[str] = None
    cancelled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
class CancellationDecision(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    admin_note: Optional[str] = None
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginRequest(BaseModel):
    email: EmailStr
    password: str