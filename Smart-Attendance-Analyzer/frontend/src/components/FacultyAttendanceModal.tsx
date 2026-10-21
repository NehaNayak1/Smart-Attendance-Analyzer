/**
 * FacultyAttendanceModal.tsx
 * ===========================
 * Data-Entry Modal for Faculty:
 *  - Manual Attendance Entry (Department, Semester, Subject, Date + Student toggles)
 *  - Attendance CSV Upload (Student Code, Status)
 */

import { useEffect, useState } from "react";
import { Check, CheckCircle2, FileSpreadsheet, Loader2, Upload, UserCheck, X } from "lucide-react";
import { facultyApi, getErrorMessage } from "@/services/api";
import type { AttendanceStudentItem, SubjectItem } from "@/types";
import { DEPARTMENTS, SEMESTERS } from "@/lib/constants";
import { toast } from "@/lib/toast";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  defaultDepartment?: string;
}

export function FacultyAttendanceModal({ isOpen, onClose, onSuccess, defaultDepartment = "Computer Science" }: Props) {
  const [tab, setTab] = useState<"manual" | "csv">("manual");
  const [department, setDepartment] = useState(defaultDepartment || "Computer Science");
  const [semester, setSemester] = useState(5);
  const [subjectId, setSubjectId] = useState<number | "">("");
  const [subjects, setSubjects] = useState<SubjectItem[]>([]);
  const [date, setDate] = useState(() => new Date().toISOString().split("T")[0]);

  const [students, setStudents] = useState<AttendanceStudentItem[]>([]);
  const [presenceMap, setPresenceMap] = useState<Record<number, boolean>>({});
  
  const [csvFile, setCsvFile] = useState<File | null>(null);

  const [isLoadingSubjects, setIsLoadingSubjects] = useState(false);
  const [isLoadingStudents, setIsLoadingStudents] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    async function loadSubjects() {
      setIsLoadingSubjects(true);
      try {
        const list = await facultyApi.getSubjects(department);
        setSubjects(list);
        if (list.length > 0) {
          setSubjectId(list[0].id);
        } else {
          setSubjectId("");
        }
      } catch (err) {
        toast.error(getErrorMessage(err));
      } finally {
        setIsLoadingSubjects(false);
      }
    }
    loadSubjects();
  }, [isOpen, department]);

  useEffect(() => {
    if (!isOpen || !department || !semester || !subjectId) return;
    async function loadStudents() {
      setIsLoadingStudents(true);
      try {
        const list = await facultyApi.getStudentsForAttendance(department, semester, Number(subjectId));
        setStudents(list);
        const initialMap: Record<number, boolean> = {};
        list.forEach((s) => {
          initialMap[s.student_id] = true; // default present
        });
        setPresenceMap(initialMap);
      } catch (err) {
        toast.error(getErrorMessage(err));
      } finally {
        setIsLoadingStudents(false);
      }
    }
    loadStudents();
  }, [isOpen, department, semester, subjectId]);

  if (!isOpen) return null;

  function toggleStudent(studentId: number) {
    setPresenceMap((prev) => ({ ...prev, [studentId]: !prev[studentId] }));
  }

  function markAll(present: boolean) {
    const updated: Record<number, boolean> = {};
    students.forEach((s) => {
      updated[s.student_id] = present;
    });
    setPresenceMap(updated);
  }

  async function handleSubmitManual(e: React.FormEvent) {
    e.preventDefault();
    if (!subjectId) {
      toast.error("Please select a subject");
      return;
    }
    if (students.length === 0) {
      toast.error("No students found for attendance marking");
      return;
    }

    setIsSubmitting(true);
    try {
      const records = students.map((s) => ({
        student_id: s.student_id,
        present: presenceMap[s.student_id] ?? true,
      }));

      const res = await facultyApi.recordAttendance({
        department,
        semester,
        subject_id: Number(subjectId),
        date,
        records,
      });

      toast.success(res.message);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSubmitCsv(e: React.FormEvent) {
    e.preventDefault();
    if (!subjectId) {
      toast.error("Please select a subject");
      return;
    }
    if (!csvFile) {
      toast.error("Please select a CSV file to upload");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await facultyApi.uploadCsvAttendance(Number(subjectId), csvFile);
      toast.success(res.message);
      onSuccess();
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  const presentCount = Object.values(presenceMap).filter(Boolean).length;
  const absentCount = students.length - presentCount;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-2xl border border-ink-100 bg-white p-6 shadow-2xl dark:border-ink-700 dark:bg-ink-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ink-100 pb-4 dark:border-ink-800">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-gold">Data Entry Authority</span>
            <h2 className="text-xl font-bold text-ink-900 dark:text-white">Record Attendance</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate transition-colors hover:bg-ink-100 dark:hover:bg-ink-800"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="mt-4 flex gap-2 border-b border-ink-100 pb-3 dark:border-ink-800">
          <button
            type="button"
            onClick={() => setTab("manual")}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
              tab === "manual"
                ? "bg-ink-900 text-white dark:bg-gold dark:text-ink-900"
                : "text-slate hover:bg-ink-100 dark:hover:bg-ink-800"
            }`}
          >
            <UserCheck size={16} /> Direct Class Mark
          </button>
          <button
            type="button"
            onClick={() => setTab("csv")}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors ${
              tab === "csv"
                ? "bg-ink-900 text-white dark:bg-gold dark:text-ink-900"
                : "text-slate hover:bg-ink-100 dark:hover:bg-ink-800"
            }`}
          >
            <FileSpreadsheet size={16} /> Upload Attendance CSV
          </button>
        </div>

        {/* Selection Bar */}
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div>
            <label className="block text-xs font-semibold uppercase text-slate mb-1">Department</label>
            <select
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
              className="w-full rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs font-medium text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
            >
              {DEPARTMENTS.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate mb-1">Semester</label>
            <select
              value={semester}
              onChange={(e) => setSemester(Number(e.target.value))}
              className="w-full rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs font-medium text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
            >
              {SEMESTERS.map((s) => (
                <option key={s} value={s}>
                  Sem {s}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate mb-1">Subject</label>
            <select
              value={subjectId}
              onChange={(e) => setSubjectId(Number(e.target.value))}
              disabled={isLoadingSubjects}
              className="w-full rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs font-medium text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white disabled:opacity-50"
            >
              {subjects.map((subj) => (
                <option key={subj.id} value={subj.id}>
                  {subj.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold uppercase text-slate mb-1">Session Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-lg border border-ink-100 bg-white px-3 py-2 text-xs font-medium text-ink-900 outline-none focus:border-gold dark:border-ink-700 dark:bg-ink-800 dark:text-white"
            />
          </div>
        </div>

        {/* Tab 1: Manual Entry */}
        {tab === "manual" && (
          <form onSubmit={handleSubmitManual} className="mt-5 space-y-4">
            <div className="flex items-center justify-between rounded-xl bg-ink-50 px-4 py-2.5 dark:bg-ink-800">
              <span className="text-xs font-medium text-slate">
                Students: <strong className="text-ink-900 dark:text-white">{students.length}</strong> | Present:{" "}
                <strong className="text-success">{presentCount}</strong> | Absent:{" "}
                <strong className="text-danger">{absentCount}</strong>
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => markAll(true)}
                  className="rounded px-2.5 py-1 text-xs font-semibold text-success bg-success/10 hover:bg-success/20 transition-colors"
                >
                  All Present
                </button>
                <button
                  type="button"
                  onClick={() => markAll(false)}
                  className="rounded px-2.5 py-1 text-xs font-semibold text-danger bg-danger/10 hover:bg-danger/20 transition-colors"
                >
                  All Absent
                </button>
              </div>
            </div>

            {isLoadingStudents ? (
              <div className="flex justify-center py-10">
                <Loader2 className="animate-spin text-gold" size={28} />
              </div>
            ) : students.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate">
                No students found for this department and semester.
              </div>
            ) : (
              <div className="max-h-64 overflow-y-auto rounded-xl border border-ink-100 dark:border-ink-800 divide-y divide-ink-50 dark:divide-ink-800">
                {students.map((stu) => {
                  const isPresent = presenceMap[stu.student_id] ?? true;
                  return (
                    <div
                      key={stu.student_id}
                      onClick={() => toggleStudent(stu.student_id)}
                      className={`flex items-center justify-between px-4 py-3 cursor-pointer transition-colors ${
                        isPresent ? "hover:bg-success/5" : "bg-danger/5 hover:bg-danger/10"
                      }`}
                    >
                      <div>
                        <span className="font-mono text-xs text-slate">{stu.student_code}</span>
                        <h4 className="text-sm font-semibold text-ink-900 dark:text-white">{stu.name}</h4>
                        <span className="text-xs text-slate">Current Subject: {stu.subject_attendance_percentage}%</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold ${
                            isPresent
                              ? "bg-success/20 text-success"
                              : "bg-danger/20 text-danger"
                          }`}
                        >
                          {isPresent ? (
                            <>
                              <CheckCircle2 size={14} /> Present
                            </>
                          ) : (
                            <>
                              <X size={14} /> Absent
                            </>
                          )}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-3 border-t border-ink-100 dark:border-ink-800">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-ink-100 px-4 py-2 text-sm font-medium text-slate hover:bg-ink-50 dark:border-ink-700 dark:hover:bg-ink-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || students.length === 0}
                className="flex items-center gap-2 rounded-lg bg-ink-900 px-5 py-2 text-sm font-semibold text-white hover:bg-ink-800 dark:bg-gold dark:text-ink-900 dark:hover:bg-gold-light disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" /> Saving & Triggering AI...
                  </>
                ) : (
                  <>
                    <Check size={16} /> Save Attendance
                  </>
                )}
              </button>
            </div>
          </form>
        )}

        {/* Tab 2: CSV Upload */}
        {tab === "csv" && (
          <form onSubmit={handleSubmitCsv} className="mt-5 space-y-4">
            <div className="rounded-xl border-2 border-dashed border-ink-200 p-8 text-center dark:border-ink-700">
              <Upload className="mx-auto text-gold mb-3" size={36} />
              <h3 className="text-sm font-semibold text-ink-900 dark:text-white">Upload Attendance CSV File</h3>
              <p className="mt-1 text-xs text-slate">
                CSV should contain <code className="rounded bg-ink-100 px-1 py-0.5 dark:bg-ink-800">student_code</code> and{" "}
                <code className="rounded bg-ink-100 px-1 py-0.5 dark:bg-ink-800">status</code> (Present / Absent)
              </p>

              <input
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                className="mt-4 block w-full text-xs text-slate file:mr-4 file:rounded-lg file:border-0 file:bg-gold file:px-4 file:py-2 file:text-xs file:font-semibold file:text-ink-900 hover:file:bg-gold-light cursor-pointer"
              />

              {csvFile && (
                <div className="mt-3 rounded-lg bg-success/10 p-2 text-xs font-semibold text-success">
                  Selected: {csvFile.name} ({(csvFile.size / 1024).toFixed(1)} KB)
                </div>
              )}
            </div>

            <div className="rounded-lg bg-ink-50 p-3 text-xs text-slate dark:bg-ink-800">
              <strong>CSV Example Format:</strong>
              <pre className="mt-1 font-mono text-ink-700 dark:text-ink-300">
                student_code,name,status{"\n"}
                STU00001,Neha Nayak,Present{"\n"}
                STU00002,Sakshi,Present{"\n"}
                STU00003,Shreya,Absent
              </pre>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-ink-100 dark:border-ink-800">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-ink-100 px-4 py-2 text-sm font-medium text-slate hover:bg-ink-50 dark:border-ink-700 dark:hover:bg-ink-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !csvFile}
                className="flex items-center gap-2 rounded-lg bg-ink-900 px-5 py-2 text-sm font-semibold text-white hover:bg-ink-800 dark:bg-gold dark:text-ink-900 dark:hover:bg-gold-light disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" /> Processing & Updating AI...
                  </>
                ) : (
                  <>
                    <Upload size={16} /> Process & Run AI Risk Analysis
                  </>
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
