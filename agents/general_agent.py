import json
import logging
from typing import Dict, Any, List, Optional
from core.browser_engine import BrowserEngine
from core.llm_client import LLMClient
from agents.base_agent import BaseBrowserAgent

logger = logging.getLogger("ShadowBrowser.GeneralAgent")

SYSTEM_PROMPT = """
You are ShadowBrowser, an expert autonomous AI web agent. You control a real Google Chrome browser.
Your goal is to accomplish the user's objective by observing the web page and deciding the next action.

You are given:
1. The Current URL and Page Title.
2. The Indexed Interactive Elements on the page, labeled with numerical IDs: [ID] <tag> details "text".
3. The History of actions taken so far.

You must respond ONLY with a valid JSON object specifying your reasoning and your NEXT action:

JSON Format:
{
  "thought": "Brief explanation of what you see and why you are taking this action",
  "action": "click" | "type" | "press_key" | "scroll" | "upload_file" | "navigate" | "wait" | "done",
  "element_id": <int: element ID from the list, required for click/type/upload>,
  "text": "<string: text to type if action is type>",
  "press_enter": <bool: whether to press enter after typing, optional>,
  "file_path": "<string: path to file if action is upload_file>",
  "direction": "down" | "up",
  "amount": <int: pixels to scroll>,
  "key": "<string: e.g. 'Enter', 'Tab', 'Escape'>",
  "url": "<string: target URL if action is navigate>",
  "seconds": <float: seconds to wait>,
  "summary": "<string: final answer or summary when action is done>"
}

Rules:
- Choose the most direct, efficient element.
- When you reach the objective or find the requested information, choose action "done" with your complete summary.
- If a cookie consent, popup, or banner blocks the page, dismiss or close it first.
- Always output strict JSON only, without additional conversational text.
"""

class GeneralAgent(BaseBrowserAgent):
    """
    Autonomous AI Browser Agent capable of general web tasks, research,
    form submission, and site navigation.
    """

    async def run(self, task: str) -> Dict[str, Any]:
        """
        Executes an autonomous task loop until completed or max_steps reached.
        """
        logger.info(f"Starting autonomous agent for task: '{task}'")
        self.step_counter = 0
        self.history = []

        while self.step_counter < self.max_steps:
            self.step_counter += 1
            logger.info(f"\n--- [STEP {self.step_counter}/{self.max_steps}] ---")

            # 1. Observe state
            state = await self.observe()
            current_url = state["url"]
            elements_text = state["elements_text"]

            # Construct user prompt for LLM
            history_summary = "\n".join([
                f"- Step {h['step']}: Thought: {h.get('thought', '')} -> Action: {h.get('action', '')} -> Result: {h.get('result', '')}"
                for h in self.history[-4:]
            ]) or "None (just started)"

            user_prompt = f"""
OBJECTIVE: {task}

CURRENT BROWSER STATE:
- URL: {current_url}
- Title: {state['title']}

INTERACTIVE ELEMENTS:
{elements_text}

RECENT ACTION HISTORY:
{history_summary}

Decide your next action in JSON format.
"""
            # 2. Query LLM
            decision = self.llm.structured_action(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                image_base64=state.get("screenshot_b64") if False else None,  # Can enable vision if supported
            )

            thought = decision.get("thought", "Proceeding with next step.")
            act_type = decision.get("action", "wait")
            logger.info(f"AI Thought: {thought}")
            logger.info(f"AI Action: {act_type} -> {decision}")

            # 3. Check for completion
            if act_type == "done":
                summary = decision.get("summary", decision.get("result", "Completed successfully."))
                return {
                    "status": "success",
                    "steps": self.step_counter,
                    "summary": summary,
                    "final_url": current_url,
                    "history": self.history,
                }

            # 4. Execute action
            result = await self.execute_action(decision)
            logger.info(f"Action Result: {result}")

            # Record in history
            self.history.append({
                "step": self.step_counter,
                "thought": thought,
                "action": decision,
                "result": result,
                "url": current_url,
                "screenshot": state.get("screenshot_path"),
            })

            # Check if execution signaled completion
            if result.startswith("TASK_COMPLETED:"):
                return {
                    "status": "success",
                    "steps": self.step_counter,
                    "summary": result.replace("TASK_COMPLETED:", "").strip(),
                    "final_url": current_url,
                    "history": self.history,
                }

        return {
            "status": "max_steps_reached",
            "steps": self.step_counter,
            "summary": "Reached maximum allowed steps without definitive completion.",
            "final_url": self.page.url,
            "history": self.history,
        }
