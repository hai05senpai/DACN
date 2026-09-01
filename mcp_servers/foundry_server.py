import os
import subprocess
from pathlib import Path
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("VeriAgent-Foundry-Server")

TEST_DIR = Path("test")

@mcp.tool()
def write_foundry_poc(test_filename: str, poc_code: str) -> str:
    """
    Tạo hoặc ghi đè một file Solidity PoC Test (.t.sol) trong thư mục test/.
    Dùng để viết kịch bản khai thác lỗ hổng bằng Foundry.
    """
    try:
        TEST_DIR.mkdir(parents=True, exist_ok=True)
        
        if not test_filename.endswith(".t.sol"):
            test_filename += ".t.sol"

        file_path = TEST_DIR / test_filename
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(poc_code)

        return f"✓ Đã ghi thành công file PoC Test tại '{file_path}'"
    except Exception as e:
        return f"LỖI khi ghi file PoC Test: {e}"

@mcp.tool()
def run_foundry_test(test_match: str = "") -> str:
    """
    Thực thi lệnh 'forge test' để chạy các bài test xác minh PoC.
    Nếu truyền test_match (ví dụ: 'testReentrancy'), forge sẽ chỉ chạy hàm test đó.
    """
    try:
        cmd = "forge test --match-test " + test_match if test_match else "forge test"
        cmd += " -vvvv" # Hiện log chi tiết trace giao dịch

        process = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        stdout = process.stdout.strip()
        stderr = process.stderr.strip()
        
        output = stdout if stdout else stderr
        if not output:
            return "CẢNH BÁO TOOL: Foundry (forge) không trả về dữ liệu. Hãy đảm bảo Foundry đã được cài đặt trên máy (https://getfoundry.sh)."

        return f"--- KẾT QUẢ CHẠY FORGE TEST ---\n{output}"
    except Exception as e:
        return f"LỖI khi thực thi forge test: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")