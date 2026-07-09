import Architect
import Mathlib
open Set
open Real
open MeasureTheory

/--
The set of all real-valued functions satisfying Putnam 1962 A2.

Solution: $f$ must be of one of four types:
1. $f(x) = a/(1-cx)^2$ for some $a \ge 0$, $c \in \mathbb{R}$;
2. $f(x) = a/(1-cx)^2$ for $x < 1/c$ and $0$ for $x \ge 1/c$, where $a \ge 0$, $c > 0$;
3. $f \ge 0$ and $f(x) = 0$ for all $x > 0$;
4. $f(0) = 0$, $f \ge 0$, and there exists $e > 0$ such that the average of $f$ over $[0,x]$ is $0$ for all $0 < x < e$.
-/
@[blueprint (statement := /-- Set of all solutions to Putnam 1962 A2 -/)]
abbrev putnam_1962_a2_solution : Set (ℝ → ℝ) :=
  {f | (∃ a c : ℝ, 0 ≤ a ∧ f = (fun x : ℝ ↦ a / (1 - c * x) ^ 2)) ∨
       (∃ a c : ℝ, 0 ≤ a ∧ 0 < c ∧ f = (fun x : ℝ ↦ if x < 1 / c then a / (1 - c * x) ^ 2 else 0)) ∨
       (0 ≤ f ∧ ∀ x : ℝ, 0 < x → f x = 0) ∨
       (∃ e : ℝ, 0 < e ∧ f 0 = 0 ∧ 0 ≤ f ∧ ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0)}

/--
The predicate `P(s, f)` means $0 \le f$ and for every $x \in s$,
$\frac{1}{x}\int_0^x f(t)\,dt = \sqrt{f(0) f(x)}$.
-/
@[blueprint (statement := /-- P(s,f): f nonnegative and average over [0,x] equals sqrt(f(0)f(x)) for all x in s -/)]
def putnam_1962_a2_P (s : Set ℝ) (f : ℝ → ℝ) : Prop :=
  0 ≤ f ∧ ∀ x ∈ s, (⨍ t in Ico (0 : ℝ) x, f t) = √(f 0 * f x)

/--
Lemma 1: A function of the form $f(x) = a/(1-cx)^2$ with $a \ge 0$, $c \le 0$
satisfies $P$ on $(0,\infty)$.
-/
@[blueprint
  (statement := /-- For a ≥ 0, c ≤ 0, the function f(x)=a/(1-cx)^2 satisfies P on (0,∞) -/)
  (proof := /-- Compute the average ∫_0^x a/(1-ct)^2 dt = a/(1-cx) and the geometric mean √(a·a/(1-cx)²) = a/(1-cx). Since 1-cx > 0 for all x ≥ 0 when c ≤ 0, equality holds. -/)
  (proofUses := [putnam_1962_a2_P])
  (hasProof := true)]
lemma putnam_1962_a2_case1_nonpositive_c (a c : ℝ) (ha : 0 ≤ a) (hc : c ≤ 0) :
    putnam_1962_a2_P (Ioi (0 : ℝ)) (fun (x : ℝ) ↦ a / (1 - c * x) ^ 2) := by
  sorry_using [putnam_1962_a2_P]

/--
Lemma 2: For $a \ge 0$, $c > 0$, the function $f(x)=a/(1-cx)^2$ satisfies $P$ on $(0, 1/c)$.
-/
@[blueprint
  (statement := /-- For a ≥ 0, c > 0, the function f(x)=a/(1-cx)^2 satisfies P on (0,1/c) -/)
  (proof := /-- Similar computation, with 1-cx > 0 on (0,1/c). -/)
  (proofUses := [putnam_1962_a2_P])
  (hasProof := true)]
lemma putnam_1962_a2_case1_positive_c (a c : ℝ) (ha : 0 ≤ a) (hc : 0 < c) :
    putnam_1962_a2_P (Ioo (0 : ℝ) (1 / c)) (fun (x : ℝ) ↦ a / (1 - c * x) ^ 2) := by
  sorry_using [putnam_1962_a2_P]

/--
Lemma 3: The truncated version (case 2 of solution) satisfies P on $(0,1/c)$.
-/
@[blueprint
  (statement := /-- Truncated function f(x)=a/(1-cx)^2 for x<1/c, 0 otherwise satisfies P on (0,1/c) -/)
  (proof := /-- On (0,1/c), the function equals the pure case 1 form, so lemma 2 applies. -/)
  (proofUses := [putnam_1962_a2_P, putnam_1962_a2_case1_positive_c])
  (hasProof := true)]
lemma putnam_1962_a2_case2_truncated (a c : ℝ) (ha : 0 ≤ a) (hc : 0 < c) :
    putnam_1962_a2_P (Ioo (0 : ℝ) (1 / c))
      (fun (x : ℝ) ↦ if x < 1 / c then a / (1 - c * x) ^ 2 else 0) := by
  sorry_using [putnam_1962_a2_P, putnam_1962_a2_case1_positive_c]

/--
Lemma 4: Any nonnegative function f with $f(x)=0$ for all $x>0$ satisfies P on $(0,\infty)$.
-/
@[blueprint
  (statement := /-- If f ≥ 0 and f(x)=0 for all x > 0, then P holds on (0,∞) -/)
  (proof := /-- Both sides are 0: average of 0 over any interval is 0, and f(0) could be anything but f(0)*0 = 0. -/)
  (proofUses := [putnam_1962_a2_P])
  (hasProof := true)]
lemma putnam_1962_a2_case3_zero (f : ℝ → ℝ) (hf_nonneg : 0 ≤ f) (hf_zero : ∀ x : ℝ, 0 < x → f x = 0) :
    putnam_1962_a2_P (Ioi (0 : ℝ)) f := by
  sorry_using [putnam_1962_a2_P]

/--
Lemma 5: Functions of case 4 satisfy P on $(0,e)$.
-/
@[blueprint
  (statement := /-- If f(0)=0, f ≥ 0, and average is 0 on (0,e), then P holds on (0,e) -/)
  (proof := /-- The average is 0 by definition, and f(0)=0 so sqrt(f(0)f(x)) = 0. -/)
  (proofUses := [putnam_1962_a2_P])
  (hasProof := true)]
lemma putnam_1962_a2_case4_zero_average (f : ℝ → ℝ) (e : ℝ) (he : 0 < e)
    (hf0 : f 0 = 0) (hf_nonneg : 0 ≤ f) (hf_avg : ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0) :
    putnam_1962_a2_P (Ioo (0 : ℝ) e) f := by
  sorry_using [putnam_1962_a2_P]

/--
Main forward direction (part 1a): If P(Ioi 0, f), then f is in the solution set on [0,∞).
-/
@[blueprint
  (statement := /-- If f satisfies the average condition on (0,∞), then f equals some solution on [0,∞) -/)
  (proof := /-- Use the structure: if f(0)=0, then case 4 applies. If f(0)>0, then the differential equation leads to the form a/(1-cx)^2 or the zero function. -/)
  (proofUses := [putnam_1962_a2_P, putnam_1962_a2_solution])
  (hasProof := true)]
lemma putnam_1962_a2_forward_global (f : ℝ → ℝ) (hP : putnam_1962_a2_P (Ioi (0 : ℝ)) f) :
    ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ici (0 : ℝ)) := by
  sorry_using [putnam_1962_a2_P, putnam_1962_a2_solution]

/--
Main forward direction (part 1b): If P(Ioo 0 e, f) for some e>0, then f is in the solution set on [0,e).
-/
@[blueprint
  (statement := /-- If f satisfies the average condition on (0,e), then f equals some solution on [0,e) -/)
  (proof := /-- Similar structure but local: if f(0)=0, case 4 applies. Otherwise solve the differential equation locally. -/)
  (proofUses := [putnam_1962_a2_P, putnam_1962_a2_solution])
  (hasProof := true)]
lemma putnam_1962_a2_forward_local (f : ℝ → ℝ) (e : ℝ) (he : 0 < e)
    (hP : putnam_1962_a2_P (Ioo (0 : ℝ) e) f) :
    ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ico (0 : ℝ) e) := by
  sorry_using [putnam_1962_a2_P, putnam_1962_a2_solution]

/--
Backward direction: Every function in the solution set satisfies P on (0,∞) or on (0,e) for some e>0.
-/
@[blueprint
  (statement := /-- Every solution function satisfies P globally or locally -/)
  (proof := /-- Check each of the four cases. Cases 1 (c≤0) and 3 satisfy P globally. Cases 1 (c>0) and 2 satisfy P locally on (0,1/c). Case 4 satisfies P locally on (0,e). -/)
  (proofUses := [putnam_1962_a2_P, putnam_1962_a2_solution, putnam_1962_a2_case1_nonpositive_c, putnam_1962_a2_case2_truncated, putnam_1962_a2_case3_zero, putnam_1962_a2_case4_zero_average])
  (hasProof := true)]
lemma putnam_1962_a2_backward (f : ℝ → ℝ) (hf : f ∈ putnam_1962_a2_solution) :
    putnam_1962_a2_P (Ioi (0 : ℝ)) f ∨ (∃ e : ℝ, 0 < e ∧ putnam_1962_a2_P (Ioo (0 : ℝ) e) f) := by
  sorry_using [putnam_1962_a2_P, putnam_1962_a2_solution, putnam_1962_a2_case1_nonpositive_c, putnam_1962_a2_case2_truncated, putnam_1962_a2_case3_zero, putnam_1962_a2_case4_zero_average]

/--
**Putnam 1962 A2**: Find every real-valued function $f$ whose domain is an interval $I$ (finite or infinite) having $0$ as a left-hand endpoint, such that for every positive member $x$ of $I$ the average of $f$ over the closed interval $[0,x]$ is equal to the geometric mean of the numbers $f(0)$ and $f(x)$.

This theorem formalizes the characterization: the solution set `putnam_1962_a2_solution` exactly captures all such functions.
-/
@[blueprint
  (statement := /-- Putnam 1962 A2 characterization theorem -/)
  (proof := /-- Combine forward and backward directions. -/)
  (proofUses := [putnam_1962_a2_P, putnam_1962_a2_solution, putnam_1962_a2_forward_global, putnam_1962_a2_forward_local, putnam_1962_a2_backward])
  (hasProof := true)]
theorem putnam_1962_a2
    (P : Set ℝ → (ℝ → ℝ) → Prop)
    (P_def : ∀ s f, P s f ↔ 0 ≤ f ∧ ∀ x ∈ s, (⨍ t in Ico (0 : ℝ) x, f t) = √(f 0 * f x)) :
    (∀ f,
      (P (Ioi (0 : ℝ)) f → ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ici (0 : ℝ))) ∧
      (∀ e > 0, P (Ioo (0 : ℝ) e) f → ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ico (0 : ℝ) e))) ∧
    ∀ f ∈ putnam_1962_a2_solution, P (Ioi (0 : ℝ)) f ∨ (∃ e > 0, P (Ioo (0 : ℝ) e) f) := by
  sorry_using [putnam_1962_a2_P, putnam_1962_a2_solution, putnam_1962_a2_forward_global, putnam_1962_a2_forward_local, putnam_1962_a2_backward]
