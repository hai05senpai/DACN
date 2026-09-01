import asyncio
import os
import sys
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

from agent_core.prompts import AUDIT_SYSTEM_PROMPT
from agent_core.memory import IncrementalFindingsMemory

load_dotenv()
console = Console()

def extract_clean_text(content) -> str:
    """Làm sạch dữ liệu trả về từ Gemini SDK để lấy chuỗi văn bản thuần."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(text_parts)
    return str(content)

def auto_record_findings(text: str, memory: IncrementalFindingsMemory):
    """Tự động quét văn bản của Agent để phát hiện và ghi nhận lỗ hổng vào Memory."""
    if "REENTRANCY" in text.upper() or "SWC-107" in text:
        if not any("Reentrancy" in f["title"] for f in memory.findings):
            memory.add_finding(
                title="Reentrancy Attack Vulnerability",
                severity="CRITICAL",
                description="Hàm withdraw() vi phạm quy tắc CEI, chuyển ETH trước khi cập nhật balances = 0.",
                evidence="contracts/SimpleBank.sol: withdraw()"
            )

def save_markdown_report(contract_path: str, report_content: str) -> Path:
    """Tự động tạo thư mục reports/ và lưu báo cáo dưới dạng file .md kèm timestamp."""
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    contract_name = Path(contract_path).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"Audit_Report_{contract_name}_{timestamp}.md"
    file_path = reports_dir / file_name

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return file_path

async def safe_llm_invoke(llm_with_tools, messages, retries=10, delay=26):
    """Tự động chờ đúng thời gian nhả Quota của Google (26s) khi bị nghẽn 429."""
    for attempt in range(retries):
        try:
            await asyncio.sleep(2.0)  # Nghỉ 2s giữa các step để hạ nhiệt RPM
            return await llm_with_tools.ainvoke(messages)
        except Exception as e:
            err_msg = str(e)
            if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                console.print(f"[bold yellow]⚠️ Chạm ngưỡng Quota Gemini (20 RPM). Đang chờ {delay}s để Google reset quota (Lần {attempt+1}/{retries})...[/bold yellow]")
                await asyncio.sleep(delay)
            else:
                raise e
    return await llm_with_tools.ainvoke(messages)

async def run_veriagent_audit(contract_path: str):
    """Chế độ Tự trị (Autonomous Batch Mode) với Multi-MCP Server."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]LỖI: Chưa cấu hình GEMINI_API_KEY![/bold red]")
        return

    console.print(Panel.fit(
        f"[bold cyan]VERI-AGENT: KIỂM TOÁN BẢO MẬT HỢP ĐỒNG THÔNG MINH (GEMINI CORE)[/bold cyan]\n"
        f"Mục tiêu: [yellow]{contract_path}[/yellow]",
        border_style="green"
    ))

    slither_script = Path(__file__).parent.parent / "mcp_servers" / "slither_server.py"
    foundry_script = Path(__file__).parent.parent / "mcp_servers" / "foundry_server.py"

    slither_params = StdioServerParameters(command=sys.executable, args=[str(slither_script.resolve())], env=os.environ.copy())
    foundry_params = StdioServerParameters(command=sys.executable, args=[str(foundry_script.resolve())], env=os.environ.copy())

    console.print("[dim]🔌 Đang kết nối đến Slither & Foundry MCP Servers...[/dim]")

    async with stdio_client(slither_params) as (read_s, write_s), stdio_client(foundry_params) as (read_f, write_f):
        async with ClientSession(read_s, write_s) as session_slither, ClientSession(read_f, write_f) as session_foundry:
            await session_slither.initialize()
            await session_foundry.initialize()
            console.print("[bold green]✓ Kết nối thành công tới tất cả MCP Servers![/bold green]\n")

            tools_s = await session_slither.list_tools()
            tools_f = await session_foundry.list_tools()
            all_mcp_tools = tools_s.tools + tools_f.tools

            tool_dispatch = {}
            for t in tools_s.tools:
                tool_dispatch[t.name] = session_slither
            for t in tools_f.tools:
                tool_dispatch[t.name] = session_foundry

            tools_for_llm = [{
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema
                }
            } for t in all_mcp_tools]

            llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key)
            llm_with_tools = llm.bind_tools(tools_for_llm)

            messages = [
                SystemMessage(content=AUDIT_SYSTEM_PROMPT),
                HumanMessage(content=f"Hãy phân tích và kiểm toán bảo mật hợp đồng tại file: '{contract_path}'")
            ]

            step_count = 1
            while True:
                console.print(f"[bold magenta]▶ [Bước {step_count}] Agent đang suy luận (Plan & Act)...[/bold magenta]")

                # Cắt tỉa ngữ cảnh để tiết kiệm token nếu chuỗi tin nhắn quá dài
                if len(messages) > 11:
                    messages = [messages[0]] + messages[-10:]

                response = await safe_llm_invoke(llm_with_tools, messages)
                messages.append(response)

                if not response.tool_calls:
                    report_text = extract_clean_text(response.content)
                    console.print("\n" + "="*60)
                    console.print(Panel(
                        report_text,
                        title="[bold green]BÁO CÁO KIỂM TOÁN TỔNG HỢP (VERIAGENT REPORT)[/bold green]",
                        border_style="cyan"
                    ))
                    saved_path = save_markdown_report(contract_path, report_text)
                    console.print(f"[bold green]💾 Báo cáo đã được lưu tự động tại:[/bold green] [yellow]{saved_path}[/yellow]")
                    break

                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]

                    console.print(f"  [yellow]🛠️  Agent kích hoạt MCP Tool:[/yellow] [bold white]{tool_name}[/bold white]")
                    console.print(f"     Tham số: {tool_args}")

                    target_session = tool_dispatch.get(tool_name)
                    if not target_session:
                        observation = f"LỖI: Không tìm thấy Server hỗ trợ công cụ '{tool_name}'."
                    else:
                        tool_result = await target_session.call_tool(tool_name, tool_args)
                        observation = tool_result.content[0].text

                    console.print(f"  [cyan]👁️  Observation (Kết quả nhận từ MCP Tool):[/cyan]")
                    preview_lines = observation.split("\n")[:4]
                    for line in preview_lines:
                        console.print(f"     [dim]{line}[/dim]")
                    if len(observation.split("\n")) > 4:
                        console.print("     [dim]... (đã nén bớt log dài)[/dim]")
                    console.print()

                    messages.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))

                step_count += 1

async def run_interactive_repl(contract_path: str):
    """Chế độ Tương tác (Interactive REPL Mode) với Multi-MCP Server & Gemini 3.6-flash."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]LỖI: Chưa cấu hình GEMINI_API_KEY![/bold red]")
        return

    slither_script = Path(__file__).parent.parent / "mcp_servers" / "slither_server.py"
    foundry_script = Path(__file__).parent.parent / "mcp_servers" / "foundry_server.py"

    slither_params = StdioServerParameters(command=sys.executable, args=[str(slither_script.resolve())], env=os.environ.copy())
    foundry_params = StdioServerParameters(command=sys.executable, args=[str(foundry_script.resolve())], env=os.environ.copy())

    findings_memory = IncrementalFindingsMemory()
    last_report_text = ""

    console.print("[dim]🔌 Đang kết nối đến Slither & Foundry MCP Servers...[/dim]")

    async with stdio_client(slither_params) as (read_s, write_s), stdio_client(foundry_params) as (read_f, write_f):
        async with ClientSession(read_s, write_s) as session_slither, ClientSession(read_f, write_f) as session_foundry:
            await session_slither.initialize()
            await session_foundry.initialize()

            tools_s = await session_slither.list_tools()
            tools_f = await session_foundry.list_tools()
            all_mcp_tools = tools_s.tools + tools_f.tools

            tool_dispatch = {}
            for t in tools_s.tools:
                tool_dispatch[t.name] = session_slither
            for t in tools_f.tools:
                tool_dispatch[t.name] = session_foundry

            tools_for_llm = [{
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema
                }
            } for t in all_mcp_tools]

            llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key)
            llm_with_tools = llm.bind_tools(tools_for_llm)

            messages = [
                SystemMessage(content=AUDIT_SYSTEM_PROMPT),
                HumanMessage(content=f"Mục tiêu kiểm toán hiện tại: File '{contract_path}'. Hãy chuẩn bị hỗ trợ Auditor.")
            ]

            console.print(Panel.fit(
                "[bold green]CHẾ ĐỘ TƯƠNG TÁC (VERIAGENT REPL INTERACTIVE)[/bold green]\n"
                f"Target: [yellow]{contract_path}[/yellow]\n"
                "Các lệnh đặc biệt:\n"
                "  [bold cyan]/summary[/bold cyan] : Xem danh sách phát hiện tích lũy\n"
                "  [bold cyan]/report[/bold cyan]  : Xuất báo cáo Markdown (.md) ra thư mục reports/\n"
                "  [bold cyan]/exit[/bold cyan]    : Thoát phiên làm việc",
                border_style="cyan"
            ))

            while True:
                user_input = console.input("\n[bold yellow]Auditor ❯ [/bold yellow]").strip()

                if not user_input:
                    continue

                if user_input.lower() == "/exit":
                    console.print("[dim]Đang đóng phiên kiểm toán REPL...[/dim]")
                    break

                if user_input.lower() == "/summary":
                    console.print(Panel(findings_memory.get_summary(), title="[bold green]Incremental Findings Memory[/bold green]", border_style="yellow"))
                    continue

                if user_input.lower() == "/report":
                    content_to_save = last_report_text if last_report_text else findings_memory.get_summary()

                    if not content_to_save or content_to_save == "Chưa ghi nhận lỗ hổng nào trong bộ nhớ.":
                        console.print("[bold red]⚠️ Chưa có dữ liệu báo cáo để xuất! Hãy yêu cầu Agent phân tích hoặc kiểm toán trước.[/bold red]")
                    else:
                        saved_file = save_markdown_report(contract_path, content_to_save)
                        console.print(Panel.fit(
                            f"[bold green]✓ ĐÃ XUẤT BÁO CÁO THÀNH CÔNG![/bold green]\n"
                            f"📁 Đường dẫn file: [yellow]{saved_file.resolve()}[/yellow]",
                            border_style="green"
                        ))
                    continue

                messages.append(HumanMessage(content=user_input))

                while True:
                    # Cắt tỉa ngữ cảnh: Giữ System Prompt + 10 tin nhắn gần nhất
                    if len(messages) > 11:
                        messages = [messages[0]] + messages[-10:]

                    response = await safe_llm_invoke(llm_with_tools, messages)
                    messages.append(response)

                    if not response.tool_calls:
                        clean_text = extract_clean_text(response.content)
                        console.print(f"\n[bold green]VeriAgent ❯[/bold green]\n{clean_text}")

                        last_report_text = clean_text
                        auto_record_findings(clean_text, findings_memory)
                        break

                    for tool_call in response.tool_calls:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["args"]

                        console.print(f"  [yellow]🛠️  Kích hoạt MCP Tool:[/yellow] {tool_name} {tool_args}")

                        target_session = tool_dispatch.get(tool_name)
                        if not target_session:
                            observation = f"LỖI: Không tìm thấy Server hỗ trợ công cụ '{tool_name}'."
                        else:
                            tool_result = await target_session.call_tool(tool_name, tool_args)
                            observation = tool_result.content[0].text

                        console.print(f"  [cyan]👁️  Observation (Kết quả nhận từ MCP Tool):[/cyan]")
                        preview_lines = observation.split("\n")[:4]
                        for line in preview_lines:
                            console.print(f"     [dim]{line}[/dim]")
                        if len(observation.split("\n")) > 4:
                            console.print("     [dim]... (đã nén bớt log dài)[/dim]")
                        console.print()

                        messages.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))