# api_tools.py
import requests
from langchain_core.tools import tool

# This is the URL where your local FastAPI server is running
BASE_URL = "http://127.0.0.1:8000"
from datetime import date

@tool
def list_available_rooms() -> list | dict:
    """List rooms currently marked available, without requiring booking dates."""
    try:
        response = requests.get(f"{BASE_URL}/rooms", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the booking database API."}
    except requests.RequestException as exc:
        return {"error": str(exc)}


@tool
def check_room_availability(check_in_date:date, check_out_date:date) -> str:
    """
    Use this tool to check which rooms are currently available for booking.
    Returns a list of available rooms, their types, and nightly prices for the dates.
    """
    try:
        # Make a GET request to our FastAPI endpoint
        response = requests.get(f"{BASE_URL}/availability", params={
            "check_in": check_in_date,
            "check_out": check_out_date
        })
        response.raise_for_status() 
        
        return response.json()   
        
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to the booking database. Is the server running?"
    except Exception as e:
        return f"An error occurred while checking availability: {str(e)}"

@tool 
def get_or_create_guest(name:str,email:str, loyalty_tier:str="Classic")->dict:
    """Use this tool check if guest exists already and if not create it and return guest ID."""
    try:
        # First check if this guest already exists
        response=requests.get(f"{BASE_URL}/guests", params={"email":email})
        response.raise_for_status() # requests Python method that checks whether an HTTP request succeeded.
        
        guests=response.json()
        if guests:
            guest=guests[0]
            return {
                "id":guest["id"],
                "name":guest["name"],
                "email":guest["email"],
                "loyalty_tier":guest.get("loyalty_tier", "Classic")
                
            }
        # Otherwise create a new guest 
        create_response=requests.post(
            f"{BASE_URL}/guests",
            json={
                "name": name,
                "email": email,
                "loyalty_tier": loyalty_tier 
            }
        )
        create_response.raise_for_status()
        guest=create_response.json()
        return {
            "id":guest["id"],
            "name":guest["name"],
            "email":guest["email"],
            "loyalty_tier":guest.get("loyalty_tier", "Classic")
        }
    except Exception as exc:
        return {"error":str(exc)}
        
@tool
def find_available_room(check_in_date:date, check_out_date:date, room_type:str | None = None):
    """Find a specific available room matching the requested dates and room type."""
    try:
        response = requests.get(f"{BASE_URL}/availability", params={
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "room_type": room_type
        })
        response.raise_for_status() 
            
        return response.json()   
            
    except requests.exceptions.ConnectionError:
        return "Error: Could not connect to the booking database. Is the server running?"
    except Exception as e:
        return f"An error occurred while checking availability: {str(e)}"
@tool
def book_room(booking: dict) -> str:
    """Create a booking through the local booking API."""
    try:
        response = requests.post(f"{BASE_URL}/book", json=booking)
        if response.ok:
            result = response.json()
            return (
                f"Booking confirmed. Booking ID: {result['id']}. "
                f"Room ID: {result['room_id']}, from {result['check_in_date']} "
                f"to {result['check_out_date']}."
            )

        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        return f"Booking failed: {detail}"
    except requests.exceptions.ConnectionError:
        return "Booking failed: Could not connect to the booking database API."
    except Exception as exc:
        return f"Booking failed: {exc}"
@tool
def check_cancellation_booking(booking_id: int, guest_name: str) -> dict:
    """Verify that a booking exists and that the guest name matches."""
    try:
        response = requests.get(
            f"{BASE_URL}/bookings/{booking_id}/cancellation-check",
            params={"guest_name": guest_name},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the booking API."}
    except requests.exceptions.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = str(exc)
        return {"error": detail, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"error": str(exc)}


@tool
def create_cancellation_request(
    booking_id: int,
    guest_name: str,
    cancellation_reason: str,
) -> dict:
    """Create a pending cancellation request after guest verification."""
    try:
        response = requests.post(
            f"{BASE_URL}/cancellation-requests",
            json={
                "booking_id": booking_id,
                "guest_name": guest_name,
                "cancellation_reason": cancellation_reason,
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the booking API."}
    except requests.exceptions.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = str(exc)
        return {"error": detail, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"error": str(exc)}


@tool
def list_pending_cancellations(admin_token: str) -> list | dict:
    """List pending cancellation requests using an admin bearer token."""
    try:
        response = requests.get(
            f"{BASE_URL}/admin/cancellation-requests",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the booking API."}
    except requests.exceptions.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = str(exc)
        return {"error": detail, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"error": str(exc)}


@tool
def decide_cancellation(
    request_id: int,
    decision: str,
    admin_token: str,
    admin_note: str | None = None,
) -> dict:
    """Approve or reject a cancellation request as an authenticated admin."""
    if decision not in {"approved", "rejected"}:
        return {"error": "Decision must be 'approved' or 'rejected'."}

    try:
        response = requests.post(
            f"{BASE_URL}/admin/cancellation-requests/{request_id}/decision",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"decision": decision, "admin_note": admin_note},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to the booking API."}
    except requests.exceptions.HTTPError as exc:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = str(exc)
        return {"error": detail, "status_code": response.status_code}
    except requests.RequestException as exc:
        return {"error": str(exc)}
Menu=["burger","Fries","soda","Veg sandwich","Sugarcane juice"]


# @tool
# def room_service_agent(requirement:List[str]):
    
    
# --- Local Testing Block ---
if __name__ == "__main__":
    print("Testing API Tool (Make sure Uvicorn is running in another terminal!)...")
    print(check_room_availability.invoke(""))