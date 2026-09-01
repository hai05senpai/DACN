import asyncio
import sys
from pathlib import Path
from agent_core.engine import run_veriagent_audit, run_interactive_repl

def main():
    # File hợp đồng mặc định để test
    contract_file = "contracts/SimpleBank.sol"
    interactive_mode = False

    for argv in sys.argv[1:]:
        if argv == "--interactive" or argv == "-i":
            interactive_mode = True
        elif not argv.startswith("-"):
            contract_file = argv

    if not Path(contract_file).exists():
        print(f"❌ Lỗi: Không tìm thấy file hợp đồng tại '{contract_file}'")
        return

    if interactive_mode:
        asyncio.run(run_interactive_repl(contract_file))
    else:
        asyncio.run(run_veriagent_audit(contract_file))

if __name__ == "__main__":
    main()