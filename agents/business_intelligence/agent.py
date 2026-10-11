from typing import Annotated
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from credentials.credentials import get_claude_api_key
from agents.business_intelligence.tools import describe_file, query_file
from agents.business_intelligence.prompt import SYSTEM_PROMPT
from langchain.tools import tool,InjectedToolCallId
from langgraph.types import Command
from langchain.messages import ToolMessage


llm = ChatAnthropic(
        model="claude-sonnet-5-5",
        api_key=get_claude_api_key(),
        max_retries=2,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
    )

subagent = create_agent(
    llm,
    tools=[describe_file, query_file],
    system_prompt=SYSTEM_PROMPT
)

@tool(
    "biagent",
    description=(
        "Business intelligence analyst. Use it for analysis and insights: trends "
        "and evolution over time, comparisons between periods, customers or products, "
        "KPIs, customer segmentation, behavior patterns, rankings, anomalies and "
        "explanations of why metrics changed. Best for questions like 'how are sales "
        "evolving' or 'which customers are declining'. Not for simply looking up "
        "a raw figure (use financeagent for that). If a question needs both the "
        "figures and their analysis, call both agents. Send a complete, "
        "self-contained query; this agent cannot see the conversation."
    ),
)
def call_bi_agent(
    query: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    result = subagent.invoke({"messages": [{"role": "user", "content": query}]})
    return Command(update={
        "messages": [
            ToolMessage(
                content=result["messages"][-1].content,
                tool_call_id=tool_call_id
            )
        ]
    })