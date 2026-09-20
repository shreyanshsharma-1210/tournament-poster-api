"""Data models and schemas for Tournament Poster Extraction API."""

from pydantic import BaseModel, Field


class TournamentInfo(BaseModel):
    """Information about the tournament itself."""

    name: str | None = Field(
        default=None,
        description="Full official name of the tournament as stated on the poster.",
    )
    sport: str | None = Field(
        default=None,
        description="Normalized sport name (e.g. Cricket, Football, Basketball, Badminton, Volleyball).",
    )
    format: str | None = Field(
        default=None,
        description="Tournament format description (e.g. Turf Cricket Tournament, Football League, T20 Cricket, 5-a-side).",
    )
    season: str | None = Field(
        default=None, description="Season or edition (e.g. Season 1, 2026 Edition)."
    )
    organizer: str | None = Field(
        default=None,
        description="Name of the organizing committee, club, company, or individual.",
    )


class DatesInfo(BaseModel):
    """Event dates and deadlines in ISO format (YYYY-MM-DD) whenever possible."""

    start_date: str | None = Field(
        default=None,
        description="Tournament match start date in ISO format (YYYY-MM-DD).",
    )
    end_date: str | None = Field(
        default=None,
        description="Tournament match end date in ISO format (YYYY-MM-DD).",
    )
    registration_deadline: str | None = Field(
        default=None,
        description="Explicit registration deadline in ISO format (YYYY-MM-DD). Only return if explicitly stated on the poster.",
    )
    auction_date: str | None = Field(
        default=None,
        description="Auction or player draft date in ISO format (YYYY-MM-DD).",
    )


class LocationInfo(BaseModel):
    """Tournament venue and address details."""

    venue: str | None = Field(
        default=None, description="Name of the ground, stadium, turf, arena, or venue."
    )
    address: str | None = Field(
        default=None, description="Specific street address or area details."
    )
    city: str | None = Field(
        default=None,
        description="City where the event is taking place, only when explicitly stated or reliably determined.",
    )
    state: str | None = Field(
        default=None,
        description="State or province, only when explicitly stated or reliably determined.",
    )
    country: str | None = Field(
        default=None,
        description="Country, only when explicitly stated or reliably determined.",
    )


class RegistrationInfo(BaseModel):
    """Registration rules, methods, contacts, and links."""

    available: bool = Field(
        default=False,
        description="Whether registration is explicitly mentioned as open or available.",
    )
    methods: list[str] = Field(
        default_factory=list,
        description="Array of visible registration methods (e.g. ['Call', 'WhatsApp', 'QR Code', 'Website', 'Google Form', 'Email', 'App', 'In Person']).",
    )
    qr_code_present: bool = Field(
        default=False, description="True if a QR code is visibly present on the poster."
    )
    registration_url: str | None = Field(
        default=None,
        description="URL for registration if explicitly written or reliably decoded. Never invent URLs.",
    )
    registration_fee: str | None = Field(
        default=None,
        description="Registration/entry fee mentioned in registration section (e.g. ₹500, ₹5,000 per team, Free).",
    )
    contact_person: str | None = Field(
        default=None,
        description="Name(s) of the contact person(s) for registration or inquiries.",
    )
    contact_numbers: list[str] = Field(
        default_factory=list,
        description="List of all visible contact phone/WhatsApp numbers without altering digits.",
    )
    email: str | None = Field(
        default=None,
        description="Contact email address if explicitly visible on the poster.",
    )


class AuctionInfo(BaseModel):
    """Auction or draft details if applicable."""

    required: bool = Field(
        default=False,
        description="Whether a player auction or draft is required/mentioned.",
    )
    date: str | None = Field(
        default=None, description="Auction date in ISO format (YYYY-MM-DD)."
    )
    venue: str | None = Field(default=None, description="Auction venue name.")
    address: str | None = Field(default=None, description="Auction address.")


class ParticipationInfo(BaseModel):
    """Team, player count, eligibility, and participation requirements."""

    number_of_teams: int | None = Field(
        default=None,
        description="Total number of teams participating or slots available (e.g. 10).",
    )
    number_of_players: int | None = Field(
        default=None,
        description="Number of players per team or total player pool (e.g. 100).",
    )
    eligibility: str | None = Field(
        default=None,
        description="Eligibility criteria (e.g. Only Maheshwari Samaj members, Under-19, Corporate employees).",
    )
    team_requirements: str | None = Field(
        default=None,
        description="Specific requirements for teams (e.g. Minimum 8 players, Jersey mandatory).",
    )
    player_requirements: str | None = Field(
        default=None,
        description="Specific requirements for individual players (e.g. Age proof, Aadhaar card required).",
    )


class FeesInfo(BaseModel):
    """Detailed fee breakdown with currency preserved."""

    registration_fee: str | None = Field(
        default=None, description="General registration fee (e.g. ₹500, $50)."
    )
    team_fee: str | None = Field(
        default=None, description="Entry fee per team (e.g. ₹5,000)."
    )
    player_fee: str | None = Field(
        default=None, description="Entry fee per player (e.g. ₹500)."
    )
    auction_fee: str | None = Field(
        default=None, description="Player auction/draft registration fee (e.g. ₹1,000)."
    )


class PrizesInfo(BaseModel):
    """Prize and awards breakdown."""

    first_prize: str | None = Field(
        default=None,
        description="First prize / Winner prize amount or description (e.g. ₹50,000 + Trophy).",
    )
    second_prize: str | None = Field(
        default=None,
        description="Second prize / Runner-up prize amount or description (e.g. ₹25,000 + Trophy).",
    )
    third_prize: str | None = Field(
        default=None, description="Third prize amount or description (e.g. ₹10,000)."
    )
    other_prizes: list[str] = Field(
        default_factory=list,
        description="Special awards and prizes (e.g. ['Man of the Match - ₹1,000', 'Best Bowler - Trophy', 'Player of the Tournament']).",
    )


class ExtractionMeta(BaseModel):
    """Extraction quality metadata and review flags."""

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Extraction quality and completeness score between 0.0 and 1.0 (e.g. 0.95 clear, 0.88 good with missing fields, 0.70 blurry, 0.50 difficult).",
    )
    fields_needing_review: list[str] = Field(
        default_factory=list,
        description="List of field paths where information was present on poster but blurry, partially readable, or ambiguous.",
    )


class TournamentPosterExtraction(BaseModel):
    """Structured response containing all extracted tournament information."""

    tournament: TournamentInfo = Field(default_factory=TournamentInfo)
    dates: DatesInfo = Field(default_factory=DatesInfo)
    location: LocationInfo = Field(default_factory=LocationInfo)
    registration: RegistrationInfo = Field(default_factory=RegistrationInfo)
    auction: AuctionInfo = Field(default_factory=AuctionInfo)
    participation: ParticipationInfo = Field(default_factory=ParticipationInfo)
    fees: FeesInfo = Field(default_factory=FeesInfo)
    prizes: PrizesInfo = Field(default_factory=PrizesInfo)
    additional_information: list[str] = Field(
        default_factory=list,
        description="Useful tournament rules, selection processes, match format/overs, and instructions. Do NOT include marketing slogans.",
    )
    extraction: ExtractionMeta = Field(default_factory=ExtractionMeta)


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Short error code or description.")
    detail: str = Field(..., description="Detailed explanation of the error.")


class RootResponse(BaseModel):
    """Root endpoint response."""

    message: str
    status: str


class HealthResponse(BaseModel):
    """Health check endpoint response."""

    status: str
