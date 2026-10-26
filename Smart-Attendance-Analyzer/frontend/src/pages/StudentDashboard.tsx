/**
 * pages/StudentDashboard.tsx
 * =============================
 * The primary student-facing page (READ-ONLY CONSUMER):
 *  - Prominent Read-Only Notice
 *  - AI Early Risk Alert Banner
 *  - Attendance Recovery Plan Card (consecutive classes needed for 75%)
 *  - Overall + subject-wise attendance with subject recovery column
 *  - Monthly trend & latest AI prediction with forecast & recommendations
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  BookOpen,
  CalendarX,
  CheckCircle2,
  Download,
  GraduationCap,
  Lock,
  Percent,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { downloadBlob, exportApi, getErrorMessage, studentApi } from "@/services/api";
import type { StudentDashboard as StudentDashboardType } from "@/types";
import { PageLoader } from "@/components/Loader";
import { ErrorState } from "@/components/EmptyState";
import { Card, SectionCard, StatCard } from "@/components/Card";
import { RiskBadge, SegmentBadge, TrendBadge } from "@/components/Badge";
import { AttendanceLineChart } from "@/charts/AttendanceLineChart";
import { SubjectRadarChart } from "@/charts/SubjectRadarChart";
import { toast } from "@/lib/toast";

export default function StudentDashboard() {
  const [data, setData] = useState<StudentDashboardType | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"pdf" | "csv" | null>(null);

  async function loadDashboard() {
    setIsLoading(true);
    setError(null);
    try {
      const result = await studentApi.getDashboard();
      setData(result);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadDashboard();
  }, []);

  async function handleDownload(format: "pdf" | "csv") {
    setDownloading(format);
    try {
      const blob = await exportApi.studentReport(format);
      downloadBlob(blob, `attendance_report.${format}`);
      toast.success(`Report downloaded as ${format.toUpperCase()}.`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDownloading(null);
    }
  }

  if (isLoading) return <PageLoader label="Loading your dashboard..." />;
  if (error || !data) return <ErrorState message={error ?? "No data available."} onRetry={loadDashboard} />;

  const {
    profile,
    overall_attendance_percentage,
    subject_wise,
    monthly_trend,
    total_leaves,
    average_internal_marks,
    latest_prediction,
    recovery_plan,
    early_risk_alert,
  } = data;

  return (
    <div className="animate-fade-in space-y-6 pb-10">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-gold-dark dark:text-gold">
            <span>Student Consumer Portal</span>
            <span className="inline-flex items-center gap-1 rounded bg-ink-100 px-2 py-0.5 text-xs text-slate dark:bg-ink-800 dark:text-slate-300">
              <Lock size={12} /> Read-Only
            </span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-ink-900 dark:text-white">
            Welcome, {profile.name} 👋 <span className="font-mono text-lg text-slate">· {profile.student_code}</span>
          </h1>
          <p className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate">
            <GraduationCap size={14} /> {profile.department} · Semester {profile.semester}
            <TrendBadge trend={profile.trend} />
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => handleDownload("csv")}
            disabled={downloading !== null}
            className="flex items-center gap-1.5 rounded-lg border border-ink-100 px-3 py-2 text-sm font-medium text-ink-700 transition-colors hover:bg-ink-50 disabled:opacity-60 dark:border-ink-700 dark:text-ink-100 dark:hover:bg-ink-800"
          >
            <Download size={14} /> {downloading === "csv" ? "Preparing..." : "CSV"}
          </button>
          <button
            onClick={() => handleDownload("pdf")}
            disabled={downloading !== null}
            className="flex items-center gap-1.5 rounded-lg bg-ink-900 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-ink-700 disabled:opacity-60 dark:bg-gold dark:text-ink-900 dark:hover:bg-gold-light"
          >
            <Download size={14} /> {downloading === "pdf" ? "Preparing..." : "Download PDF"}
          </button>
        </div>
      </div>

      {/* Early Risk Alert Banner */}
      {early_risk_alert && (
        <div
          className={`flex items-start gap-3 rounded-2xl p-4 border shadow-sm ${
            overall_attendance_percentage < 75
              ? "border-danger/30 bg-danger/10 text-danger-dark dark:border-danger/20 dark:bg-danger/15 dark:text-danger-light"
              : "border-gold/30 bg-gold/10 text-gold-dark dark:border-gold/20 dark:bg-gold/15 dark:text-gold"
          }`}
        >
          <ShieldAlert className="mt-0.5 shrink-0" size={20} />
          <div>
            <h3 className="font-bold text-sm">AI Risk Alert & Early Warning</h3>
            <p className="mt-0.5 text-xs font-medium leading-relaxed">{early_risk_alert}</p>
          </div>
        </div>
      )}

      {/* Recovery Plan Card */}
      {recovery_plan && (
        <SectionCard
          title="Attendance Recovery Calculator"
          description="Classes needed to meet or maintain the mandatory 75% attendance threshold."
        >
          <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="flex flex-col justify-center rounded-xl bg-ink-50 p-4 dark:bg-ink-800">
              <span className="text-xs font-semibold uppercase text-slate">Current Attendance</span>
              <div className="mt-1 flex items-baseline gap-2">
                <span
                  className={`font-mono text-3xl font-extrabold ${
                    overall_attendance_percentage < 75 ? "text-danger" : "text-success"
                  }`}
                >
                  {overall_attendance_percentage}%
                </span>
                <span className="text-xs text-slate">Requirement: 75%</span>
              </div>
              <p className="mt-1 text-xs text-slate">
                {recovery_plan.classes_attended} attended out of {recovery_plan.total_classes} total classes
              </p>
            </div>

            <div className="flex flex-col justify-center rounded-xl bg-gold/10 p-4 dark:bg-gold/15">
              <span className="text-xs font-bold uppercase text-gold-dark dark:text-gold">Recovery Target</span>
              <div className="mt-1">
                {recovery_plan.classes_needed_for_75 > 0 ? (
                  <span className="font-mono text-2xl font-extrabold text-danger">
                    Attend Next {recovery_plan.classes_needed_for_75} Classes
                  </span>
                ) : (
                  <span className="font-mono text-2xl font-extrabold text-success flex items-center gap-1">
                    <CheckCircle2 size={20} /> On Track (0 Needed)
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate">
                {recovery_plan.classes_needed_for_75 > 0
                  ? "You must attend these consecutive classes without absence to reach 75%."
                  : "You are currently meeting the attendance criteria."}
              </p>
            </div>

            <div className="flex flex-col justify-center">
              <div className="flex items-center justify-between text-xs font-semibold text-slate mb-1">
                <span>Progress to 75%</span>
                <span>{overall_attendance_percentage} / 75.0%</span>
              </div>
              <div className="h-4 w-full rounded-full bg-ink-100 dark:bg-ink-800 overflow-hidden p-0.5">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    overall_attendance_percentage < 75 ? "bg-danger" : "bg-success"
                  }`}
                  style={{ width: `${Math.min(100, (overall_attendance_percentage / 75) * 100)}%` }}
                />
              </div>
              <p className="mt-2 text-xs text-slate text-right">
                {overall_attendance_percentage >= 75
                  ? "Safe Zone ✅"
                  : `Short by ${(75 - overall_attendance_percentage).toFixed(1)}%`}
              </p>
            </div>
          </div>

          {/* A* Search Optimal Multi-Subject Recovery Path (Module 3) */}
          {recovery_plan.a_star_plan && recovery_plan.a_star_plan.total_classes_to_attend > 0 && (
            <div className="mt-6 border-t border-ink-100 pt-5 dark:border-ink-700">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center rounded-md bg-gold/15 px-2.5 py-1 text-xs font-semibold text-gold-dark dark:text-gold">
                    ⚡ {recovery_plan.a_star_plan.algorithm}
                  </span>
                  <span className="text-xs text-slate">
                    Optimal path resolved in <strong className="font-mono text-ink-900 dark:text-white">{recovery_plan.a_star_plan.nodes_explored}</strong> search nodes
                  </span>
                </div>
                <span className="text-xs font-mono text-slate">
                  Total Classes to Recover: <strong className="text-danger font-bold">{recovery_plan.a_star_plan.total_classes_to_attend}</strong>
                </span>
              </div>

              {/* Subject Breakdown */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {recovery_plan.a_star_plan.subject_breakdown.map((sb) => (
                  <div
                    key={sb.subject}
                    className="flex flex-col justify-between rounded-lg border border-ink-100 bg-white p-3 shadow-xs dark:border-ink-700 dark:bg-ink-900"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-ink-800 dark:text-ink-100 truncate">{sb.subject}</span>
                      <span
                        className={`text-xs font-mono font-bold ${
                          sb.initial_percentage < 75 ? "text-danger" : "text-success"
                        }`}
                      >
                        {sb.initial_percentage}%
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-xs text-slate">
                      <span>Action:</span>
                      {sb.classes_needed > 0 ? (
                        <span className="font-bold text-gold-dark dark:text-gold font-mono">
                          Attend next +{sb.classes_needed} classes
                        </span>
                      ) : (
                        <span className="text-success font-medium">Safe (0 needed)</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </SectionCard>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Overall Attendance"
          value={`${overall_attendance_percentage}%`}
          icon={<Percent size={16} />}
          accent={overall_attendance_percentage < 75 ? "danger" : "success"}
          sublabel={overall_attendance_percentage < 75 ? "Below requirement" : "Meets requirement"}
        />
        <StatCard label="Total Leaves" value={total_leaves} icon={<CalendarX size={16} />} accent="ink" />
        <StatCard
          label="Avg. Internal Marks"
          value={average_internal_marks ?? "-"}
          icon={<BookOpen size={16} />}
          accent="ink"
        />
        <StatCard
          label="AI Risk Level"
          value={latest_prediction?.predicted_risk_level ?? "Not predicted"}
          icon={<Sparkles size={16} />}
          accent={
            latest_prediction?.predicted_risk_level === "High Risk"
              ? "danger"
              : latest_prediction?.predicted_risk_level === "Medium Risk"
              ? "warning"
              : "success"
          }
        />
      </div>

      {/* Prediction summary */}
      {latest_prediction ? (
        <SectionCard
          title="AI Risk Analysis & Forecast"
          description={`Generated by ${latest_prediction.risk_model_used} & ${latest_prediction.forecast_model_used}`}
        >
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <RiskBadge level={latest_prediction.predicted_risk_level} />
            <SegmentBadge segment={latest_prediction.cluster_segment} />
            <span className="text-sm text-slate">
              Projected Semester-End Attendance:{" "}
              <span className="font-mono font-bold text-ink-900 dark:text-white">
                {latest_prediction.forecast_attendance_percentage}%
              </span>
            </span>
          </div>
          <ul className="space-y-2">
            {latest_prediction.ai_recommendations.map((tip, i) => (
              <li
                key={i}
                className="flex items-start gap-2 rounded-lg bg-ink-50 px-3 py-2 text-sm text-ink-800 dark:bg-ink-800 dark:text-ink-100"
              >
                <Sparkles size={14} className="mt-0.5 shrink-0 text-gold" />
                {tip}
              </li>
            ))}
          </ul>
        </SectionCard>
      ) : (
        <Card className="flex flex-col items-center gap-3 p-6 text-center">
          <Sparkles size={24} className="text-gold" />
          <p className="text-sm text-slate">
            Your attendance is regularly processed by AI models to predict risk and forecast term-end attendance.
          </p>
        </Card>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <SectionCard title="Monthly Attendance Trend" description="Your average attendance across all subjects, by month.">
          <AttendanceLineChart data={monthly_trend} />
        </SectionCard>
        <SectionCard title="Subject-wise Attendance" description="Attendance % per subject vs. the 75% requirement.">
          <SubjectRadarChart subjects={subject_wise} />
        </SectionCard>
      </div>

      {/* Subject table */}
      <SectionCard title="Subject Details & Recovery Metrics">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-ink-100 text-xs uppercase tracking-wide text-slate dark:border-ink-700">
                <th className="py-2.5 pr-4">Subject</th>
                <th className="py-2.5 pr-4">Classes Attended</th>
                <th className="py-2.5 pr-4">Attendance %</th>
                <th className="py-2.5 pr-4">Classes Needed for 75%</th>
                <th className="py-2.5 pr-4">Leaves</th>
                <th className="py-2.5 pr-4">Marks</th>
                <th className="py-2.5 pr-4">Risk</th>
              </tr>
            </thead>
            <tbody>
              {subject_wise.map((s) => (
                <tr key={s.subject_name} className="border-b border-ink-50 dark:border-ink-800">
                  <td className="py-2.5 pr-4 font-medium text-ink-800 dark:text-ink-100">{s.subject_name}</td>
                  <td className="py-2.5 pr-4 font-mono text-slate">
                    {s.classes_attended}/{s.total_classes}
                  </td>
                  <td
                    className={`py-2.5 pr-4 font-mono font-semibold ${
                      s.attendance_percentage < 75 ? "text-danger" : "text-success"
                    }`}
                  >
                    {s.attendance_percentage}%
                  </td>
                  <td className="py-2.5 pr-4 font-mono">
                    {s.classes_needed_for_75 && s.classes_needed_for_75 > 0 ? (
                      <span className="font-bold text-danger">{s.classes_needed_for_75} classes</span>
                    ) : (
                      <span className="text-success font-semibold">0 (On track)</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-slate">{s.leaves_taken}</td>
                  <td className="py-2.5 pr-4 font-mono text-slate">{s.internal_marks ?? "-"}</td>
                  <td className="py-2.5 pr-4">
                    <RiskBadge level={s.risk_label} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </SectionCard>
    </div>
  );
}
