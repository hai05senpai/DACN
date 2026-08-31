import json
import subprocess
from pathlib import Path
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("VeriAgent-Slither-Server")

@mcp.tool()
def run_slither_analysis(contract_path: str) -> str:
    """
    Thực thi phân tích tĩnh Slither trên file Smart Contract Solidity.
    Nếu Slither thiếu trình biên dịch, công cụ sẽ trích xuất mã nguồn và phân tích cấu trúc chi tiết cho Agent.
    """
    file_path = Path(contract_path).resolve()
    if not file_path.exists():
        return f"LỖI: Không tìm thấy file hợp đồng tại '{contract_path}'."

    # Đọc nội dung file contract
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            code_content = f.read()
    except Exception as e:
        code_content = f"Không thể đọc file: {e}"

    # 1. Thử chạy Slither CLI
    slither_findings = ""
    try:
        process = subprocess.run(
            f'slither "{str(file_path)}" --json -',
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        output = process.stdout.strip() if process.stdout.strip() else process.stderr.strip()

        if output:
            try:
                data = json.loads(output)
                if data.get("success", False):
                    detectors = data.get("results", {}).get("detectors", [])
                    findings = []
                    for idx, d in enumerate(detectors, 1):
                        findings.append(
                            f"[{idx}] Check: {d.get('check', 'Unknown')}\n"
                            f"    - Impact: {d.get('impact', 'Informational')}\n"
                            f"    - Description: {d.get('description', '').strip()}\n"
                        )
                    if findings:
                        slither_findings = "\n".join(findings)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    # 2. Nếu Slither không trả dữ liệu (do thiếu solc), trả về kết quả Recon mã nguồn đầy đủ
    if not slither_findings:
        return (
            f"--- KẾT QUẢ RECON & MÃ NGUỒN TARGET ({file_path.name}) ---\n"
            f"CẢNH BÁO TOOL: Slither CLI thiếu trình biên dịch solc local. Đã trích xuất mã nguồn thực tế để kiểm toán:\n\n"
            f"```solidity\n{code_content}\n```\n\n"
            f"HƯỚNG DẪN AGENT: Hãy phân tích kỹ mã nguồn trên, tập trung kiểm tra các lỗi Reentrancy (State updates after external call), Access Control, và Unchecked Transfers."
        )

    return f"--- KẾT QUẢ QUÉT TĨNH SLITHER ---\n" + slither_findings

if __name__ == "__main__":
    mcp.run(transport="stdio")