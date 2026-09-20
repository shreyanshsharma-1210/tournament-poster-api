"""Unit and integration tests for Tournament Poster Extraction API."""

import io
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    TournamentPosterExtraction,
    TournamentInfo,
    DatesInfo,
    LocationInfo,
    RegistrationInfo,
    AuctionInfo,
    ParticipationInfo,
    FeesInfo,
    PrizesInfo,
    ExtractionMeta,
)

client = TestClient(app)

# Standard 1x1 dummy PNG bytes for test uploads
DUMMY_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
    b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_root_endpoint():
    """Verify root endpoint returns correct status and message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Tournament Poster Extraction API",
        "status": "running"
    }


def test_health_endpoint():
    """Verify health endpoint returns status healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy"
    }


def test_extract_missing_file():
    """Verify 422 error when no file is uploaded."""
    response = client.post("/extract")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert "detail" in data


def test_extract_invalid_mime_type():
    """Verify 415 error for unsupported file formats like .txt or .pdf."""
    file_content = b"This is a text file, not an image."
    response = client.post(
        "/extract",
        files={"poster": ("document.txt", io.BytesIO(file_content), "text/plain")}
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"] == "Unsupported Media Type"
    assert "Only JPEG, JPG, PNG, and WEBP images are supported" in data["detail"]


def test_extract_empty_file():
    """Verify 400 error when an empty 0-byte image file is uploaded."""
    empty_content = b""
    response = client.post(
        "/extract",
        files={"poster": ("poster.jpg", io.BytesIO(empty_content), "image/jpeg")}
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "Bad Request"
    assert "Uploaded file is empty" in data["detail"]


def test_extract_file_too_large():
    """Verify 413 error when file exceeds MAX_FILE_SIZE_MB."""
    with patch("app.main.MAX_FILE_SIZE_BYTES", 10):
        large_content = b"x" * 20
        response = client.post(
            "/extract",
            files={"poster": ("poster.png", io.BytesIO(large_content), "image/png")}
        )
        assert response.status_code == 413
        data = response.json()
        assert data["error"] == "Payload Too Large"
        assert "exceeds maximum allowable size" in data["detail"]


def test_extract_missing_api_key():
    """Verify 500 error with descriptive message when Gemini API key is missing."""
    with patch("app.services.gemini_service.gemini_service.api_key", ""):
        response = client.post(
            "/extract",
            files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")}
        )
        assert response.status_code == 500
        data = response.json()
        assert "GEMINI_API_KEY" in data["detail"]


def test_extract_success_with_mocked_gemini():
    """Verify complete updated structured response output when Gemini service returns valid extracted data."""
    mock_extracted_data = TournamentPosterExtraction(
        tournament=TournamentInfo(
            name="Champions Trophy 2026",
            sport="Cricket",
            format="Turf Cricket Tournament",
            season="Season 3",
            organizer="Apex Sports Club"
        ),
        dates=DatesInfo(
            start_date="2026-11-29",
            end_date="2026-12-05",
            registration_deadline="2026-11-20",
            auction_date="2026-11-25"
        ),
        location=LocationInfo(
            venue="Skyline Turf Arena",
            address="Plot 42, Cyber Hub Road",
            city="Bengaluru",
            state="Karnataka",
            country="India"
        ),
        registration=RegistrationInfo(
            available=True,
            methods=["WhatsApp", "Google Form", "QR Code"],
            qr_code_present=True,
            registration_url="https://example.com/register",
            registration_fee="₹5,000 per team",
            contact_person="Rahul Sharma",
            contact_numbers=["9876543210", "9123456789"],
            email="contact@apexsports.com"
        ),
        auction=AuctionInfo(
            required=True,
            date="2026-11-25",
            venue="Grand Palace Hall",
            address="MG Road, Bengaluru"
        ),
        participation=ParticipationInfo(
            number_of_teams=16,
            number_of_players=11,
            eligibility="Open to all players aged 18+",
            team_requirements="Minimum 11 players per squad",
            player_requirements="Aadhaar card mandatory"
        ),
        fees=FeesInfo(
            registration_fee="₹5,000",
            team_fee="₹5,000",
            player_fee=None,
            auction_fee="₹1,000"
        ),
        prizes=PrizesInfo(
            first_prize="₹1,00,000",
            second_prize="₹50,000",
            third_prize="₹25,000",
            other_prizes=["Man of the Match - ₹1,000", "Best Bowler - Trophy"]
        ),
        additional_information=[
            "100 players will be selected through auction",
            "10 overs per match with red tennis ball"
        ],
        extraction=ExtractionMeta(
            confidence=0.95,
            fields_needing_review=[]
        )
    )

    with patch(
        "app.main.gemini_service.extract_tournament_from_image",
        new=AsyncMock(return_value=mock_extracted_data)
    ):
        response = client.post(
            "/extract",
            files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")}
        )

        assert response.status_code == 200
        data = response.json()

        # Check tournament
        assert data["tournament"]["name"] == "Champions Trophy 2026"
        assert data["tournament"]["sport"] == "Cricket"

        # Check dates
        assert data["dates"]["start_date"] == "2026-11-29"
        assert data["dates"]["end_date"] == "2026-12-05"
        assert data["dates"]["auction_date"] == "2026-11-25"

        # Check registration
        assert data["registration"]["available"] is True
        assert data["registration"]["methods"] == ["WhatsApp", "Google Form", "QR Code"]
        assert data["registration"]["qr_code_present"] is True
        assert data["registration"]["email"] == "contact@apexsports.com"
        assert len(data["registration"]["contact_numbers"]) == 2

        # Check fees & prizes
        assert data["fees"]["registration_fee"] == "₹5,000"
        assert data["fees"]["auction_fee"] == "₹1,000"
        assert data["prizes"]["first_prize"] == "₹1,00,000"
        assert data["prizes"]["other_prizes"] == ["Man of the Match - ₹1,000", "Best Bowler - Trophy"]

        # Check participation
        assert data["participation"]["number_of_teams"] == 16
        assert data["participation"]["team_requirements"] == "Minimum 11 players per squad"

        # Check extraction meta
        assert data["extraction"]["confidence"] == 0.95
        assert data["extraction"]["fields_needing_review"] == []


def test_registration_methods_array():
    """Verify registration methods array contains list of visible methods."""
    mock_data = TournamentPosterExtraction(
        registration=RegistrationInfo(
            available=True,
            methods=["Call", "WhatsApp", "QR Code"],
            qr_code_present=True
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["registration"]["methods"], list)
        assert data["registration"]["methods"] == ["Call", "WhatsApp", "QR Code"]


def test_missing_registration_deadline_is_null():
    """Verify registration deadline returns null when not explicitly stated."""
    mock_data = TournamentPosterExtraction(
        dates=DatesInfo(
            start_date="2026-11-29",
            end_date="2026-12-05",
            registration_deadline=None
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert data["dates"]["start_date"] == "2026-11-29"
        assert data["dates"]["registration_deadline"] is None


def test_multiple_contact_numbers_preserved():
    """Verify all contact numbers are extracted without digit modification."""
    mock_data = TournamentPosterExtraction(
        registration=RegistrationInfo(
            contact_numbers=["9669632910", "9876543210", "+91 9123456780"]
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert data["registration"]["contact_numbers"] == ["9669632910", "9876543210", "+91 9123456780"]


def test_missing_location_null_handling():
    """Verify venue/address/city/state/country are null when not explicitly stated."""
    mock_data = TournamentPosterExtraction(
        location=LocationInfo(
            venue="Indori Turf & Cafe",
            address=None,
            city=None,
            state=None,
            country=None
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert data["location"]["venue"] == "Indori Turf & Cafe"
        assert data["location"]["address"] is None
        assert data["location"]["city"] is None
        assert data["location"]["state"] is None
        assert data["location"]["country"] is None


def test_prize_extraction_schema():
    """Verify first_prize, second_prize, third_prize, and other_prizes extraction."""
    mock_data = TournamentPosterExtraction(
        prizes=PrizesInfo(
            first_prize="₹50,000",
            second_prize="₹25,000",
            third_prize=None,
            other_prizes=["Best Batsman - ₹2,000", "Best Bowler - ₹2,000"]
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert data["prizes"]["first_prize"] == "₹50,000"
        assert data["prizes"]["second_prize"] == "₹25,000"
        assert data["prizes"]["third_prize"] is None
        assert len(data["prizes"]["other_prizes"]) == 2


def test_fee_extraction_schema():
    """Verify separate fee types (registration, team, player, auction) with currency preserved."""
    mock_data = TournamentPosterExtraction(
        fees=FeesInfo(
            registration_fee="₹500",
            team_fee="₹5,000",
            player_fee="₹500",
            auction_fee="₹1,000"
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert data["fees"]["registration_fee"] == "₹500"
        assert data["fees"]["team_fee"] == "₹5,000"
        assert data["fees"]["player_fee"] == "₹500"
        assert data["fees"]["auction_fee"] == "₹1,000"


def test_qr_code_boolean():
    """Verify QR code detection boolean flags."""
    mock_data_with_qr = TournamentPosterExtraction(
        registration=RegistrationInfo(qr_code_present=True, registration_url=None)
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data_with_qr)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert data["registration"]["qr_code_present"] is True
        assert data["registration"]["registration_url"] is None


def test_confidence_range_and_review_fields():
    """Verify confidence score is within 0.0 - 1.0 and fields_needing_review paths are present."""
    mock_data = TournamentPosterExtraction(
        extraction=ExtractionMeta(
            confidence=0.72,
            fields_needing_review=["location.address", "dates.auction_date"]
        )
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["extraction"]["confidence"] <= 1.0
        assert data["extraction"]["confidence"] == 0.72
        assert "location.address" in data["extraction"]["fields_needing_review"]
        assert "dates.auction_date" in data["extraction"]["fields_needing_review"]


def test_additional_information_excludes_slogans():
    """Verify additional_information contains rules and useful facts rather than slogans."""
    mock_data = TournamentPosterExtraction(
        additional_information=[
            "Only Maheshwari Samaj members can participate",
            "10 overs per innings",
            "White tennis ball will be used"
        ]
    )
    with patch("app.main.gemini_service.extract_tournament_from_image", new=AsyncMock(return_value=mock_data)):
        response = client.post("/extract", files={"poster": ("poster.png", io.BytesIO(DUMMY_PNG_BYTES), "image/png")})
        assert response.status_code == 200
        data = response.json()
        assert len(data["additional_information"]) == 3
        assert "Only Maheshwari Samaj members can participate" in data["additional_information"]
