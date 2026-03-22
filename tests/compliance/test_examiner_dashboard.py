"""
Tests for examiner dashboard engine.
"""

from __future__ import annotations

import pytest

from offchain.services import audit
from compliance.examiner_dashboard.engine import ExaminerDashboardEngine


class TestExaminerDashboard:
    """Tests for examiner-facing reporting."""

    @pytest.mark.asyncio
    async def test_generate_summary(self):
        audit.clear_log()
        dashboard = ExaminerDashboardEngine()
        summary = await dashboard.generate_dashboard_summary(
            total_supply_usd=10_000_000.0,
            total_reserves_usd=10_100_000.0,
            backing_ratio=1.01,
            reserve_proof_status="VERIFIED",
            control_effectiveness_pct=92.5,
        )
        assert summary.backing_ratio == 1.01
        assert summary.reserve_proof_status == "VERIFIED"

    @pytest.mark.asyncio
    async def test_generate_report(self):
        audit.clear_log()
        dashboard = ExaminerDashboardEngine()
        report = await dashboard.generate_report(
            report_type="CONTROL_MATRIX",
            title="Q1 2026 Control Effectiveness",
            content={"controls": 16, "passed": 16},
        )
        assert report.report_type == "CONTROL_MATRIX"
        assert report.generated_by == "CARI_PLATFORM"

    @pytest.mark.asyncio
    async def test_csv_export(self):
        dashboard = ExaminerDashboardEngine()
        data = [
            {"name": "Control A", "status": "PASSED", "effectiveness": 95},
            {"name": "Control B", "status": "PASSED", "effectiveness": 90},
        ]
        csv = await dashboard.export_csv(data)
        assert "name" in csv
        assert "Control A" in csv
        lines = csv.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows

    @pytest.mark.asyncio
    async def test_empty_csv(self):
        dashboard = ExaminerDashboardEngine()
        csv = await dashboard.export_csv([])
        assert csv == ""

    @pytest.mark.asyncio
    async def test_report_history(self):
        audit.clear_log()
        dashboard = ExaminerDashboardEngine()
        await dashboard.generate_report(
            report_type="AML_SUMMARY", title="AML Report", content={}
        )
        await dashboard.generate_report(
            report_type="RISK_REGISTER", title="Risk Report", content={}
        )
        all_reports = dashboard.get_reports()
        assert len(all_reports) == 2
        aml_reports = dashboard.get_reports(report_type="AML_SUMMARY")
        assert len(aml_reports) == 1
