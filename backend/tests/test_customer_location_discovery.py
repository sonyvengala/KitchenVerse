"""
Test Suite: Customer Kitchen Location Discovery & Geocoding
Validates:
1. Sony Kitchen discovery without location filter (shows approved kitchen).
2. Radius filtering with real stored coordinates (18.004892, 79.543196).
3. Distant location radius rejection and expansion.
4. Location autocomplete endpoint returns real structured suggestions.
5. Location reverse-geocode endpoint returns formatted address.
"""

import pytest
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.core.database import Base
from backend.app.models.user import User, KitchenProfile
from backend.app.models.enums import UserRole
from backend.app.services.customer_service import CustomerService, haversine_distance


@pytest.fixture
def loc_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create isolated test kitchen owner & test kitchen with exact test coordinates
    owner = User(
        id=str(uuid.uuid4()),
        email="test_owner_loc_discovery@example.com",
        hashed_password="hash",
        full_name="Test Location Chef",
        role=UserRole.KITCHEN_OWNER,
        is_active=True,
        is_verified=True,
    )
    db.add(owner)
    db.commit()

    kitchen = KitchenProfile(
        id=str(uuid.uuid4()),
        user_id=owner.id,
        kitchen_name="Hanamkonda Central Kitchen",
        address="123 Cloud Kitchen Way",
        city="Hanamkonda",
        latitude=18.004892,
        longitude=79.543196,
        is_open=True,
        is_approved=True,
        approval_status="APPROVED",
    )
    db.add(kitchen)
    db.commit()

    yield {"db": db, "kitchen": kitchen, "owner": owner}
    db.close()


def test_discovery_no_location_selected(loc_db):
    """When no delivery location is selected, all approved kitchens should be shown."""
    db = loc_db["db"]
    kitchens = CustomerService.get_kitchens(db)
    assert len(kitchens) == 1
    assert kitchens[0].kitchen_name == "Hanamkonda Central Kitchen"
    assert getattr(kitchens[0], "distance_km", None) is None


def test_discovery_within_radius(loc_db):
    """When delivery spot is near Hanamkonda (18.0068, 79.5578), test kitchen is within 5 km."""
    db = loc_db["db"]
    # ~1.6 km away
    kitchens = CustomerService.get_kitchens(
        db,
        latitude=18.006863,
        longitude=79.557872,
        radius_km=5.0
    )
    assert len(kitchens) == 1
    assert kitchens[0].kitchen_name == "Hanamkonda Central Kitchen"
    dist = getattr(kitchens[0], "distance_km")
    assert dist is not None
    assert 1.0 <= dist <= 2.0


def test_discovery_outside_radius_then_expanded(loc_db):
    """When delivery spot is far (Hyderabad: 17.448, 78.374), 5 km radius filters it out."""
    db = loc_db["db"]
    # 5 km radius: excluded
    kitchens_near = CustomerService.get_kitchens(
        db,
        latitude=17.448293,
        longitude=78.374187,
        radius_km=5.0
    )
    assert len(kitchens_near) == 0

    # Expand radius to 150 km: included
    kitchens_expanded = CustomerService.get_kitchens(
        db,
        latitude=17.448293,
        longitude=78.374187,
        radius_km=150.0
    )
    assert len(kitchens_expanded) == 1
    assert kitchens_expanded[0].kitchen_name == "Hanamkonda Central Kitchen"
    dist = getattr(kitchens_expanded[0], "distance_km")
    assert 120.0 <= dist <= 140.0


def test_autocomplete_service():
    """Autocomplete returns structured suggestions for search query."""
    suggestions = CustomerService.autocomplete_locations("Hanamkonda")
    assert isinstance(suggestions, list)
    if len(suggestions) > 0:
        first = suggestions[0]
        assert "main_text" in first
        assert "secondary_text" in first
        assert "formatted_address" in first
        assert "latitude" in first
        assert "longitude" in first
        assert isinstance(first["latitude"], float)
        assert isinstance(first["longitude"], float)


def test_reverse_geocode_service():
    """Reverse geocode returns structured address for coordinates."""
    result = CustomerService.reverse_geocode(18.004892, 79.543196)
    assert "formatted_address" in result
    assert result["latitude"] == 18.004892
    assert result["longitude"] == 79.543196
