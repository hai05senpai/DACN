import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agent_core.prompts import AUDIT_SYSTEM_PROMPT

load_dotenv()
console = Console()

async def run_veriagent_audit(contract_path: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]LỖI: Chưa cấu hình GEMINI_API_KEY trong file .env![/bold red]")
        return

    console.print(Panel.fit(
        f"[bold cyan]VERI-AGENT: KIỂM TOÁN BẢO MẬT HỢP ĐỒNG THÔNG MINH (GEMINI CORE)[/bold cyan]\n"
        f"Mục tiêu: [yellow]{contract_path}[/yellow]",
        border_style="green"
    ))

    mcp_server_script = Path(__file__).parent.parent / "mcp_servers" / "slither_server.py"

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(mcp_server_script.resolve())],
        env=os.environ.copy()
    )

    console.print("[dim]🔌 Đang kết nối đến Slither MCP Server...[/dim]")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            console.print("[bold green]✓ Kết nối MCP Server thành công![/bold green]\n")

            mcp_tools = await session.list_tools()
            tools_for_llm = []
            for tool in mcp_tools.tools:
                tools_for_llm.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema
                    }
                })

            llm = ChatGoogleGenerativeAI(
                model="gemini-3.6-flash",
                google_api_key=api_key
            )
            llm_with_tools = llm.bind_tools(tools_for_llm)

            messages = [
                SystemMessage(content=AUDIT_SYSTEM_PROMPT),
                HumanMessage(content=f"Hãy phân tích và kiểm toán bảo mật hợp đồng tại file: '{contract_path}'")
            ]

            step_count = 1
            while True:
                console.print(f"[bold magenta]▶ [Bước {step_count}] Agent đang suy luận (Plan & Act)...[/bold magenta]")
                
                response = await llm_with_tools.ainvoke(messages)
                messages.append(response)

                if not response.tool_calls:
                    # Trích xuất dạng chuỗi text an toàn để rich Panel render không bị lỗi
                    report_text = response.content
                    if isinstance(report_text, list):
                        # Lấy phần text từ danh sách các block nếu SDK trả về list
                        report_text = "\n".join([item.get("text", "") if isinstance(item, dict) else str(item) for item in report_text])
                    
                    console.print("\n" + "="*60)
                    console.print(Panel(
                        str(report_text),
                        title="[bold green]BÁO CÁO KIỂM TOÁN TỔNG HỢP (VERIAGENT REPORT)[/bold green]",
                        border_style="cyan"
                    ))
                    break

                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]

                    console.print(f"  [yellow]🛠️  Agent kích hoạt MCP Tool:[/yellow] [bold white]{tool_name}[/bold white]")
                    console.print(f"     Tham số: {tool_args}")

                    tool_result = await session.call_tool(tool_name, tool_args)
                    observation = tool_result.content[0].text

                    console.print(f"  [cyan]👁️  Observation (Kết quả nhận từ MCP Tool):[/cyan]")
                    preview_lines = observation.split("\n")[:4]
                    for line in preview_lines:
                        console.print(f"     [dim]{line}[/dim]")
                    if len(observation.split("\n")) > 4:
                        console.print("     [dim]... (đã nén bớt log dài)[/dim]")
                    console.print()

                    messages.append(ToolMessage(
                        content=observation,
                        tool_call_id=tool_call["id"]
                    ))

                step_count += 1

if __name__ == "__main__":
    test_contract = "contracts/SimpleBank.sol"
    asyncio.run(run_veriagent_audit(test_contract))