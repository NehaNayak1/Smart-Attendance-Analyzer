/**
 * WhatIfSimulatorModal.tsx
 * =========================
 * Interactive What-If Simulator tool for Faculty:
 * Allows faculty to simulate attendance trajectories ("What if student attends next 10 classes?" / "What if student misses next 3 classes?")
 */

import { useState } from "react";
import { ArrowRight, Calculator, CheckCircle, Loader2, Sparkles, TrendingDown, TrendingUp, AlertTriangle, X } from "lucide-react";
import { facultyApi, getErrorMessage } from "@/services/api";
import type { WhatIfResponse } from "@/types";
import { RiskBadge } from "@/components/Badge";
import { toast } from "@/lib/toast";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  initialStudentCode?: string;
}

export function WhatIfSimulatorModal({ isOpen, onClose, initialStudentCode = "" }: Props) {
  const [studentCode, setStudentCode] = useState(initialStudentCode);
  const [mode, setMode] = useState<"attend" | "miss">("attend");
  const [classCount, setClassCount] = useState(10);
  const [result, setResult] = useState<WhatIfResponse | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  if (!isOpen) return null;

  async function handleSimulate(e: React.FormEvent) {
    e.preventDefault();
    if (!studentCode.trim()) {
      toast.error("Please enter a student code");
      return;
    }

    setIsSimulating(true);
    try {
      const res = await facultyApi.runWhatIf({
        student_code: studentCode.trim(),
        attend_next: mode === "attend" ? classCount : 0,
        miss_next: mode === "miss" ? classCount : 0,
      });
      setResult(res);
      toast.success("Simulation complete!");
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setIsSimulating(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-xl rounded-2xl border border-ink-100 bg-white p-6 shadow-2xl dark:border-ink-700 dark:bg-ink-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ink-100 pb-4 dark:border-ink-800">
          <div>
            <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-gold">
              <Sparkles size={14} /> AI Decision Support
            </span>
            <h2 className="text-xl font-bold text-ink-900 dark:text-white">What-If Attendance Simulator</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate transition-colors hover:bg-ink-100 dark:hover:bg-ink-800"
          >
            <X size={20} />
          </button>
        </div>

        {/* Input Form */}
        <form onSubmit={handleSimulate} className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate mb-1">Student ID / Code</label>
            <input
              type="text"
              placeholder="e.g. STU00001"
              value={studentCode}
              onChange={(e) => setStudentCode(e.target.value)}
              className="w-full rounded-lg border border-ink-100 bg-white px-3.5 py-2 text-sm font-medium text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold uppercase text-slate mb-1">Scenario Type</label>
              <div className="flex rounded-lg border border-ink-100 p-1 dark:border-ink-700 bg-ink-50 dark:bg-ink-800">
                <button
                  type="button"
                  onClick={() => setMode("attend")}
                  className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${
                    mode === "attend"
                      ? "bg-success text-white shadow-sm"
                      : "text-slate hover:text-ink-900 dark:hover:text-white"
                  }`}
                >
                  Attends Next Classes
                </button>
                <button
                  type="button"
                  onClick={() => setMode("miss")}
                  className={`flex-1 rounded-md py-1.5 text-xs font-bold transition-colors ${
                    mode === "miss"
                      ? "bg-danger text-white shadow-sm"
                      : "text-slate hover:text-ink-900 dark:hover:text-white"
                  }`}
                >
                  Misses Next Classes
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase text-slate mb-1">Number of Classes</label>
              <input
                type="number"
                min={1}
                max={30}
                value={classCount}
                onChange={(e) => setClassCount(Number(e.target.value))}
                className="w-full rounded-lg border border-ink-100 bg-white px-3.5 py-2 text-sm font-medium text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isSimulating}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ink-800 dark:bg-gold dark:text-ink-900 dark:hover:bg-gold-light disabled:opacity-50"
          >
            {isSimulating ? (
              <>
                <Loader2 size={16} className="animate-spin" /> Calculating Trajectory...
              </>
            ) : (
              <>
                <Calculator size={16} /> Run What-If Simulation
              </>
            )}
          </button>
        </form>

        {/* Results Display */}
        {result && (
          <div className="mt-6 animate-fade-in space-y-4 rounded-xl border border-gold/30 bg-gold/5 p-5 dark:border-gold/20 dark:bg-gold/10">
            <div className="flex items-center justify-between border-b border-gold/20 pb-3">
              <div>
                <h3 className="font-bold text-ink-900 dark:text-white">{result.name}</h3>
                <span className="font-mono text-xs text-slate">{result.student_code}</span>
              </div>
              <div className="text-right">
                <span className="text-xs text-slate">Recovery Requirement</span>
                <p className="text-xs font-bold text-ink-900 dark:text-white">
                  {result.classes_needed_for_75 > 0 ? (
                    <span className="text-danger flex items-center gap-1 justify-end">
                      <AlertTriangle size={12} /> {result.classes_needed_for_75} consecutive classes needed for 75%
                    </span>
                  ) : (
                    <span className="text-success flex items-center gap-1 justify-end">
                      <CheckCircle size={12} /> Above 75% threshold
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* Comparison Cards */}
            <div className="grid grid-cols-2 gap-4 text-center">
              <div className="rounded-lg bg-white p-3 shadow-sm dark:bg-ink-800">
                <span className="text-xs font-semibold text-slate">Current Status</span>
                <p className="font-mono text-xl font-bold text-ink-900 dark:text-white">{result.current_percentage}%</p>
                <div className="mt-1 flex justify-center">
                  <RiskBadge level={result.current_risk_level} />
                </div>
              </div>

              <div className="rounded-lg bg-white p-3 shadow-sm dark:bg-ink-800">
                <span className="text-xs font-semibold text-slate">
                  Simulated ({mode === "attend" ? `+${classCount} Attended` : `+${classCount} Missed`})
                </span>
                <p
                  className={`font-mono text-xl font-bold ${
                    result.projected_percentage >= result.current_percentage ? "text-success" : "text-danger"
                  }`}
                >
                  {result.projected_percentage}%
                </p>
                <div className="mt-1 flex justify-center">
                  <RiskBadge level={result.projected_risk_level} />
                </div>
              </div>
            </div>

            {/* Step Trajectory */}
            <div>
              <h4 className="text-xs font-semibold uppercase text-slate mb-2">Simulated Attendance Trajectory</h4>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {result.trajectory.map((pt, i) => (
                  <div key={i} className="flex items-center justify-between rounded-lg bg-white/80 px-3 py-1.5 text-xs dark:bg-ink-800/80">
                    <span className="font-medium text-ink-800 dark:text-ink-200 flex items-center gap-1">
                      {i === 0 ? null : mode === "attend" ? <TrendingUp size={14} className="text-success" /> : <TrendingDown size={14} className="text-danger" />}
                      {pt.label}
                    </span>
                    <span
                      className={`font-mono font-bold ${
                        pt.percentage >= 75 ? "text-success" : "text-danger"
                      }`}
                    >
                      {pt.percentage}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
