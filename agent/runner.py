import json
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

from agent.tools import TOOL_REGISTRY
from agent.prompt import SYSTEM_PROMPT

# Initialize OpenAI client (expects OPENAI_API_KEY environment variable)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Define OpenAI function-calling tool schemas mapped to our allowlist
OPENAI_TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_customer_account",
            "description": "Retrieve customer account details securely.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The unique identifier of the customer."}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_history",
            "description": "Retrieve all order records associated with a customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The unique identifier of the customer."}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_delivery_status",
            "description": "Check the delivery and shipping status of an order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The unique identifier of the order."}
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_billing_history",
            "description": "Retrieve invoice and billing history for a customer's orders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "The unique identifier of the customer."}
                },
                "required": ["customer_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_refund_eligibility",
            "description": "Evaluate refund eligibility using deterministic policy rules (return windows & order status).",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order ID to evaluate."},
                    "amount": {"type": "number", "description": "The requested refund amount."}
                },
                "required": ["order_id", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_return_request",
            "description": "Create a return request with idempotency protection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The unique order ID."},
                    "customer_id": {"type": "string", "description": "The customer ID."},
                    "reason": {"type": "string", "description": "Reason for the return."},
                    "idempotency_key": {"type": "string", "description": "Unique UUID idempotency key."}
                },
                "required": ["order_id", "customer_id", "reason", "idempotency_key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Process or queue a refund based on deterministic threshold policies with idempotency guards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The unique order ID."},
                    "customer_id": {"type": "string", "description": "The customer ID."},
                    "amount": {"type": "number", "description": "The refund amount."},
                    "reason": {"type": "string", "description": "Reason for the refund."},
                    "idempotency_key": {"type": "string", "description": "Unique UUID idempotency key for financial safety."}
                },
                "required": ["order_id", "customer_id", "amount", "reason", "idempotency_key"]
            }
        }
    }
]

def run_agent_turn(user_message: str, chat_history: Optional[List[Dict[str, Any]]] = None, max_iterations: int = 5) -> str:
    """
    Executes an agent conversation turn with a hard iteration cap and tool orchestration loop.
    """
    if chat_history is None:
        chat_history = []

    # Initialize message list with centralized system prompt and history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_history
    messages.append({"role": "user", "content": user_message})

    for iteration in range(max_iterations):
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=OPENAI_TOOLS_SPEC,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        messages.append(response_message)

        # If the model didn't call any tools, we have our final text response
        if not response_message.tool_calls:
            return response_message.content

        # Process each tool call requested by the model
        for tool_call in response_message.tool_calls:
            function_name = tool_call.function.name
            function_args_str = tool_call.function.arguments

            if function_name not in TOOL_REGISTRY:
                tool_output = {"success": False, "error": f"Tool '{function_name}' is not allowed or registered."}
            else:
                func, pydantic_validator = TOOL_REGISTRY[function_name]
                try:
                    # Parse and validate arguments using Pydantic
                    raw_args = json.loads(function_args_str)
                    validated_args = pydantic_validator(**raw_args)
                    
                    # Execute the tool function
                    tool_output = func(**validated_args.model_dump())
                except Exception as e:
                    tool_output = {"success": False, "error": f"Argument validation or execution failed: {str(e)}"}

            # Append tool execution result back to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_output)
            })

    # Fallback if iteration limit is breached
    return "I apologize, but I encountered an issue completing your request due to complexity limits. Please try again or speak with a support supervisor."
