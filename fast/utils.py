# fastapi/utils.py
from database import engine, SessionLocal, Base
from models import Rooms, Guest, Bookings
from datetime import date, timedelta

def seed_database():
    # 1. Create all tables defined in models.py
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # 2. Prevent duplicate seeding if the script is run twice
    if db.query(Rooms).first():
        print("Database is already seeded!")
        db.close()
        return

    # 3. Create Dummy Novotel Rooms
    rooms = [
        Rooms(room_number="101", room_type="Standard", price_per_night=120.0, is_pet_friendly=True, status="Available"),
        Rooms(room_number="310", room_type="Standard", price_per_night=120.0, is_pet_friendly=False, status="Available"),
        Rooms(room_number="111", room_type="Family Room", price_per_night=120.0, is_pet_friendly=False, status="Available"),
        Rooms(room_number="102", room_type="Standard", price_per_night=120.0, is_pet_friendly=False, status="Available"),
        Rooms(room_number="201", room_type="Executive Suite", price_per_night=350.0, is_pet_friendly=False, status="Available"),
        Rooms(room_number="301", room_type="Family Room", price_per_night=250.0, is_pet_friendly=True, status="Occupied")
    ]
    db.add_all(rooms)
    db.commit() # Commit to generate IDs

    # 4. Create a Dummy Guest
    guest = Guest(name="Sarah Connor", email="sarah.connor@example.com", loyalty_tier="Gold")
    guest1 = Guest(name="Sam Carrie", email="sam.carrie@example.com", loyalty_tier="Platinum")
    guest2 = Guest(name="Raja Kutti", email="raja.kutti@example.com", loyalty_tier="Classic")
    db.add(guest)
    db.add(guest1)
    db.add(guest2)
    db.commit()

    # 5. Create a Dummy Booking
    # Sarah is booking the Family Room (which is why it's marked "Occupied" above)
    booking = Bookings(
        guest_id=guest.id,
        room_id=rooms[5].id, # Links to Room 301
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=2),
        special_requests="Late check-out requested.",
        booking_status="Confirmed"
    )
    db.add(booking)
    db.commit()
    
    print("Success! Database seeded with dummy Novotel inventory and guests.")
    db.close()

if __name__ == "__main__":
    seed_database()