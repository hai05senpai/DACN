from typing import List, Dict, Any

class IncrementalFindingsMemory:
    """Quản lý bộ nhớ tích lũy các phát hiện bảo mật trong phiên kiểm toán."""
    
    def __init__(self):
        self.findings: List[Dict[str, Any]] = []

    def add_finding(self, title: str, severity: str, description: str, evidence: str):
        """Thêm một phát hiện mới vào bộ nhớ."""
        finding = {
            "id": len(self.findings) + 1,
            "title": title,
            "severity": severity, # CRITICAL, HIGH, MEDIUM, LOW, INFO
            "description": description,
            "evidence": evidence
        }
        self.findings.append(finding)
        return finding

    def get_summary(self) -> str:
        """Xuất tóm tắt danh sách phát hiện hiện tại."""
        if not self.findings:
            return "Chưa ghi nhận lỗ hổng nào trong bộ nhớ."
        
        summary = "BỘ NHỚ LỖ HỔNG ĐÃ GHI NHẬN:\n"
        for f in self.findings:
            summary += f"- [{f['severity']}] #{f['id']} {f['title']}: {f['description']}\n  Bằng chứng: {f['evidence']}\n"
        return summary

    def clear(self):
        """Xóa bộ nhớ khi chuyển sang dự án mới."""
        self.findings = []