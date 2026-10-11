import google.auth

from typing import Annotated
from langchain.agents import create_agent
from agents.finance_agent.tools import describe_file, query_file
from agents.finance_agent.prompt import SYSTEM_PROMPT
from langchain_anthropic import ChatAnthropic
from credentials.credentials import get_claude_api_key
from langchain.tools import tool,InjectedToolCallId
from langgraph.types import Command
from langchain.messages import ToolMessage

_, PROJECT_ID = google.auth.default()

llm = ChatAnthropic(
        model="claude-sonnet-5-5",
        api_key=get_claude_api_key(),
        max_retries=2,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
    )

subagent = create_agent(
    llm,
    tools=[query_file,describe_file],
    system_prompt=SYSTEM_PROMPT
)


@tool(
    "financeagent",
    description=(
        "Financial and sales data expert. Use it to retrieve concrete figures: "
        "sales and revenue (total, by customer, by product, by period), orders, "
        "invoices, payments, average ticket, costs, margins and cash flow. "
        "Best for questions like 'how much did X buy' or 'what were sales in March'. "
        "Not for trend analysis, segmentation or explaining why numbers changed "
        "(use biagent for that). Send a complete, self-contained query with any "
        "customer emails, IDs and date ranges in plain text; this agent cannot "
        "see the conversation."
    ),
)
def call_finance_agent(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
)-> Command:
    result = subagent.invoke({"messages": [{"role": "user", "content": query}]})
    return Command(update={
        "messages": [
            ToolMessage(
                content=result["messages"][-1].content,
                tool_call_id=tool_call_id
            )
        ]
    })
