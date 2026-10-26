# Smart Attendance Pattern Analyzer
## Complete AI, Machine Learning & Architecture Summary

This document provides a comprehensive breakdown of the Artificial Intelligence (AI) and Machine Learning (ML) features implemented in the **Smart Attendance Pattern Analyzer**, along with a complete architecture reference for the frontend, backend, database, and API routes. Use this guide to explain and demonstrate the project during reviews, vivas, and project presentations.

---

# Part 1: AI & Machine Learning Core

The project uniquely bridges **Classical Artificial Intelligence (Search & Heuristics, Knowledge Representation & Reasoning)** with **Modern Machine Learning (Supervised Classification, Regression, and Unsupervised Clustering)**.

```
                           ┌────────────────────────────────────────────────────────┐
                           │            Smart Attendance Pattern Analyzer           │
                           └──────────────────────────┬─────────────────────────────┘
                                                      │
                     ┌────────────────────────────────┴────────────────────────────────┐
                     ▼                                                                 ▼
      ┌─────────────────────────────┐                                   ┌─────────────────────────────┐
      │   Classical AI Algorithms   │                                   │   Machine Learning Models   │
      │    (Syllabus: M3 & M4)      │                                   │   (Scikit-Learn Lifecycle)  │
      └──────────────┬──────────────┘                                   └──────────────┬──────────────┘
                     │                                                                 │
    ┌────────────────┼────────────────┐                               ┌────────────────┼────────────────┐
    ▼                ▼                ▼                               ▼                ▼                ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐              ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  A* Search   │ │Hill Climbing │ │  Knowledge   │              │     Risk     │ │  Attendance  │ │   Student    │
│  Algorithm   │ │    Search    │ │Inference (FC/│              │Classification│ │  Forecast    │ │ Segmentation │
│ (M3, Lec 16) │ │ (M3, Lec 19) │ │BC) (M4, L23) │              │(Random Forest│ │(Random Forest│ │   (K-Means   │
└──────────────┘ └──────────────┘ └──────────────┘              │  Classifier) │ │  Regressor)  │ │   k = 3)     │
                                                                └──────────────┘ └──────────────┘ └──────────────┘
```

---

## 1. Classical Artificial Intelligence Algorithms

### A. A* Search Algorithm ($f(n) = g(n) + h(n)$)
* **Syllabus Mapping:** Module 3, Lecture 16 (*A\* Search Algorithm & Heuristic Search*)
* **Implementation File:** `backend/ml/ai_search.py`
* **Endpoint:** `POST /api/prediction/ai/a-star-recovery` & embedded in `GET /api/student/dashboard`
* **Where Displayed in UI:** Student Dashboard (`/student/dashboard`) under the **Attendance Recovery Calculator** card.
* **What it does:**
  * Models multi-subject attendance recovery as a state-space heuristic search problem.
  * **State Space:** Tuple of `((classes_attended_1, total_classes_1), (classes_attended_2, total_classes_2), ...)`.
  * **Evaluation Function:** $f(n) = g(n) + h(n)$:
    * $g(n)$: Accumulated weighted effort / difficulty cost invested by attending classes.
    * $h(n)$ (Admissible Heuristic): $\sum_{i} w_i \times \max\left(0, \left\lceil \frac{0.75 \times T_i - A_i}{1 - 0.75} \right\rceil\right)$. Because each action can attend at most 1 class in 1 subject, $h(n) \le h^*(n)$ (never overestimates remaining cost), guaranteeing an optimal solution.
  * **Symmetry Reduction:** Enforces canonical action ordering to prevent exploring commutative permutations of class schedules.
* **Why it is used:** Rather than telling a student a naive scalar ("attend 10 classes"), A* plans the **mathematically optimal, minimal-effort sequence of classes across all enrolled subjects** to ensure every single deficit subject crosses 75%.

---

### B. Steepest-Ascent Hill Climbing Search
* **Syllabus Mapping:** Module 3, Lecture 19 (*Hill Climbing & Local Search*)
* **Implementation File:** `backend/ml/ai_search.py`
* **Endpoint:** `POST /api/prediction/ai/hill-climbing-optimize`
* **What it does:**
  * Formulated as a constrained local search to optimize class attendance allocation.
  * **State:** Vector $[a_1, a_2, \dots, a_N]$ where $\sum a_i = K$ (the student's total attendance budget).
  * **Evaluation / Fitness Function $E(s)$:**
    $$E(s) = \sum_{i=1}^{N} \left( \text{percentage}_i \times \text{weight}_i + \text{Bonus}_{75} - \text{Penalty}_{\text{medium}} - \text{Penalty}_{\text{critical}} \right)$$
  * **Neighborhood Transition:** Transfers 1 class unit between subject $i$ and subject $j$.
  * **Steepest-Ascent Strategy:** Evaluates all valid neighboring transitions and commits to the move producing the highest positive improvement $\Delta E > 0$, terminating when a peak/local optimum is reached.
* **Why it is used:** Students with strict external constraints (medical issues, financial jobs, long commutes) cannot attend all remaining lectures. Given a finite capacity (e.g. $K = 12$ classes), Hill Climbing finds the **best possible distribution of those 12 classes to prevent detention and pull critical subjects above 65%**.

---

### C. Forward Chaining Inference Engine (Data-Driven)
* **Syllabus Mapping:** Module 4, Lecture 23 (*Knowledge Representation, Forward & Backward Chaining*)
* **Implementation File:** `backend/ml/knowledge_engine.py`
* **Where Displayed in UI:** Prediction & Recommendations Page (`/prediction`) in the **Prediction Result** card.
* **What it does:**
  * Operates over a formal Knowledge Base of **Horn Clauses**: $\text{Antecedent}_1 \land \text{Antecedent}_2 \implies \text{Consequent}$.
  * Extracts symbolic ground propositions from numeric features (`attendance_below_75`, `trend_declining`, `leaves_high`, `commute_long`, `internal_marks_low`).
  * Iteratively checks rule premises against working memory, fires triggered rules, and records new conclusions into working memory until saturation.
* **Why it is used:** Replaces unexplainable hardcoded `if-else` branches with a structured expert system. It diagnoses root causes (e.g., distinguishing between **Commute-Induced Absenteeism** vs. **Habitual Absenteeism**) and derives actionable recommendations with full rule derivation logs.

---

### D. Backward Chaining Goal Verification (Goal-Driven)
* **Syllabus Mapping:** Module 4, Lecture 23 (*Knowledge Representation, Forward & Backward Chaining*)
* **Implementation File:** `backend/ml/knowledge_engine.py`
* **Endpoint:** `POST /api/prediction/ai/backward-chain-query`
* **What it does:**
  * Verifies target hypotheses (e.g., `exam_eligibility_cleared`, `high_exam_detention_risk`, `academic_probation_risk`).
  * Checks if the goal exists in ground facts; if not, identifies rules concluding the goal and recursively attempts to prove all necessary subgoals.
  * If unproven, outputs the proof tree and the exact list of missing ground conditions.
* **Why it is used:** Enables students and faculty to test "what-if" outcomes and regulatory compliance before final exam clearances.

---

## 2. Machine Learning Models (scikit-learn Pipeline)

All ML models are trained on a synthetic dataset of **5,000 students** and **22,535 attendance records** across 6 engineering departments, 8 semesters, and 30 courses.

| Task | Problem Type | Compared Algorithms | Winning Production Model | Key Metrics |
|---|---|---|---|---|
| **1. Risk Classification** | Supervised Multi-class Classification | Decision Tree vs. **Random Forest Classifier** | **Random Forest Classifier** (`backend/ml/saved_models/risk_model.pkl`) | **96.8% Accuracy**, Weighted F1: 0.968, Multi-class ROC-AUC: 0.99 |
| **2. Attendance Forecast** | Supervised Continuous Regression | Linear Regression vs. **Random Forest Regressor** | **Random Forest Regressor** (`backend/ml/saved_models/forecast_model.pkl`) | **$R^2 = 0.963$**, MAE: 2.36%, RMSE: 3.41% |
| **3. Student Segmentation** | Unsupervised Clustering | K-Means ($k=3$) with PCA 2D reduction | **K-Means Clustering** (`backend/ml/saved_models/segmentation_model.pkl`) | **Silhouette Score: 0.334**, Clusters: `Excellent`, `Average`, `Critical` |

---

# Part 2: Complete Project Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    CLIENT BROWSER                                      │
│                React 18 + TypeScript + Vite + Tailwind CSS + Recharts                  │
│                                                                                        │
│   ┌────────────────────┐   ┌─────────────────────┐   ┌─────────────────────────────┐   │
│   │ Student Dashboard  │   │  Faculty Dashboard  │   │  Prediction & What-If Studio│   │
│   │ (A* Recovery Card) │   │  (Institution Stats)│   │  (Forward Chaining Tags)    │   │
│   └─────────┬──────────┘   └──────────┬──────────┘   └──────────────┬──────────────┘   │
└─────────────┼─────────────────────────┼─────────────────────────────┼──────────────────┘
              │                         │ Axios API Client            │
              ▼                         ▼                             ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  FASTAPI REST BACKEND                                  │
│                             Python 3.11+ / Uvicorn Server                              │
│                                                                                        │
│  [JWT Authentication] ──────► [Role-Based Access Control] ──────► [Pydantic Validation]│
│                                                                                        │
│  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌────────────────────────┐  │
│  │     Routes Layer        │  │   Classical AI Engine   │  │    Machine Learning    │  │
│  │ auth, student, faculty, │  │ a_star_recovery_planner │  │ risk_model (RF)        │  │
│  │ prediction, analytics   │  │ hill_climbing_optimizer │  │ forecast_model (RF)    │  │
│  │ export (PDF/CSV)        │  │ forward_chain / b_chain │  │ segmentation (KMeans)  │  │
│  └──────────┬──────────────┘  └───────────┬─────────────┘  └───────────┬────────────┘  │
└─────────────┼─────────────────────────────┼────────────────────────────┼───────────────┘
              │                             │                            │
              ▼                             ▼                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                    DATABASE LAYER                                      │
│                               SQLite 3 via SQLAlchemy ORM                              │
│         [users] ─── [students] ─── [subjects] ─── [attendance] ─── [predictions]       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Frontend Architecture
* **Framework:** React 18 with Vite for ultra-fast Hot Module Replacement (HMR).
* **Language:** TypeScript for compile-time type safety across all API payloads.
* **Styling:** Vanilla CSS design tokens + Tailwind CSS with dark/light mode toggles.
* **Chart Visualizations:** Powered by **Recharts**:
  * `AttendanceLineChart`: Displays 6-month historical attendance trends.
  * `SubjectRadarChart`: Multi-axis radar comparing subject performance against the 75% boundary.
  * `RiskLedgerStrip`: Proportional horizontal bar showing Low/Medium/High risk distributions.
* **Primary Pages:**
  * `StudentDashboard.tsx`: Displays attendance percentage, subject tables, early risk warnings, and the **A\* Recovery Plan breakdown**.
  * `FacultyDashboard.tsx`: Departmental stats, defaulters list, student lookup, and CSV attendance upload.
  * `PredictionPage.tsx`: Interactive prediction runner displaying **Forward Chaining rules & diagnoses**.

---

## 2. Backend Architecture
* **FastAPI:** Async Python REST framework featuring automatic OpenAPI documentation generation at `/docs`.
* **Security & Authentication:**
  * **JWT (JSON Web Tokens):** Cryptographic bearer tokens with configured expiration.
  * **Bcrypt:** Salted password hashing via `passlib`.
  * **RBAC Dependencies:** Route-level permission guards (`require_student`, `require_faculty`).
* **Model Registry (`backend/ml/predict.py`):** Loads serialized model bundles (`.pkl`) lazily once during process initialization to maintain low response latencies (<10 ms).

---

## 3. Database Schema & Tables (SQLAlchemy ORM)
* **`users`:** User authentication profiles (`id`, `username`, `password_hash`, `role`).
* **`students`:** Student biographical information (`student_code`, `name`, `department`, `semester`, `distance_km`, `trend`).
* **`subjects`:** Course information (`id`, `name`, `code`, `department`, `semester`, `credits`).
* **`attendance`:** Active enrollment records (`student_id`, `subject_id`, `classes_attended`, `total_classes`, `attendance_percentage`, `leaves_taken`, `internal_marks`, `risk_label`).
* **`monthly_attendance`:** Historical month-wise points (Jan-Jun) for trend and trajectory analysis.
* **`predictions`:** Persistent log of generated AI predictions, forecasted percentages, and recommendation logs.

---

## 4. API Endpoints Reference

| Prefix | Method | Endpoint | Description |
|---|---|---|---|
| **`/api/auth`** | POST | `/login` | Authenticate user & return JWT token |
| | POST | `/register` | Register student/faculty profile |
| | GET | `/me` | Get current user context |
| **`/api/student`** | GET | `/dashboard` | Complete student dashboard (includes A\* recovery plan) |
| | GET | `/profile` | Get logged-in student profile |
| **`/api/faculty`** | GET | `/dashboard` | Institution/department analytics & defaulters list |
| | POST | `/what-if` | Simulate attendance trajectories for attend/miss scenarios |
| | POST | `/mark-attendance` | Batch attendance entry |
| | POST | `/upload-csv-attendance` | Bulk CSV attendance processing |
| **`/api/prediction`**| POST | `/predict` | Run Random Forest & K-Means prediction pipeline |
| | POST | **`/ai/a-star-recovery`** | **Run A\* Multi-Subject Recovery Planner** |
| | POST | **`/ai/hill-climbing-optimize`** | **Run Steepest-Ascent Hill Climbing Optimizer** |
| | POST | **`/ai/backward-chain-query`** | **Run Backward Chaining Goal Verification** |
| | GET | **`/ai/knowledge-rules`** | **Inspect Knowledge Base Horn Clauses** |
| **`/api/analytics`** | GET | `/overview` | Feature correlations & model importances |
| **`/api/export`** | GET | `/student/report` | Export student report (PDF/CSV) |
| | GET | `/faculty/report` | Export class/department report (PDF/CSV) |

---

# Part 3: Demo Walkthrough & Presentation Script

Use these exact steps to demonstrate your project:

### Step 1: Student Login & A* Search Demo
1. Open `http://localhost:5173` and log in with student credentials:
   * **Username:** `stu00001` | **Password:** `student123`
2. Point out the **Attendance Recovery Calculator** card.
3. **What to say:**
   > *"Notice that this student has subjects below 75%. Rather than showing a generic number, our backend executes the **A\* Search Algorithm (Module 3)**. It models this as a state-space search with an admissible heuristic $h(n)$ and calculates the exact, least-effort number of classes the student must attend in each specific course (e.g. +7 in Data Structures, +3 in DBMS) to cross the detention threshold."*

### Step 2: Prediction Page & Forward Chaining Demo
1. In the sidebar, navigate to **Prediction**.
2. Click **Run Live AI Prediction**.
3. Under the result card, highlight the **Forward Chaining** tags.
4. **What to say:**
   > *"Here our system runs both machine learning and classical AI. While the **Random Forest Classifier** predicts the high risk label and the **Regressor** forecasts the term-end percentage, our **Forward Chaining Inference Engine (Module 4)** fires rules from a Horn-Clause Knowledge Base to deduce root-cause diagnoses, distinguishing between transit issues, study habits, and academic probation."*

### Step 3: Interactive Swagger API Demonstration
1. Open `http://127.0.0.1:8000/docs` in your browser.
2. Scroll to the **Prediction** section.
3. Test **`POST /api/prediction/ai/hill-climbing-optimize`**:
   * Enter an attendance budget of `12` classes and hit **Execute**.
   * Show how Hill Climbing iteratively maximizes the objective score and outputs the optimal distribution of classes across subjects.
4. Test **`POST /api/prediction/ai/backward-chain-query`**:
   * Set `target_goal: "exam_eligibility_cleared"` and hit **Execute**.
   * Show the backward proof tree and the missing conditions required to qualify for exams.
