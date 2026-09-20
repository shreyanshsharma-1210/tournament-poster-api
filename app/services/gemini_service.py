"""Gemini Vision Service for extracting structured tournament details from posters."""

import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.models import TournamentPosterExtraction

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert sports tournament poster information extraction system.

Analyze the entire uploaded poster, including small text.

Extract ONLY information that is actually visible or reliably readable.

NEVER hallucinate.
NEVER guess missing information.
NEVER invent dates, phone numbers, fees, addresses, URLs, people or organizations.

Date rules:
- Distinguish tournament dates, auction dates, registration deadlines, and other dates.
- start_date and end_date: match play dates in ISO format (YYYY-MM-DD).
- registration_deadline: cutoff date for registration in ISO format (YYYY-MM-DD). Only extract if explicitly stated on the poster. NEVER infer a deadline from the tournament dates.
- auction_date: date when player auction or draft occurs in ISO format (YYYY-MM-DD).
- If the year is unclear or missing, do not invent it.

Contact rules:
- Extract EVERY visible phone number. Keep original digits without alteration or fabrication.
- Extract contact person name(s) and email address if visible.

Location rules:
- Extract venue and address separately.
- Extract city, state, and country ONLY when explicitly written on the poster or reliably determined from clearly stated location details.
- Do NOT guess or hallucinate city/state/country from vague names.

Registration rules:
- Extract registration methods as an array of visible methods (e.g. ['Call', 'WhatsApp', 'QR Code', 'Website', 'Google Form', 'Email', 'App', 'In Person', 'Other']).
- Detect visible QR codes: set qr_code_present to true if a QR code is visibly present. Do NOT invent registration URLs.

Fee rules:
- Extract explicitly mentioned fees with currency preserved (e.g. registration_fee, team_fee, player_fee, auction_fee).
- If no fee is mentioned, return null.

Prize rules:
- Extract first_prize, second_prize, third_prize.
- Put individual awards (e.g. Man of the Match, Best Bowler, Best Batsman, Player of the Tournament) in other_prizes array.

Participation rules:
- Extract number_of_teams, number_of_players, eligibility, team_requirements, and player_requirements.
- Do not convert approximate statements into exact numbers.

Additional Information:
- Include ONLY useful tournament rules, selection procedures (e.g. auction selection), Samaj eligibility, match duration, number of overs, or instructions.
- IGNORE and EXCLUDE marketing slogans or decorative text (e.g. do NOT include 'Play Compete Conquer', 'More Than Just a Game', 'Together for a Bigger Game').

Extraction Quality & Confidence:
- Set confidence between 0.0 and 1.0 representing approximate extraction quality and completeness (e.g. 0.95 for excellent clear poster, 0.88 for good with some missing fields, 0.70 for blurry/unclear text, 0.50 for very difficult poster). Do not automatically return 1.0.
- In fields_needing_review, add field paths ONLY if text was present on poster but blurry, partially readable, or ambiguous. Do not add fields merely because they are legitimately absent.

If information is absent, return null for scalar fields and [] for arrays.

Return only the structured response."""

USER_PROMPT = "Please analyze this tournament poster image carefully and extract all tournament details according to the schema."


class GeminiServiceException(Exception):
    """Base exception for Gemini service errors."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail or message


class GeminiService:
    """Service to interact with Google Gemini multimodal models."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

    def get_client(self) -> genai.Client:
        """Initialize and return the Google GenAI client."""
        if (
            not self.api_key
            or self.api_key == "your_key_here"
            or self.api_key == "your_gemini_api_key_here"
        ):
            raise GeminiServiceException(
                message="Gemini API key is not configured",
                status_code=500,
                detail="GEMINI_API_KEY environment variable is missing or unset. Please set a valid Gemini API key in your .env file.",
            )
        return genai.Client(api_key=self.api_key)

    async def extract_tournament_from_image(
        self, image_bytes: bytes, mime_type: str
    ) -> TournamentPosterExtraction:
        """
        Send tournament poster image directly to Gemini vision and return structured extraction.
        """
        client = self.get_client()

        try:
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )

            response = client.models.generate_content(
                model=self.model,
                contents=[image_part, USER_PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=TournamentPosterExtraction,
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                ),
            )

            if response.parsed and isinstance(
                response.parsed, TournamentPosterExtraction
            ):
                return response.parsed

            if response.text:
                return TournamentPosterExtraction.model_validate_json(response.text)

            raise GeminiServiceException(
                message="Empty extraction response",
                status_code=502,
                detail="Gemini API returned an empty response. Please check image clarity and try again.",
            )

        except APIError as e:
            logger.error("Gemini API Error: %s", str(e))
            error_message = str(e)
            if (
                "API_KEY_INVALID" in error_message
                or "invalid API key" in error_message.lower()
            ):
                raise GeminiServiceException(
                    message="Invalid Gemini API Key",
                    status_code=401,
                    detail="The provided Gemini API key is invalid or unauthorized.",
                ) from e
            elif (
                "RESOURCE_EXHAUSTED" in error_message
                or "quota" in error_message.lower()
            ):
                raise GeminiServiceException(
                    message="Gemini API Quota Exceeded",
                    status_code=429,
                    detail="Gemini API rate limit or quota exceeded. Please try again later.",
                ) from e
            else:
                raise GeminiServiceException(
                    message="Gemini API Error",
                    status_code=502,
                    detail=f"Error communicating with Gemini Vision API: {e.message if hasattr(e, 'message') else str(e)}",
                ) from e

        except GeminiServiceException:
            raise

        except Exception as e:
            logger.exception("Unexpected error during Gemini extraction")
            raise GeminiServiceException(
                message="Poster extraction failed",
                status_code=500,
                detail=f"An unexpected error occurred while processing the poster: {e!s}",
            ) from e


# Global singleton instance for injection
gemini_service = GeminiService()
