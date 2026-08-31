import asyncio
import sys
from pathlib import Path
from agent_core.engine import run_veriagent_audit

def main():
    # File hợp đồng mặc định để test
    contract_file = "contracts/SimpleBank.sol"

    # Cho phép truyền file qua dòng lệnh (vd: python main.py contracts/MyToken.sol)
    if len(sys.argv) > 1:
        contract_file = sys.argv[1]

    if not Path(contract_file).exists():
        print(f"❌ Lỗi: Không tìm thấy file hợp đồng tại '{contract_file}'")
        return

    # Chạy vòng lặp Async của Agent
    asyncio.run(run_veriagent_audit(contract_file))

if __name__ == "__main__":
    main()