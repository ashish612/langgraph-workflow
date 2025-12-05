"""
Webex service for posting messages to Webex spaces.
"""

import httpx
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class WebexResult:
    """Result of a Webex message post operation."""

    success: bool
    message: str
    message_id: Optional[str] = None


class WebexService:
    """Service for interacting with Webex API."""

    BASE_URL = "https://webexapis.com/v1"

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _get_person_id_by_email(self, email: str) -> Optional[str]:
        """
        Get a Webex person ID by their email address.

        Args:
            email: The email address to look up

        Returns:
            The person ID if found, None otherwise
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.BASE_URL}/people",
                    headers=self.headers,
                    params={"email": email},
                )
                response.raise_for_status()
                data = response.json()
                if data.get("items"):
                    return data["items"][0]["id"]
                return None
        except Exception:
            return None

    def post_message(
        self,
        room_id: str,
        text: str,
        markdown: Optional[str] = None,
        mention_emails: Optional[List[str]] = None,
    ) -> WebexResult:
        """
        Post a message to a Webex space.

        Args:
            room_id: The Webex room/space ID
            text: Plain text message
            markdown: Optional markdown formatted message
            mention_emails: Optional list of emails to mention in the message

        Returns:
            WebexResult with success status and details
        """
        try:
            # Build the message with mentions
            message_text = text
            message_markdown = markdown or text

            # If we have people to mention, prepend mentions to the message
            # Use <@personEmail:email> format which Webex resolves automatically
            if mention_emails:
                mention_parts = [f"<@personEmail:{email}>" for email in mention_emails if email]
                if mention_parts:
                    mentions_str = " ".join(mention_parts)
                    message_markdown = f"{mentions_str}\n\n{message_markdown}"

            # Prepare the payload
            payload: Dict[str, Any] = {
                "roomId": room_id,
                "text": message_text,
            }

            if markdown or mention_emails:
                payload["markdown"] = message_markdown

            # Send the message
            with httpx.Client() as client:
                response = client.post(
                    f"{self.BASE_URL}/messages",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                return WebexResult(
                    success=True,
                    message="Message posted successfully to Webex",
                    message_id=data.get("id"),
                )

        except httpx.HTTPStatusError as e:
            return WebexResult(
                success=False,
                message=f"Webex API error: {e.response.status_code} - {e.response.text}",
            )
        except Exception as e:
            return WebexResult(
                success=False, message=f"Failed to post to Webex: {str(e)}"
            )

    async def post_message_async(
        self,
        room_id: str,
        text: str,
        markdown: Optional[str] = None,
        mention_emails: Optional[List[str]] = None,
    ) -> WebexResult:
        """
        Async version of post_message.

        Args:
            room_id: The Webex room/space ID
            text: Plain text message
            markdown: Optional markdown formatted message
            mention_emails: Optional list of emails to mention

        Returns:
            WebexResult with success status and details
        """
        try:
            message_text = text
            message_markdown = markdown or text

            # Build mentions using <@personEmail:email> format which Webex resolves automatically
            if mention_emails:
                mention_parts = [f"<@personEmail:{email}>" for email in mention_emails if email]
                if mention_parts:
                    mentions_str = " ".join(mention_parts)
                    message_markdown = f"{mentions_str}\n\n{message_markdown}"

            # Prepare payload
            payload: Dict[str, Any] = {
                "roomId": room_id,
                "text": message_text,
            }

            if markdown or mention_emails:
                payload["markdown"] = message_markdown

            # Send message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}/messages",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                return WebexResult(
                    success=True,
                    message="Message posted successfully to Webex",
                    message_id=data.get("id"),
                )

        except httpx.HTTPStatusError as e:
            return WebexResult(
                success=False,
                message=f"Webex API error: {e.response.status_code} - {e.response.text}",
            )
        except Exception as e:
            return WebexResult(
                success=False, message=f"Failed to post to Webex: {str(e)}"
            )

