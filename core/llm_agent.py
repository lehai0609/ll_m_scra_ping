"""LLM navigation intelligence."""
# core/llm_agent.py
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import openai

from config.settings import ScrapingConfig

logger = logging.getLogger("layout_aware_scraper.llm_agent")

class ActionType(Enum):
    """Types of actions the LLM agent can recommend"""
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    WAIT = "wait"
    NAVIGATE = "navigate"
    EXTRACT = "extract"
    ERROR = "error"

@dataclass
class NavigationAction:
    """Represents an action recommended by the LLM agent"""
    action_type: ActionType
    target_description: str
    parameters: Dict[str, Any]
    confidence: float
    reasoning: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'action_type': self.action_type.value,
            'target_description': self.target_description,
            'parameters': self.parameters,
            'confidence': self.confidence,
            'reasoning': self.reasoning
        }

class LLMNavigationAgent:
    """LLM-powered intelligent navigation agent for dynamic web content"""
    
    def __init__(self, config: ScrapingConfig):
        self.config = config
        self.client = openai.AsyncOpenAI(api_key=config.openai_api_key)
        self.conversation_history: List[Dict[str, str]] = []
        
    async def analyze_page_and_plan_action(
        self, 
        accessibility_tree: Dict[str, Any],
        current_url: str,
        navigation_goal: str,
        page_content_summary: Optional[str] = None
    ) -> NavigationAction:
        """Analyze page structure and plan the next navigation action"""
        
        try:
            # Build context for LLM
            context = self._build_navigation_context(
                accessibility_tree, current_url, navigation_goal, page_content_summary
            )
            
            # Get LLM decision
            response = await self._query_llm_for_action(context)
            
            # Parse and validate response
            action = self._parse_llm_response(response)
            
            # Update conversation history
            self._update_conversation_history(context, response)
            
            logger.info(f"LLM recommended action: {action.action_type.value} - {action.target_description}")
            logger.debug(f"Action reasoning: {action.reasoning}")
            
            return action
            
        except Exception as e:
            logger.error(f"Error in LLM navigation planning: {e}")
            return NavigationAction(
                action_type=ActionType.ERROR,
                target_description="LLM analysis failed",
                parameters={},
                confidence=0.0,
                reasoning=f"Error: {str(e)}"
            )
    
    def _build_navigation_context(
        self,
        accessibility_tree: Dict[str, Any],
        current_url: str,
        navigation_goal: str,
        page_content_summary: Optional[str] = None
    ) -> str:
        """Build comprehensive context for LLM analysis"""
        
        context_parts = [
            "# Web Page Navigation Analysis",
            "",
            f"**Current URL:** {current_url}",
            f"**Navigation Goal:** {navigation_goal}",
            "",
            "## Page Structure (Accessibility Tree)",
            "```json",
            json.dumps(accessibility_tree, indent=2)[:2000] + ("..." if len(json.dumps(accessibility_tree)) > 2000 else ""),
            "```",
            ""
        ]
        
        if page_content_summary:
            context_parts.extend([
                "## Page Content Summary",
                page_content_summary,
                ""
            ])
        
        # Add conversation history for context
        if self.conversation_history:
            context_parts.extend([
                "## Recent Navigation History",
                *[f"- {entry['goal']}: {entry['action']}" for entry in self.conversation_history[-3:]],
                ""
            ])
        
        context_parts.extend([
            "## Your Task",
            "Analyze the page structure and recommend the SINGLE BEST next action to achieve the navigation goal.",
            "Consider:",
            "- What interactive elements are available?",
            "- Which element best matches the navigation goal?",
            "- What's the most efficient path forward?",
            "- Are there any obvious obstacles or dynamic content loading?",
            "",
            "Respond with a JSON object containing:",
            '- "action_type": one of [click, type, scroll, wait, navigate, extract, error]',
            '- "target_description": clear description of the target element',
            '- "parameters": action-specific parameters (selector, text, direction, etc.)',
            '- "confidence": float 0-1 indicating confidence in this action',
            '- "reasoning": brief explanation of why this action was chosen',
            "",
            "Example response:",
            '```json',
            '{',
            '  "action_type": "click",',
            '  "target_description": "Discussion tab in main navigation",',
            '  "parameters": {"selector": "[role=tab][name*=Discussion]", "wait_after": 2000},',
            '  "confidence": 0.9,',
            '  "reasoning": "Discussion tab is clearly visible and matches navigation goal"',
            '}',
            '```'
        ])
        
        return "\n".join(context_parts)
    
    async def _query_llm_for_action(self, context: str) -> str:
        """Query LLM with navigation context and get action recommendation"""
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert web navigation agent. You understand web page structures "
                    "through accessibility trees and make intelligent decisions about how to navigate "
                    "to achieve specific goals. You are precise, efficient, and handle edge cases gracefully. "
                    "Always respond with valid JSON as specified in the prompt."
                )
            },
            {
                "role": "user",
                "content": context
            }
        ]
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                response_format={"type": "json_object"}
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            raise
    
    def _parse_llm_response(self, response: str) -> NavigationAction:
        """Parse and validate LLM response into NavigationAction"""
        
        try:
            data = json.loads(response)
            
            # Validate required fields
            required_fields = ['action_type', 'target_description', 'parameters', 'confidence', 'reasoning']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Parse action type
            action_type = ActionType(data['action_type'].lower())
            
            # Validate confidence
            confidence = float(data['confidence'])
            if not 0 <= confidence <= 1:
                raise ValueError(f"Confidence must be between 0 and 1, got: {confidence}")
            
            # Ensure parameters is a dict
            parameters = data['parameters'] if isinstance(data['parameters'], dict) else {}
            
            return NavigationAction(
                action_type=action_type,
                target_description=str(data['target_description']),
                parameters=parameters,
                confidence=confidence,
                reasoning=str(data['reasoning'])
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from LLM: {e}")
            raise ValueError(f"LLM returned invalid JSON: {e}")
        
        except ValueError as e:
            logger.error(f"Invalid LLM response format: {e}")
            raise ValueError(f"Invalid LLM response: {e}")
        
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            raise ValueError(f"Failed to parse LLM response: {e}")
    
    def _update_conversation_history(self, context: str, response: str) -> None:
        """Update conversation history for context in future requests"""
        
        # Extract goal and action for summary
        try:
            lines = context.split('\n')
            goal = next((line.split('**Navigation Goal:** ')[1] for line in lines if '**Navigation Goal:**' in line), "Unknown")
            
            action_data = json.loads(response)
            action_summary = f"{action_data['action_type']} -> {action_data['target_description']}"
            
            self.conversation_history.append({
                'goal': goal,
                'action': action_summary
            })
            
            # Keep only recent history to manage token usage
            if len(self.conversation_history) > 10:
                self.conversation_history = self.conversation_history[-10:]
                
        except Exception as e:
            logger.debug(f"Could not update conversation history: {e}")
    
    async def analyze_content_structure(
        self, 
        page_content: str, 
        extraction_goal: str
    ) -> Dict[str, Any]:
        """Analyze page content and identify extraction targets"""
        
        context = f"""
# Content Analysis Task

**Extraction Goal:** {extraction_goal}

## Page Content (First 3000 characters)
```
{page_content[:3000]}
```

## Your Task
Analyze the content and identify:
1. **Content Sections**: What major sections/categories exist?
2. **Data Patterns**: What structured data is available?
3. **Navigation Elements**: What links, buttons, or interactive elements are present?
4. **Extraction Targets**: Which specific elements match the extraction goal?

Respond with JSON containing:
- "sections": array of identified content sections
- "extraction_targets": array of elements matching the goal
- "next_actions": recommended actions to gather more content
- "confidence": overall confidence in the analysis

Example:
```json
{{
  "sections": ["overview", "timeline", "discussion"],
  "extraction_targets": [
    {{"type": "title", "content": "Competition Title", "location": "h1 element"}},
    {{"type": "description", "content": "Main description...", "location": "description section"}}
  ],
  "next_actions": ["click_discussion_tab", "scroll_for_more_content"],
  "confidence": 0.85
}}
```
        """
        
        try:
            response = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=[
                    {"role": "system", "content": "You are an expert content analyst specializing in web page structure and data extraction."},
                    {"role": "user", "content": context}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                response_format={"type": "json_object"}
            )
            
            return json.loads(response.choices[0].message.content.strip())
            
        except Exception as e:
            logger.error(f"Error in content analysis: {e}")
            return {
                "sections": [],
                "extraction_targets": [],
                "next_actions": [],
                "confidence": 0.0,
                "error": str(e)
            }
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the navigation conversation for debugging"""
        if not self.conversation_history:
            return "No navigation history"
        
        summary_parts = ["Navigation History:"]
        for i, entry in enumerate(self.conversation_history[-5:], 1):
            summary_parts.append(f"{i}. Goal: {entry['goal']} -> Action: {entry['action']}")
        
        return "\n".join(summary_parts)