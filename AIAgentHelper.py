import os
import json
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
from dotenv import load_dotenv

# Import existing helpers
from EventDBHelper import DatabaseHelper
import AIHelper

# Load environment variables
load_dotenv()

class AIAgentHelper:
    def __init__(self):
        self.db = DatabaseHelper()
        self.ai_helper = AIHelper
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
        
        if not self.api_key:
            logging.error("DASHSCOPE_API_KEY not found in environment variables.")
            # Fallback or error handling
            
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )
        self.model = "qwen-flash"

    def start_new_session(self, host_id: int, initial_prompt: str) -> int:
        """
        Creates a new session, processes the initial prompt, and returns the session_id.
        """
        # 1. Create a basic starting draft
        default_draft = {
            "event_name": "New Event",
            "description": "",
            "event_type": "physical", # Default setting
            "visibility": "private",  # Default setting
            "start_date": "",
            "end_date": "",
            "start_time": "",
            "end_time": "",
            "location": "",
            "interest_tags": "",
            "enable_group_chat": 1,
            "enable_minigames": 1,
            "ai_theme": "",
            "image_source": "ai" # Use AI-generated image by default
        }
        
        # 2. Save the session to the database
        session_id = self.db.create_ai_session(host_id, default_draft)
        
        # 3. Handle the first message
        self.process_turn(session_id, initial_prompt)
        
        return session_id

    def process_turn(self, session_id: int, user_message: str) -> Dict[str, Any]:
        """
        Main process: User sends message, AI replies, updates draft, checks impact, and responds.
        """
        # 1. Save the user's message
        self.db.add_ai_message(session_id, "admin", user_message)
        
        # 2. Get the current session info
        session = self.db.get_ai_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        current_draft = json.loads(session["current_draft_json"])
        history = self.db.get_ai_messages(session_id)
        
        # 3. Create the instructions for the AI
        system_prompt = self._build_system_prompt(current_draft)
        messages = [{"role": "system", "content": system_prompt}]
        
        # Include the last 10 messages to keep the conversation context without using too much memory
        for msg in history[-10:]:
            role = "user" if msg["role"] == "admin" else "assistant"
            # If the AI sent data before, send it back as data so it remembers what it said
            messages.append({"role": role, "content": msg["content"]})
            
        # 4. Call AI
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=2000,
                temperature=0.7
            )
            response_content = completion.choices[0].message.content
            ai_response_json = json.loads(response_content)
            
            # --- DEBUG LOGGING ---
            print(f"\n[DEBUG] Full AI Response JSON:\n{json.dumps(ai_response_json, indent=2)}\n")
            print(f"[DEBUG] Warning Message Field: {ai_response_json.get('warning_message')}\n")
            # ---------------------

            # Get the changes the AI wants to make
            raw_patch = ai_response_json.get("patch", {})
            
            # Only keep changes that are actually different from the current draft
            patch = {}
            for k, v in raw_patch.items():
                # Check if the value is different.
                # Note: "1" and 1 might look different, but that is okay for now.
                if current_draft.get(k) != v:
                    patch[k] = v

            # If the AI didn't provide a summary, create one automatically
            if "ai_thinking_summary" not in ai_response_json or not ai_response_json["ai_thinking_summary"]:
                if ai_response_json.get("diff_mode"):
                    changed_fields = ", ".join(patch.keys()) if patch else "details"
                    ai_response_json["ai_thinking_summary"] = f"User requested updates to {changed_fields}."
                else:
                    ai_response_json["ai_thinking_summary"] = "User is defining new event details."

            # Clean up the description to make sure it is just one paragraph
            if "description" in patch and isinstance(patch["description"], str):
                import re
                desc = patch["description"]
                # 1. Remove bold and italic formatting
                desc = desc.replace("**", "").replace("__", "")
                # 2. Replace long dashes with short dashes
                desc = desc.replace("—", " - ")
                # 3. Remove bullet points at the start of lines
                desc = re.sub(r'(?m)^[\s]*[-*•]\s+', '', desc)
                
                # 4. Combine everything into one block of text by replacing new lines with spaces
                
                # Fix text that actually says "\n"
                desc = desc.replace('\\n', ' ').replace('\\r', ' ')
                
                # Remove remaining backslashes
                desc = desc.replace('\\', '')

                # Then replace actual hidden line break characters
                desc = re.sub(r'[\r\n]+', ' ', desc).strip()
                
                # Remove any resulting double spaces
                desc = re.sub(r'\s+', ' ', desc)

                patch["description"] = desc
            
            # Safety Check: If the AI talks about finding an image, make sure it actually searches for one
            # Sometimes the AI says it will search but forgets to add the command.
            if not ai_response_json.get("suggest_image_query"):
                text_lower = ai_response_json.get("assistant_block", "").lower()
                triggers = ["image finder", "brought up the image", "search for an image", "finding an image"]
                if any(t in text_lower for t in triggers):
                    # Create a search query using the event details we have
                    fallback_query = f"{current_draft.get('event_name', 'Community Event')} {current_draft.get('location', '')} Singapore".strip()
                    ai_response_json["suggest_image_query"] = fallback_query
                    print(f"[DEBUG] Safety Net triggered: Injected image query '{fallback_query}'")

            # Send the filtered changes back to the user
            ai_response_json["patch"] = patch

            # --- 4b. Ask the Advisor Agent for feedback ---
            # We ask the advisor one by one.
            # Only ask if something changed.
            updated_draft = current_draft.copy()
            updated_draft.update(patch)

            advisor_feedback = self._get_advisor_feedback(updated_draft, user_message)
            
            # --- DEBUG LOGGING (Advisor) ---
            print(f"\n[DEBUG] [Advisor Agent] Feedback: {advisor_feedback}\n")
            # -------------------------------
            
            if advisor_feedback:
                 ai_response_json["advisory_message"] = advisor_feedback
            
            # Save the full response so the app can display it correctly
            # This allows the app to show the different parts (message, summary, etc.)
            ai_text = json.dumps(ai_response_json)
            
        except Exception as e:
            logging.error(f"AI Error: {e}")
            # Use this default response if something goes wrong
            fallback_response = {
                "assistant_block": "Sorry, I encountered an error processing your request.",
                "summary_block_title": "",
                "summary_items": [],
                "missing_questions": [],
                "ai_thinking_summary": "Error processing intent.",
                "diff_mode": False,
                "patch": {}
            }
            ai_text = json.dumps(fallback_response)
            patch = {}
            
        # 5. Apply the changes
        updated_draft = current_draft.copy()
        updated_draft.update(patch)
        
        # 6. Check how good the event is
        impact_result = self.ai_helper.analyze_event_impact(updated_draft)
        
        # 7. Save the changes to the database
        self.db.update_ai_session_draft(session_id, json.dumps(updated_draft))
        msg_id = self.db.add_ai_message(session_id, "ai", ai_text)
        self.db.add_ai_patch(session_id, msg_id, json.dumps(patch), json.dumps(impact_result))
        
        # 8. Send the result back to the app
        return {
            "session_id": session_id,
            "ai_message": ai_text, # Contains all the data
            "draft": updated_draft,
            "patch": patch,
            "impact": impact_result
        }

    def _get_advisor_feedback(self, draft: Dict[str, Any], user_msg: str) -> Optional[str]:
        """
        Agent 2: The Advisor. Checks if the event is safe for seniors and good quality.
        Returns a message or nothing.
        """
        # Get the official rules from AIHelper to ensure consistency
        rules = self.ai_helper.get_spec_rules()
        
        prompt = f"""
You are the KampongKonek Intergenerational Safety Officer.
Your job is to enforce senior-friendly standards based on the Official Scoring Rules.

Current Draft:
{json.dumps(draft, indent=2)}

User's Latest Request: "{user_msg}"

OFFICIAL SCORING RULES (Use these as the ground truth for valid times/types):
{rules}

INSTRUCTIONS:
1. IGNORE EMPTY FIELDS: Do NOT comment on fields that are empty (""), null, or "TBD". Only judge values that exist.
2. CHECK TIME: Use the "Timing accessibility" rule. If the time results in a penalty or low score (e.g., late night), warn the user.
   - If start_time or end_time is missing/empty, say NOTHING about time.
3. CHECK DESCRIPTION: Only check word count if the description is NOT empty.
4. BE LOGICAL: Do not suggest changes that contradict the rules.
5. TIME FORMAT: When mentioning time in your "advisory_message", ALWAYS use 12-hour AM/PM format (e.g., "2:00 PM" instead of "14:00"). Convert if necessary.

Output Rules:
- If a violation is found (based on the Scoring Rules), return a DIRECT warning.
- If everything looks fine or fields are empty, return null.
- Return valid JSON: {{ "advisory_message": "..." }} or {{ "advisory_message": null }}
- Keep it under 2 sentences.
"""
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                max_tokens=2000, # Cap at 1k tokens
                temperature=0.7
            )
            res = json.loads(completion.choices[0].message.content)
            return res.get("advisory_message")
        except Exception as e:
            logging.error(f"Advisor Agent Error: {e}")
            return None

    def revert_session_to_message(self, session_id: int, target_message_id: int) -> Dict[str, Any]:
        """
        Reverts the session to the state it was in after target_message_id was processed.
        Reconstructs the draft by replaying patches.
        """
        # 1. Get all patches
        patches = self.db.get_ai_patches(session_id)
        
        # 2. Filter patches up to target message
        relevant_patches = []
        for p in patches:
            if target_message_id == -1:
                break
                
            # Only include patches that are associated with a message ID <= target (or have no message ID for initial setup if any)
            if p["message_id"] and p["message_id"] <= target_message_id:
                relevant_patches.append(p)
                
        # 3. Reconstruct Draft (Start with Default)
        current_draft = {
            "event_name": "New Event",
            "description": "",
            "event_type": "physical",
            "visibility": "private",
            "start_date": "",
            "end_date": "",
            "start_time": "",
            "end_time": "",
            "location": "",
            "interest_tags": "",
            "enable_group_chat": 1,
            "enable_minigames": 1,
            "ai_theme": "",
            "image_source": "ai"
        }
        
        for p in relevant_patches:
            try:
                patch_data = json.loads(p["patch_json"])
                current_draft.update(patch_data)
            except json.JSONDecodeError:
                pass
            
        # 4. Save to DB (Update draft, delete future messages/patches)
        self.db.revert_session_to_checkpoint(session_id, current_draft, target_message_id)
        
        return current_draft

    def _build_system_prompt(self, current_draft: Dict[str, Any]) -> str:
        draft_str = json.dumps(current_draft, indent=2)
        return f"""
You are the KampungKonek Event Wizard, an expert in creating intergenerational events.
Your goal is to help the admin complete their event draft by extracting details and asking missing questions.

Current Event Draft:
{draft_str}

AI Response Structure:
Return valid JSON matching this structure exactly:
{{
  "assistant_block": "Block A: The main conversational response. Include acknowledgement, 'I’m still missing a few details...' (if applicable), numbered missing questions (max 3), and a closing line.",
  "summary_block_title": "Block B Title: 'Here’s what I’ve set so far based on your message:' OR 'Here’s what I’ve changed:' (if updating)",
  "summary_items": ["List of strings for Block B. E.g., 'Draft title: ...', 'Time: ...' or 'Time: 8pm -> 3pm'"],
  "missing_questions": ["List of missing questions for internal tracking (optional)"],
  "ai_thinking_summary": "A 3rd-person summary of the user's intent. E.g. 'User is trying to create a heritage event with...' or 'User requested a change in venue to...'.",
  "suggest_image_query": "Search query string if user asks to find an image (e.g. 'Karaoke Singapore'). Null otherwise.",
  "diff_mode": <boolean: true if updating existing fields, false if setting new ones>,
  "patch": {{ "field_name": "new_value", ... }}
}}

Rules:
1. Extract event details from the user's message and map them to the schema fields:
   - event_name, description, location, start_date, end_date, start_time, end_time
   - visibility (public/private), event_type (physical/online), interest_tags
   - enable_group_chat (1/0), enable_minigames (1/0)
   - image_url, image_source
2. CRITICAL: If the user provides ANY new information (e.g. Date, Time, Venue), you MUST include it in the "patch" object.
   - "patch" is the ONLY way the database gets updated. If you don't put it in "patch", the user won't see it!
   - Date Format: YYYY-MM-DD (e.g. 2026-02-25)
   - Time Format: HH:MM (24-hour, e.g. 15:00)
3. Identify MISSING required fields (Date, Time, Location, Type, Visibility).
4. Ask for the 1-3 most important missing fields in "assistant_block" (numbered).
5. "summary_items" rules:
   - If diff_mode is false: List 5-7 known/inferred fields. Mark inferred as "(inferred)".
   - If diff_mode is true: List ONLY changed fields (max 6) in format "Field: Old -> New".
6. "assistant_block" rules:
   - Start with a warm acknowledgement.
   - If missing info, say "I’m still missing a few details..." then list questions.
   - End with "Once you tell me these, I’ll update the draft..."
   - DO NOT use markdown bolding (**), italics, or em dashes (—). Use standard punctuation.
   - Use numbered lists (1., 2.) for questions. Avoid bullet points (-).
7. Enforce Intergenerational Focus: Suggest inclusive changes if needed.
8. FORMATTING RULES for 'description' field (STRICT):
   - Write the entire description as ONE SINGLE CONTINUOUS PARAGRAPH.
   - ABSOLUTELY NO vertical lists, bullet points, or agendas.
   - Flatten any lists into full sentences within the paragraph.
   - Example: Instead of "- 9am: Welcome", write "At 9am, we will have the Welcome."
   - DO NOT use markdown symbols like **, -, #, or em dashes (—).
   - DO NOT use line breaks (\n).
9. "ai_thinking_summary" rules:
   - Summarize the user's intent in 3rd person.
   - If creating: "User is trying to create a [type] event with:"
   - If updating: "User requested change in [field] to..."
10. IMAGE HANDLING:
    - If user input contains "[I uploaded an image at ...]", extract the path and set patch.image_url = [path] and patch.image_source = "upload".
    - If user input contains "I have selected this image: ...", extract the url and set patch.image_url = [url] and patch.image_source = "ai".
    - If draft has Title, Date, Time, Location but NO image, ASK the user: "Would you like to upload an image or have me search for one?"
    - STRICTLY ONLY set 'suggest_image_query' if the user EXPLICITLY asks to search (e.g. "find one", "search image", "suggest picture").
    - WHEN setting 'suggest_image_query', you MUST include the actual query string in the JSON field "suggest_image_query".
    - NEVER set 'suggest_image_query' automatically.
    - If 'suggest_image_query' is set, say "I've brought up the image finder..." in assistant_block.
11. INTERGENERATIONAL RUBRICS & WARNINGS:
    - PROACTIVELY CHECK if the user's request (or the resulting draft) violates senior-friendly principles.
    - IF a violation is detected, populate "warning_message" with a polite, educational caution (max 2 sentences).
     - DO NOT BLOCK the change. Apply the change to "patch" regardless.
     - CRITICAL: DO NOT include the warning text in "assistant_block". "assistant_block" must remain positive and focused on the update/questions.
     - Rubrics to Watch:
       a) Time: Events ending after 9:00 PM or starting before 8:00 AM are "too late/early for many seniors".
      b) Venue: High-intensity venues (e.g. "Trampoline Park", "Standing Bar") or accessibility issues.
      c) Complexity: "Bring your own smartphone with app installed" (might need tech support).
    - Example Warning: "Just a heads-up: 11pm is quite late for many seniors. You might want to consider ending by 9pm to encourage better attendance."
"""
