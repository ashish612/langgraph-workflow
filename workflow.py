"""
LangGraph workflow for AI-powered communication automation.

This workflow takes a text message and:
1. Generates a formal email using an LLM (Cisco Bridge API)
2. Pauses for human review (optional)
3. Sends the email to configured recipients
4. Creates a Webex message with mentions
5. Posts the message to the configured Webex space
"""

from typing import List, Literal, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.prompts import ChatPromptTemplate

from models import WorkflowState
from services.email_service import EmailService
from services.webex_service import WebexService
from services.cisco_bridge_llm import CiscoBridgeChatModel
from config import Settings


class CommunicationWorkflow:
    """
    LangGraph-based workflow for automated formal communication.

    Takes an informal message and transforms it into:
    - A formal email sent to configured recipients
    - A Webex message posted to a space with mentions

    Uses Cisco Bridge API (GPT-4o-mini) for LLM capabilities.
    Supports human-in-the-loop review before sending.
    """

    def __init__(self, settings: Settings, enable_human_review: bool = True):
        self.settings = settings
        self.enable_human_review = enable_human_review

        # Initialize Cisco Bridge LLM
        self.llm = CiscoBridgeChatModel(
            client_id=settings.cisco_client_id,
            client_secret=settings.cisco_client_secret,
            app_key=settings.cisco_app_key,
            token_url=settings.cisco_token_url,
            api_url=settings.cisco_api_url,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        self.email_service = EmailService(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            from_address=settings.email_from,
        )
        self.webex_service = WebexService(access_token=settings.webex_access_token)
        self.checkpointer = MemorySaver()
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow with optional human review for both email and Webex."""
        # Create the graph with our state type
        builder = StateGraph(WorkflowState)

        # Add nodes
        builder.add_node("generate_email", self._generate_email)
        builder.add_node("email_review", self._email_review_node)
        builder.add_node("send_email", self._send_email)
        builder.add_node("generate_webex_message", self._generate_webex_message)
        builder.add_node("webex_review", self._webex_review_node)
        builder.add_node("post_to_webex", self._post_to_webex)
        builder.add_node("handle_rejection", self._handle_rejection)

        # Define the flow with conditional routing
        builder.add_edge(START, "generate_email")
        builder.add_edge("generate_email", "email_review")

        # Conditional edge after email review
        builder.add_conditional_edges(
            "email_review",
            self._route_after_email_review,
            {
                "approved": "send_email",
                "rejected": "handle_rejection",
                "awaiting": END,  # Paused for email review
            },
        )

        builder.add_edge("send_email", "generate_webex_message")
        builder.add_edge("generate_webex_message", "webex_review")

        # Conditional edge after Webex review
        builder.add_conditional_edges(
            "webex_review",
            self._route_after_webex_review,
            {
                "approved": "post_to_webex",
                "rejected": "handle_rejection",
                "awaiting": END,  # Paused for Webex review
            },
        )

        builder.add_edge("post_to_webex", END)
        builder.add_edge("handle_rejection", END)

        # Compile with checkpointer for interrupt support
        # Interrupt before both review nodes when human review is enabled
        interrupt_nodes = ["email_review", "webex_review"] if self.enable_human_review else []
        return builder.compile(
            checkpointer=self.checkpointer,
            interrupt_before=interrupt_nodes,
        )

    def _route_after_email_review(self, state: WorkflowState) -> Literal["approved", "rejected", "awaiting"]:
        """Route based on email review decision."""
        if state.get("email_rejected"):
            return "rejected"
        elif state.get("email_approved"):
            return "approved"
        else:
            return "awaiting"

    def _route_after_webex_review(self, state: WorkflowState) -> Literal["approved", "rejected", "awaiting"]:
        """Route based on Webex review decision."""
        if state.get("webex_rejected"):
            return "rejected"
        elif state.get("webex_approved"):
            return "approved"
        else:
            return "awaiting"

    def _email_review_node(self, state: WorkflowState) -> WorkflowState:
        """
        Email review checkpoint node.

        This node marks the state as awaiting email review. The actual review
        happens externally, and the workflow is resumed with updated state.
        """
        # If already approved/rejected (resumed after review), pass through
        if state.get("email_approved") or state.get("email_rejected"):
            return state

        # Mark as awaiting email review
        return {
            **state,
            "status": "awaiting_email_review",
            "requires_human_review": True,
        }

    def _webex_review_node(self, state: WorkflowState) -> WorkflowState:
        """
        Webex review checkpoint node.

        This node marks the state as awaiting Webex review. The actual review
        happens externally, and the workflow is resumed with updated state.
        """
        # If already approved/rejected (resumed after review), pass through
        if state.get("webex_approved") or state.get("webex_rejected"):
            return state

        # Mark as awaiting Webex review
        return {
            **state,
            "status": "awaiting_webex_review",
            "requires_human_review": True,
        }

    def _handle_rejection(self, state: WorkflowState) -> WorkflowState:
        """Handle when email or Webex message is rejected by the human reviewer."""
        return {
            **state,
            "status": "cancelled",
            "email_sent": state.get("email_sent", False),  # Keep existing email status
            "webex_posted": False,
        }

    def _generate_email(self, state: WorkflowState) -> WorkflowState:
        """Generate a formal email from the original message using the LLM."""
        original_message = state.get("original_message", "")
        sender_name = state.get("sender_name", "Team Member")

        # Prompt for generating formal email
        email_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a professional communication assistant. Your task is to transform 
informal messages into formal, professional emails. 

Guidelines:
- Maintain the core message and intent
- Use professional language and tone
- Include appropriate greeting and closing
- Be concise but complete
- Do not add information not present in the original message

Output format:
SUBJECT: [A concise, professional subject line]
---
[The formal email body]""",
                ),
                (
                    "human",
                    """Transform this message into a formal email:

Original message: {message}

The email should be signed by: {sender_name}""",
                ),
            ]
        )

        chain = email_prompt | self.llm

        response = chain.invoke({"message": original_message, "sender_name": sender_name})
        content = response.content

        # Parse the response
        if "---" in content:
            parts = content.split("---", 1)
            subject_line = parts[0].replace("SUBJECT:", "").strip()
            email_body = parts[1].strip()
        else:
            # Fallback parsing
            lines = content.strip().split("\n")
            subject_line = lines[0].replace("SUBJECT:", "").strip() if lines else "Update"
            email_body = "\n".join(lines[1:]).strip() if len(lines) > 1 else content

        return {
            **state,
            "formal_email_subject": subject_line,
            "formal_email_body": email_body,
            "status": "in_progress",
        }

    def _send_email(self, state: WorkflowState) -> WorkflowState:
        """Send the formal email to configured recipients."""
        recipients = state.get("email_recipients", self.settings.email_recipients)
        subject = state.get("formal_email_subject", "")
        body = state.get("formal_email_body", "")

        errors = list(state.get("errors", []))

        result = self.email_service.send_email(
            recipients=recipients, subject=subject, body=body
        )

        if not result.success:
            errors.append(f"Email: {result.message}")

        return {
            **state,
            "email_sent": result.success,
            "email_error": None if result.success else result.message,
            "errors": errors,
        }

    def _generate_webex_message(self, state: WorkflowState) -> WorkflowState:
        """Generate a Webex message from the original message using the LLM."""
        original_message = state.get("original_message", "")
        sender_name = state.get("sender_name", "Team Member")
        mention_emails = state.get("webex_mentions", self.settings.webex_mentions)

        # Create mention names for the prompt
        mention_names = [email.split("@")[0] for email in mention_emails]
        mentions_text = ", ".join(mention_names) if mention_names else "the team"

        # Prompt for generating Webex message
        webex_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a professional communication assistant. Your task is to transform 
messages into clear, concise Webex space messages.

Guidelines:
- Keep it brief and actionable
- Use a friendly but professional tone
- Make it easy to read (use bullet points if helpful)
- The message will be posted in a team collaboration space
- Do not include greetings like "Hi" - get straight to the point
- End with any action items or next steps if applicable

Output the message in markdown format suitable for Webex.""",
                ),
                (
                    "human",
                    """Transform this message into a Webex space message addressed to {mentions}:

Original message: {message}

From: {sender_name}""",
                ),
            ]
        )

        chain = webex_prompt | self.llm

        response = chain.invoke({
            "message": original_message,
            "sender_name": sender_name,
            "mentions": mentions_text,
        })

        return {
            **state,
            "webex_message": response.content,
        }

    def _post_to_webex(self, state: WorkflowState) -> WorkflowState:
        """Post the message to the configured Webex space."""
        room_id = state.get("webex_room_id", self.settings.webex_room_id)
        message = state.get("webex_message", "")
        mention_emails = state.get("webex_mentions", self.settings.webex_mentions)

        errors = list(state.get("errors", []))

        result = self.webex_service.post_message(
            room_id=room_id,
            text=message,
            markdown=message,
            mention_emails=mention_emails,
        )

        if not result.success:
            errors.append(f"Webex: {result.message}")

        # Determine final status
        email_sent = state.get("email_sent", False)
        webex_success = result.success

        if email_sent and webex_success:
            final_status = "completed"
        elif not email_sent and not webex_success:
            final_status = "failed"
        else:
            final_status = "completed"  # Partial success

        return {
            **state,
            "webex_posted": result.success,
            "webex_error": None if result.success else result.message,
            "errors": errors,
            "status": final_status,
        }

    def run(
        self,
        message: str,
        sender_name: str = "Team Member",
        email_recipients: List[str] = None,
        webex_room_id: str = None,
        webex_mentions: List[str] = None,
        thread_id: str = "default",
    ) -> WorkflowState:
        """
        Execute the communication workflow.

        Args:
            message: The original message to transform and send
            sender_name: Name of the sender for signatures
            email_recipients: Optional override for email recipients
            webex_room_id: Optional override for Webex room ID
            webex_mentions: Optional override for Webex mentions
            thread_id: Unique ID for this workflow run (for checkpointing)

        Returns:
            Workflow state (may be paused for human review)
        """
        initial_state: WorkflowState = {
            "original_message": message,
            "sender_name": sender_name,
            "email_recipients": email_recipients or self.settings.email_recipients,
            "webex_room_id": webex_room_id or self.settings.webex_room_id,
            "webex_mentions": webex_mentions or self.settings.webex_mentions,
            "status": "pending",
            "errors": [],
            "email_approved": False,
            "email_rejected": False,
            "webex_approved": False,
            "webex_rejected": False,
            "requires_human_review": self.enable_human_review,
        }

        config = {"configurable": {"thread_id": thread_id}}

        # Run the workflow (may pause at interrupt)
        result = None
        for event in self.graph.stream(initial_state, config, stream_mode="values"):
            result = event

        return result

    def get_pending_state(self, thread_id: str = "default") -> Optional[WorkflowState]:
        """
        Get the current state of a paused workflow.

        Args:
            thread_id: The thread ID of the workflow

        Returns:
            Current state if workflow is paused, None otherwise
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = self.graph.get_state(config)
        if state and state.values:
            return state.values
        return None

    def approve_email(
        self,
        thread_id: str = "default",
        edited_subject: str = None,
        edited_body: str = None,
    ) -> WorkflowState:
        """
        Approve the email and continue the workflow.

        Args:
            thread_id: The thread ID of the paused workflow
            edited_subject: Optional edited email subject
            edited_body: Optional edited email body

        Returns:
            Final workflow state after completion
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Get current state
        current_state = self.graph.get_state(config)
        if not current_state or not current_state.values:
            raise ValueError(f"No pending workflow found for thread_id: {thread_id}")

        # Prepare update with approval and any edits
        update: WorkflowState = {
            "email_approved": True,
            "email_rejected": False,
        }

        if edited_subject is not None:
            update["formal_email_subject"] = edited_subject
        if edited_body is not None:
            update["formal_email_body"] = edited_body

        # Update state and resume
        self.graph.update_state(config, update)

        # Continue execution
        result = None
        for event in self.graph.stream(None, config, stream_mode="values"):
            result = event

        return result

    def reject_email(
        self,
        thread_id: str = "default",
        reason: str = None,
    ) -> WorkflowState:
        """
        Reject the email and cancel the workflow.

        Args:
            thread_id: The thread ID of the paused workflow
            reason: Optional reason for rejection

        Returns:
            Final workflow state (cancelled)
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Get current state
        current_state = self.graph.get_state(config)
        if not current_state or not current_state.values:
            raise ValueError(f"No pending workflow found for thread_id: {thread_id}")

        # Prepare update with rejection
        update: WorkflowState = {
            "email_approved": False,
            "email_rejected": True,
            "rejection_reason": reason,
        }

        # Update state and resume
        self.graph.update_state(config, update)

        # Continue execution (will route to handle_rejection)
        result = None
        for event in self.graph.stream(None, config, stream_mode="values"):
            result = event

        return result

    def approve_webex(
        self,
        thread_id: str = "default",
        edited_message: str = None,
    ) -> WorkflowState:
        """
        Approve the Webex message and continue the workflow.

        Args:
            thread_id: The thread ID of the paused workflow
            edited_message: Optional edited Webex message

        Returns:
            Final workflow state after completion
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Get current state
        current_state = self.graph.get_state(config)
        if not current_state or not current_state.values:
            raise ValueError(f"No pending workflow found for thread_id: {thread_id}")

        # Prepare update with approval and any edits
        update: WorkflowState = {
            "webex_approved": True,
            "webex_rejected": False,
        }

        if edited_message is not None:
            update["webex_message"] = edited_message

        # Update state and resume
        self.graph.update_state(config, update)

        # Continue execution
        result = None
        for event in self.graph.stream(None, config, stream_mode="values"):
            result = event

        return result

    def reject_webex(
        self,
        thread_id: str = "default",
        reason: str = None,
    ) -> WorkflowState:
        """
        Reject the Webex message and cancel posting.

        Args:
            thread_id: The thread ID of the paused workflow
            reason: Optional reason for rejection

        Returns:
            Final workflow state (cancelled)
        """
        config = {"configurable": {"thread_id": thread_id}}

        # Get current state
        current_state = self.graph.get_state(config)
        if not current_state or not current_state.values:
            raise ValueError(f"No pending workflow found for thread_id: {thread_id}")

        # Prepare update with rejection
        update: WorkflowState = {
            "webex_approved": False,
            "webex_rejected": True,
            "webex_rejection_reason": reason,
        }

        # Update state and resume
        self.graph.update_state(config, update)

        # Continue execution (will route to handle_rejection)
        result = None
        for event in self.graph.stream(None, config, stream_mode="values"):
            result = event

        return result

    def run_without_review(
        self,
        message: str,
        sender_name: str = "Team Member",
        email_recipients: List[str] = None,
        webex_room_id: str = None,
        webex_mentions: List[str] = None,
    ) -> WorkflowState:
        """
        Execute the workflow without human review (auto-approve).

        Args:
            message: The original message to transform and send
            sender_name: Name of the sender for signatures
            email_recipients: Optional override for email recipients
            webex_room_id: Optional override for Webex room ID
            webex_mentions: Optional override for Webex mentions

        Returns:
            Final workflow state with results
        """
        initial_state: WorkflowState = {
            "original_message": message,
            "sender_name": sender_name,
            "email_recipients": email_recipients or self.settings.email_recipients,
            "webex_room_id": webex_room_id or self.settings.webex_room_id,
            "webex_mentions": webex_mentions or self.settings.webex_mentions,
            "status": "pending",
            "errors": [],
            "email_approved": True,  # Pre-approved
            "email_rejected": False,
            "webex_approved": True,  # Pre-approved
            "webex_rejected": False,
            "requires_human_review": False,
        }

        # Create a workflow without interrupts for this run
        builder = StateGraph(WorkflowState)
        builder.add_node("generate_email", self._generate_email)
        builder.add_node("email_review", self._email_review_node)
        builder.add_node("send_email", self._send_email)
        builder.add_node("generate_webex_message", self._generate_webex_message)
        builder.add_node("webex_review", self._webex_review_node)
        builder.add_node("post_to_webex", self._post_to_webex)

        builder.add_edge(START, "generate_email")
        builder.add_edge("generate_email", "email_review")
        builder.add_conditional_edges(
            "email_review",
            self._route_after_email_review,
            {"approved": "send_email", "rejected": END, "awaiting": END},
        )
        builder.add_edge("send_email", "generate_webex_message")
        builder.add_edge("generate_webex_message", "webex_review")
        builder.add_conditional_edges(
            "webex_review",
            self._route_after_webex_review,
            {"approved": "post_to_webex", "rejected": END, "awaiting": END},
        )
        builder.add_edge("post_to_webex", END)

        no_interrupt_graph = builder.compile()

        result = no_interrupt_graph.invoke(initial_state)
        return result


def create_workflow(
    settings: Settings = None,
    enable_human_review: bool = True,
) -> CommunicationWorkflow:
    """
    Factory function to create a configured workflow instance.

    Args:
        settings: Optional settings override. If not provided, loads from environment.
        enable_human_review: Whether to pause for human review before sending.

    Returns:
        Configured CommunicationWorkflow instance
    """
    from config import get_settings

    if settings is None:
        settings = get_settings()

    return CommunicationWorkflow(settings, enable_human_review=enable_human_review)

