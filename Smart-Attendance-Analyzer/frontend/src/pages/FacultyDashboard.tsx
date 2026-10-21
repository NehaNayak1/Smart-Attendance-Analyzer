/**
 * pages/FacultyDashboard.tsx
 * =============================
 * The primary faculty-facing page: totals, below-75% count, at-risk count,
 * department filter, attendance entry modal trigger, CSV upload trigger,
 * What-If simulator modal trigger, immediate attention interventions,
 * searchable student risk table, department/subject comparisons, and report export.
 */

import { useEffect, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Calculator,
  Download,
  Filter,
  Percent,
  PlusCircle,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import { downloadBlob, exportApi, facultyApi, getErrorMessage } from "@/services/api";
import type { FacultyDashboard as FacultyDashboardType, StudentSummary } from "@/types";
import { PageLoader } from "@/components/Loader";
import { ErrorState } from "@/components/EmptyState";
import { SectionCard, StatCard } from "@/components/Card";
import { RiskBadge, TrendBadge } from "@/components/Badge";
import { RiskLedgerStrip } from "@/components/RiskLedgerStrip";
import { AttendanceBarChart, type BarDatum } from "@/charts/AttendanceBarChart";
import { FacultyAttendanceModal } from "@/components/FacultyAttendanceModal";
import { WhatIfSimulatorModal } from "@/components/WhatIfSimulatorModal";
import { DEPARTMENTS } from "@/lib/constants";
import { toast } from "@/lib/toast";

export default function FacultyDashboard() {
  const [data, setData] = useState<FacultyDashboardType | null>(null);
  const [department, setDepartment] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"pdf" | "csv" | null>(null);

  // Modals state
  const [isAttendanceModalOpen, setIsAttendanceModalOpen] = useState(false);
  const [isWhatIfModalOpen, setIsWhatIfModalOpen] = useState(false);
  const [selectedStudentForWhatIf, setSelectedStudentForWhatIf] = useState<string>("");

  // Student table filters
  const [searchQuery, setSearchQuery] = useState("");
  const [riskFilter, setRiskFilter] = useState<string>("all");

  async function loadDashboard(dept: string) {
    setIsLoading(true);
    setError(null);
    try {
      const result = await facultyApi.getDashboard(dept || undefined);
      setData(result);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard(department);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [department]);

  async function handleDownload(format: "pdf" | "csv") {
    setDownloading(format);
    try {
      const blob = await exportApi.facultyReport(format, department || undefined);
      downloadBlob(blob, `faculty_report.${format}`);
      toast.success(`Report downloaded as ${format.toUpperCase()}.`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDownloading(null);
    }
  }

  function handleOpenWhatIf(studentCode?: string) {
    setSelectedStudentForWhatIf(studentCode || "");
    setIsWhatIfModalOpen(true);
  }

  if (isLoading && !data) return <PageLoader label="Loading faculty dashboard..." />;
  if (error && !data) return <ErrorState message={error} onRetry={() => loadDashboard(department)} />;
  if (!data) return null;

  const departmentBars: BarDatum[] = data.department_stats.map((d) => ({ label: d.department, value: d.average_attendance }));
  const subjectBars: BarDatum[] = data.subject_stats.map((s) => ({ label: s.subject_name, value: s.average_attendance }));

  // Combined list of students for main risk table
  const allTableStudents = [...data.top_defaulters, ...data.students_declining];
  // Deduplicate by student_code
  const uniqueStudentsMap = new Map<string, StudentSummary>();
  allTableStudents.forEach((s) => uniqueStudentsMap.set(s.student_code, s));
  const uniqueStudents = Array.from(uniqueStudentsMap.values());

  const filteredStudents = uniqueStudents.filter((s) => {
    const matchesSearch =
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.student_code.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRisk =
      riskFilter === "all" ||
      (riskFilter === "high" && s.risk_level === "High Risk") ||
      (riskFilter === "medium" && s.risk_level === "Medium Risk") ||
      (riskFilter === "low" && s.risk_level === "Low Risk");
    return matchesSearch && matchesRisk;
  });

  return (
    <div className="animate-fade-in space-y-6 pb-10">
      {/* Modals */}
      <FacultyAttendanceModal
        isOpen={isAttendanceModalOpen}
        onClose={() => setIsAttendanceModalOpen(false)}
        onSuccess={() => loadDashboard(department)}
        defaultDepartment={department || "Computer Science"}
      />
      <WhatIfSimulatorModal
        isOpen={isWhatIfModalOpen}
        onClose={() => setIsWhatIfModalOpen(false)}
        initialStudentCode={selectedStudentForWhatIf}
      />

      {/* Header */}
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <p className="text-sm font-medium uppercase tracking-wide text-gold-dark dark:text-gold">
            Faculty Dashboard · Data Entry Authority
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold text-ink-900 dark:text-white">
            AI Attendance Risk Alert & Decision Center
          </h1>
        </div>

        {/* Header Actions */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setIsAttendanceModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg bg-gold px-4 py-2 text-sm font-bold text-ink-900 shadow-sm transition-all hover:bg-gold-light"
          >
            <UserCheck size={16} /> Record Attendance / Upload CSV
          </button>
          <button
            onClick={() => handleOpenWhatIf("")}
            className="flex items-center gap-1.5 rounded-lg border border-gold/40 bg-gold/10 px-3.5 py-2 text-sm font-semibold text-gold-dark dark:text-gold hover:bg-gold/20"
          >
            <Calculator size={16} /> What-If Simulator
          </button>
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="rounded-lg border border-ink-100 bg-white px-3 py-2 text-sm text-ink-800 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
          >
            <option value="">All Departments</option>
            {DEPARTMENTS.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <button
            onClick={() => handleDownload("csv")}
            disabled={downloading !== null}
            className="flex items-center gap-1.5 rounded-lg border border-ink-100 px-3 py-2 text-sm font-medium text-ink-700 transition-colors hover:bg-ink-50 disabled:opacity-60 dark:border-ink-700 dark:text-ink-100 dark:hover:bg-ink-800"
          >
            <Download size={14} /> CSV
          </button>
          <button
            onClick={() => handleDownload("pdf")}
            disabled={downloading !== null}
            className="flex items-center gap-1.5 rounded-lg bg-ink-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-ink-700 disabled:opacity-60 dark:bg-gold dark:text-ink-900 dark:hover:bg-gold-light"
          >
            <Download size={14} /> {downloading === "pdf" ? "Preparing..." : "Export PDF"}
          </button>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Total Students" value={data.total_students} icon={<Users size={16} />} accent="ink" />
        <StatCard
          label="Below 75%"
          value={data.students_below_75}
          icon={<AlertTriangle size={16} />}
          accent="danger"
          sublabel={`${((data.students_below_75 / Math.max(data.total_students, 1)) * 100).toFixed(1)}% of total`}
        />
        <StatCard
          label="At High Risk"
          value={data.risk_distribution.high_risk}
          icon={<ShieldAlert size={16} />}
          accent="danger"
          sublabel="Requires early intervention"
        />
        <StatCard label="Average Attendance" value={`${data.average_attendance}%`} icon={<Percent size={16} />} accent="ink" />
      </div>

      {/* Immediate Attention & AI Intervention Recommendations */}
      <div className="rounded-2xl border border-danger/30 bg-danger/5 p-6 dark:border-danger/20 dark:bg-danger/10">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-start gap-3">
            <div className="rounded-xl bg-danger/20 p-2.5 text-danger">
              <ShieldAlert size={24} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-ink-900 dark:text-white">Immediate Attention & Early Interventions</h3>
                <span className="rounded-full bg-danger px-2.5 py-0.5 text-xs font-bold text-white">
                  {data.risk_distribution.high_risk} Students at Risk
                </span>
              </div>
              <p className="mt-1 text-xs text-slate">
                AI Risk engine detected {data.risk_distribution.high_risk} high-risk students and {data.students_below_75} students currently below 75%.
              </p>
            </div>
          </div>
          <button
            onClick={() => handleOpenWhatIf("")}
            className="flex items-center justify-center gap-2 rounded-xl bg-danger px-4 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-danger/90"
          >
            <Calculator size={14} /> Run What-If Recovery Analysis
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 pt-4 border-t border-danger/20 text-xs">
          <div className="rounded-lg bg-white p-3 dark:bg-ink-800">
            <span className="font-bold text-danger">1. Early Counseling</span>
            <p className="mt-1 text-slate">Contact students with predicted forecast attendance &lt; 70% before term end.</p>
          </div>
          <div className="rounded-lg bg-white p-3 dark:bg-ink-800">
            <span className="font-bold text-amber-600 dark:text-amber-400">2. Attendance Recovery</span>
            <p className="mt-1 text-slate">Provide custom recovery plans specifying consecutive classes needed for 75%.</p>
          </div>
          <div className="rounded-lg bg-white p-3 dark:bg-ink-800">
            <span className="font-bold text-ink-900 dark:text-white">3. Declining Trend Watch</span>
            <p className="mt-1 text-slate">Monitor {data.students_declining.length} students whose attendance dropped continuously.</p>
          </div>
          <div className="rounded-lg bg-white p-3 dark:bg-ink-800">
            <span className="font-bold text-gold-dark dark:text-gold">4. Subject Review</span>
            <p className="mt-1 text-slate">Review subjects with lowest average attendance: {data.subject_stats[0]?.subject_name || "N/A"}.</p>
          </div>
        </div>
      </div>

      {/* Main Student Risk Table with Search & Filters */}
      <SectionCard
        title="Student Risk & Forecast Ledger"
        description="Filter and inspect individual student attendance percentages, AI risk levels, and forecasts."
      >
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate" />
            <input
              type="text"
              placeholder="Search by student name or code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-lg border border-ink-100 bg-white pl-9 pr-4 py-2 text-sm text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter size={14} className="text-slate" />
            <span className="text-xs font-semibold text-slate uppercase">Filter Risk:</span>
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="rounded-lg border border-ink-100 bg-white px-3 py-1.5 text-xs font-semibold text-ink-800 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
            >
              <option value="all">All Risk Levels</option>
              <option value="high">🔴 High Risk Only</option>
              <option value="medium">🟠 Medium Risk Only</option>
              <option value="low">🟢 Low Risk Only</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-100 text-xs uppercase tracking-wide text-slate dark:border-ink-700">
                <th className="py-2.5 pr-4">Student ID</th>
                <th className="py-2.5 pr-4">Name</th>
                <th className="py-2.5 pr-4">Dept / Sem</th>
                <th className="py-2.5 pr-4">Attendance</th>
                <th className="py-2.5 pr-4">Trend</th>
                <th className="py-2.5 pr-4">AI Risk</th>
                <th className="py-2.5 pr-4">Forecast</th>
                <th className="py-2.5 pr-4">Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredStudents.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-sm text-slate">
                    No students match the search/filter criteria.
                  </td>
                </tr>
              ) : (
                filteredStudents.map((s) => (
                  <tr key={s.student_code} className="border-b border-ink-50 hover:bg-ink-50/50 dark:border-ink-800 dark:hover:bg-ink-800/50">
                    <td className="py-3 pr-4 font-mono text-xs text-slate">{s.student_code}</td>
                    <td className="py-3 pr-4 font-medium text-ink-900 dark:text-white">{s.name}</td>
                    <td className="py-3 pr-4 text-xs text-slate">
                      {s.department} (Sem {s.semester})
                    </td>
                    <td
                      className={`py-3 pr-4 font-mono font-bold ${
                        (s.overall_attendance_percentage ?? 0) < 75 ? "text-danger" : "text-success"
                      }`}
                    >
                      {s.overall_attendance_percentage}%
                    </td>
                    <td className="py-3 pr-4">
                      <TrendBadge trend={s.trend} />
                    </td>
                    <td className="py-3 pr-4">
                      <RiskBadge level={s.risk_level} />
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs font-semibold text-ink-800 dark:text-ink-200">
                      {s.forecast_attendance_percentage ? `${s.forecast_attendance_percentage}%` : "-"}
                    </td>
                    <td className="py-3 pr-4">
                      <button
                        onClick={() => handleOpenWhatIf(s.student_code)}
                        className="flex items-center gap-1 rounded bg-ink-100 px-2.5 py-1 text-xs font-semibold text-ink-800 hover:bg-gold hover:text-ink-900 dark:bg-ink-800 dark:text-ink-200 dark:hover:bg-gold dark:hover:text-ink-900"
                      >
                        <Calculator size={12} /> What-If
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* Risk distribution */}
      <SectionCard title="Overall Risk Distribution" description="Worst-case risk level across each student's enrolled subjects.">
        <RiskLedgerStrip
          low={data.risk_distribution.low_risk}
          medium={data.risk_distribution.medium_risk}
          high={data.risk_distribution.high_risk}
        />
      </SectionCard>

      {/* Comparisons */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard title="Department Comparison" description="Average attendance % by department.">
          <AttendanceBarChart data={departmentBars} height={Math.max(220, departmentBars.length * 45)} />
        </SectionCard>
        <SectionCard title="Subject Comparison" description="Average attendance % by subject.">
          <AttendanceBarChart data={subjectBars} height={Math.max(220, subjectBars.length * 32)} />
        </SectionCard>
      </div>

      {/* Improving / Declining */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard
          title="Students Improving"
          description="Trending upward compared to last semester."
          action={<ArrowUpRight size={16} className="text-success" />}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-100 text-xs uppercase tracking-wide text-slate dark:border-ink-700">
                  <th className="py-2 pr-4">Code</th>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Attendance</th>
                  <th className="py-2 pr-4">Risk</th>
                </tr>
              </thead>
              <tbody>
                {data.students_improving.map((s) => (
                  <tr key={s.student_code} className="border-b border-ink-50 dark:border-ink-800">
                    <td className="py-2 pr-4 font-mono text-xs text-slate">{s.student_code}</td>
                    <td className="py-2 pr-4 font-medium text-ink-800 dark:text-ink-100">{s.name}</td>
                    <td className="py-2 pr-4 font-mono font-semibold text-success">{s.overall_attendance_percentage}%</td>
                    <td className="py-2 pr-4">
                      <RiskBadge level={s.risk_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard
          title="Students Declining"
          description="Trending downward compared to last semester."
          action={<ArrowDownRight size={16} className="text-danger" />}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-ink-100 text-xs uppercase tracking-wide text-slate dark:border-ink-700">
                  <th className="py-2 pr-4">Code</th>
                  <th className="py-2 pr-4">Name</th>
                  <th className="py-2 pr-4">Attendance</th>
                  <th className="py-2 pr-4">Risk</th>
                </tr>
              </thead>
              <tbody>
                {data.students_declining.map((s) => (
                  <tr key={s.student_code} className="border-b border-ink-50 dark:border-ink-800">
                    <td className="py-2 pr-4 font-mono text-xs text-slate">{s.student_code}</td>
                    <td className="py-2 pr-4 font-medium text-ink-800 dark:text-ink-100">{s.name}</td>
                    <td className="py-2 pr-4 font-mono font-semibold text-danger">{s.overall_attendance_percentage}%</td>
                    <td className="py-2 pr-4">
                      <RiskBadge level={s.risk_level} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
