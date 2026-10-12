from sqlalchemy import Column,Boolean, ForeignKey, Integer, String, Float, Date, DateTime
from database import Base
from sqlalchemy.orm import relationship
from datetime import datetime
class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    loyalty_tier = Column(String, default="Classic") # Classic, Silver, Gold, Platinum

    # Relationship to bookings
    bookings = relationship("Bookings", back_populates="guest")

class Rooms(Base):
    __tablename__ = "rooms_info"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, unique=True, index=True)
    room_type = Column(String)
    price_per_night = Column(Float)
    is_pet_friendly=Column(Boolean, default=False)
    status=Column(String, default="Available")
    # Relationship to bookings
    bookings = relationship("Bookings", back_populates="room")
    
class Bookings(Base):
    __tablename__= "bookings_info"
    
    id = Column(Integer, primary_key=True, index=True)
    guest_id = Column(Integer, ForeignKey("guests.id"))
    room_id = Column(Integer, ForeignKey("rooms_info.id"))
    check_in_date = Column(Date)
    check_out_date = Column(Date)
    special_requests = Column(String, nullable=True) #(e.g., "Late check-out," "High floor") to track the customer reservations.
    booking_status = Column(String, default="Confirmed") # Cancelled

    # Relationships back to Guest and Room
    guest = relationship("Guest", back_populates="bookings")
    room = relationship("Rooms", back_populates="bookings")
    
class Admins(Base):
    __tablename__ = "admins_info"

    id = Column(Integer, primary_key=True, index=True)
    firstname = Column(String, nullable=False)
    lastname = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

from datetime import date,datetime
class Cancellations(Base):
    __tablename__ = "cancellations"

    id = Column(Integer, primary_key=True, index=True)

    booking_id = Column(
        Integer,
        ForeignKey("bookings_info.id"),
        nullable=False,
        index=True,
    )
    guest_id = Column(
        Integer,
        ForeignKey("guests.id"),
        nullable=False,
    )
    room_id = Column(
        Integer,
        ForeignKey("rooms_info.id"),
        nullable=False,
    )

    guest_name = Column(String, nullable=False)
    cancellation_reason = Column(String, nullable=False)

    status = Column(
        String,
        default="PENDING",
        nullable=False,
    )

    requested_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    decided_at = Column(DateTime, nullable=True)

    admin_decided_by = Column(
        Integer,
        ForeignKey("admins_info.id"),
        nullable=True,
    )

    admin_note = Column(String, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)