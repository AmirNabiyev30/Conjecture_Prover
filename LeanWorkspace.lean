import Mathlib
import Architect

open MeasureTheory Set

open scoped Real

/--
The set of all real-valued functions satisfying the Putnam 1962 A2 classification.
These are the functions that satisfy the average-geometric-mean condition on some interval containing 0.
-/
@[blueprint (statement := /-- The four types of solutions to the Putnam 1962 A2 functional equation -/)]
abbrev putnam_1962_a2_solution : Set (ℝ → ℝ) :=
  {f | (∃ a c : ℝ, 0 ≤ a ∧ f = (fun x : ℝ ↦ a / (1 - c * x) ^ 2)) ∨
       (∃ a c : ℝ, 0 ≤ a ∧ 0 < c ∧ f = (fun x : ℝ ↦ if x < 1 / c then a / (1 - c * x) ^ 2 else 0)) ∨
       (0 ≤ f ∧ ∀ x : ℝ, 0 < x → f x = 0) ∨
       (∃ e : ℝ, 0 < e ∧ f 0 = 0 ∧ 0 ≤ f ∧ ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0)}

/--
The property that f satisfies the average-geometric-mean condition on the set s.
That is: f is nonnegative on the domain and for every positive x in s,
the average of f over [0, x] equals sqrt(f(0) * f(x)).
-/
@[blueprint (statement := /-- The property that f satisfies the average-geometric-mean condition on the set s -/)]
def average_geometric_condition (s : Set ℝ) (f : ℝ → ℝ) : Prop :=
  0 ≤ f ∧ ∀ x ∈ s, 0 < x → (⨍ t in Ico (0 : ℝ) x, f t) = √(f 0 * f x)

/--
If f(0) = 0 and the condition holds on (0,∞), then the average of f over [0,x] is 0 for all x>0.
-/
@[blueprint
  (statement := /-- If f(0) = 0 and the condition holds on Ioi 0, then the average of f over [0,x] is zero for all x > 0 -/)
  (proof := /-- Direct from the condition: since f(0)=0, sqrt(f(0)*f(x)) = sqrt(0) = 0. -/)
  (proofUses := [average_geometric_condition])]
lemma average_zero_when_f0_zero_global (f : ℝ → ℝ) (hf : average_geometric_condition (Ioi 0) f) (hf0 : f 0 = 0) :
    ∀ x > 0, (⨍ t in Ico (0 : ℝ) x, f t) = 0 := by
  sorry_using [average_geometric_condition]

/--
If the average of f over [0,x] is zero for all x>0 in an interval, and f is nonnegative,
then f(x)=0 for all x>0 in that interval (under mild measurability/integrability assumptions).
-/
@[blueprint
  (statement := /-- If the average of f over [0,x] is zero for all x > 0 in an interval, and f ≥ 0, then f is zero a.e. on that interval -/)
  (proof := /-- Since f ≥ 0, its integral over [0,x] is zero, so f is zero a.e. on [0,x] for each x. -/)
  (proofUses := [])]
lemma zero_average_implies_zero (f : ℝ → ℝ) (s : Set ℝ) (hs : s ⊆ Ioi 0) (hf_nonneg : 0 ≤ f)
    (h_avg_zero : ∀ x ∈ s, 0 < x → (⨍ t in Ico (0 : ℝ) x, f t) = 0) : ∀ x ∈ s, 0 < x → f x = 0 := by
  sorry_using []

/--
If f(0) = 0 and the condition holds on Ioi 0, then f(x) = 0 for all x > 0.
This covers solution type 3.
-/
@[blueprint
  (statement := /-- If f(0) = 0 and the condition holds on (0,∞), then f(x) = 0 for all x > 0 -/)
  (proof := /-- By `average_zero_when_f0_zero_global`, the average is zero for all x > 0. Then by `zero_average_implies_zero`, f(x) = 0 for all x > 0. -/)
  (proofUses := [average_zero_when_f0_zero_global, zero_average_implies_zero])]
lemma f_zero_when_f0_zero_global (f : ℝ → ℝ) (hf : average_geometric_condition (Ioi 0) f) (hf0 : f 0 = 0) :
    ∀ x > 0, f x = 0 := by
  sorry_using [average_zero_when_f0_zero_global, zero_average_implies_zero]

/--
If f(0) > 0 and the condition holds on Ioi 0, then F(x) = ∫_0^x f satisfies a differential equation:
F'(x) = (F(x)/x)^2 / f(0).
This follows from squaring the condition and differentiating.
-/
@[blueprint
  (statement := /-- If f(0) > 0, then from the condition we get a relation (F(x)/x)^2 = f(0)*f(x) where F(x)=∫_0^x f -/)
  (proof := /-- Square both sides of the condition: (⨍_0^x f)^2 = f(0)*f(x). Multiply by x^2. -/)
  (proofUses := [average_geometric_condition])]
lemma squared_condition_global (f : ℝ → ℝ) (hf : average_geometric_condition (Ioi 0) f) (hf0_pos : 0 < f 0) (x : ℝ) (hx : 0 < x) :
    ((⨍ t in Ico (0 : ℝ) x, f t) ^ 2) = f 0 * f x := by
  sorry_using [average_geometric_condition]

/--
If f(0) > 0 and the condition holds on Ioi 0, then we can solve the functional equation
to get f(x) = a/(1 - c*x)^2 for some a ≥ 0, c ∈ ℝ.
-/
@[blueprint
  (statement := /-- If f(0) > 0 and the condition holds on (0,∞), then f has the form a/(1-cx)^2 -/)
  (proof := /-- Solve the differential equation derived from squaring the condition. The key step is setting u(x) = (F(x)/x) and getting u'(x) = u(x)^2/(f(0)*x), leading to 1/u(x) = c - x/f(0). -/)
  (proofUses := [squared_condition_global])]
lemma solution_form_global (f : ℝ → ℝ) (hf : average_geometric_condition (Ioi 0) f) (hf0_pos : 0 < f 0) :
    ∃ a c : ℝ, 0 ≤ a ∧ f = (fun x : ℝ ↦ a / ((1 : ℝ) - c * x) ^ 2) := by
  sorry_using [squared_condition_global]

/--
If f(0) = 0 and the condition holds on a small interval (0,e), then the average is zero on (0,e).
-/
@[blueprint
  (statement := /-- If f(0) = 0 and the condition holds on Ioo 0 e, then the average of f over [0,x] is zero for all x in (0,e) -/)
  (proof := /-- Direct from the condition: since f(0)=0, sqrt(f(0)*f(x)) = 0. -/)
  (proofUses := [average_geometric_condition])]
lemma average_zero_when_f0_zero_local (f : ℝ → ℝ) (e : ℝ) (he : 0 < e) (hf : average_geometric_condition (Ioo 0 e) f) (hf0 : f 0 = 0) :
    ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0 := by
  sorry_using [average_geometric_condition]

/--
If f(0) > 0 and the condition holds on (0,e), then f has form a/(1-cx)^2 on (0,e) for some a,c.
-/
@[blueprint
  (statement := /-- If f(0) > 0 and the condition holds on (0,e), then f(a)/(1-cx)^2 on (0,e) -/)
  (proof := /-- Same differential equation approach as the global case, but on a restricted interval. -/)
  (proofUses := [squared_condition_global, average_geometric_condition])]
lemma solution_form_local (f : ℝ → ℝ) (e : ℝ) (he : 0 < e) (hf : average_geometric_condition (Ioo 0 e) f) (hf0_pos : 0 < f 0) :
    ∃ a c : ℝ, 0 ≤ a ∧ Set.EqOn f (fun x : ℝ ↦ a / ((1 : ℝ) - c * x) ^ 2) (Ioo 0 e) := by
  sorry_using [squared_condition_global, average_geometric_condition]

/--
If f has the form a/(1-cx)^2 for all x (solution type 1), then it satisfies the condition on (0,∞).
-/
@[blueprint
  (statement := /-- Functions of the form a/(1-cx)^2 with a ≥ 0 satisfy the condition on (0,∞) -/)
  (proof := /-- Direct computation: the average of a/(1-cx)^2 over [0,x] is a/(1-cx), and sqrt(f(0)*f(x)) = sqrt(a * a/(1-cx)^2) = a/(1-cx) for a ≥ 0. -/)
  (proofUses := [average_geometric_condition])]
lemma type_one_satisfies_global (a c : ℝ) (ha : 0 ≤ a) :
    average_geometric_condition (Ioi 0) (fun x : ℝ ↦ a / ((1 : ℝ) - c * x) ^ 2) := by
  sorry_using [average_geometric_condition]

/--
If f has the form a/(1-cx)^2 for x < 1/c and 0 otherwise (solution type 2), then it satisfies the condition on (0,∞).
-/
@[blueprint
  (statement := /-- Functions of the truncated form a/(1-cx)^2 with a ≥ 0, c > 0 satisfy the condition on (0,∞) -/)
  (proof := /-- For x < 1/c this reduces to type 1. For x ≥ 1/c, the average is (1/x)*a*∫_0^{1/c} 1/(1-ct)^2 dt = a/(c*x*(1-c*(1/c)))... This needs careful computation. -/)
  (proofUses := [average_geometric_condition])]
lemma type_two_satisfies_global (a c : ℝ) (ha : 0 ≤ a) (hc : 0 < c) :
    average_geometric_condition (Ioi 0) (fun x : ℝ ↦ if x < 1 / c then a / ((1 : ℝ) - c * x) ^ 2 else 0) := by
  sorry_using [average_geometric_condition]

/--
If f is nonnegative and f(x) = 0 for all x > 0 (solution type 3), then it satisfies the condition on (0,∞).
-/
@[blueprint
  (statement := /-- Nonnegative functions vanishing on (0,∞) satisfy the condition on (0,∞) -/)
  (proof := /-- The average over [0,x] is 0 for any x > 0, and sqrt(f(0)*f(x)) = sqrt(f(0)*0) = 0. -/)
  (proofUses := [average_geometric_condition])]
lemma type_three_satisfies_global (f : ℝ → ℝ) (hf_nonneg : 0 ≤ f) (hf_zero : ∀ x > 0, f x = 0) :
    average_geometric_condition (Ioi 0) f := by
  sorry_using [average_geometric_condition]

/--
If f(0) = 0, f ≥ 0, and the average of f over [0,x] is 0 for all x in (0,e) (solution type 4),
then the condition holds on (0,e).
-/
@[blueprint
  (statement := /-- Type 4 functions satisfy the condition on (0,e) -/)
  (proof := /-- Direct: f(0) = 0, so RHS is 0. The average is 0 by definition of type 4. -/)
  (proofUses := [average_geometric_condition])]
lemma type_four_satisfies_local (f : ℝ → ℝ) (e : ℝ) (he : 0 < e) (hf0 : f 0 = 0) (hf_nonneg : 0 ≤ f)
    (h_avg_zero : ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0) :
    average_geometric_condition (Ioo 0 e) f := by
  sorry_using [average_geometric_condition]

/--
If f satisfies the condition on (0,∞), then f is in the solution set.
This is the first direction of the classification.
-/
@[blueprint
  (statement := /-- Any function satisfying the condition on (0,∞) belongs to the solution set -/)
  (proof := /-- Case analysis on f(0). If f(0) = 0, then by `f_zero_when_f0_zero_global`, f is type 3. If f(0) > 0, then by `solution_form_global`, f is type 1. -/)
  (proofUses := [f_zero_when_f0_zero_global, solution_form_global, putnam_1962_a2_solution])]
lemma global_solution_membership (f : ℝ → ℝ) (hf : average_geometric_condition (Ioi 0) f) :
    f ∈ putnam_1962_a2_solution := by
  sorry_using [f_zero_when_f0_zero_global, solution_form_global, putnam_1962_a2_solution]

/--
If f satisfies the condition on (0,e) for some e>0, then f is in the solution set.
This is the second direction of the classification.
-/
@[blueprint
  (statement := /-- Any function satisfying the condition on (0,e) for some e>0 belongs to the solution set -/)
  (proof := /-- Case analysis on f(0). If f(0) = 0, then either the function is type 4 (average zero on (0,e)) or... Additional case analysis needed. If f(0) > 0, then f matches type 1 or 2 on (0,e). -/)
  (proofUses := [average_zero_when_f0_zero_local, solution_form_local, putnam_1962_a2_solution])]
lemma local_solution_membership (f : ℝ → ℝ) (e : ℝ) (he : 0 < e) (hf : average_geometric_condition (Ioo 0 e) f) :
    f ∈ putnam_1962_a2_solution := by
  sorry_using [average_zero_when_f0_zero_local, solution_form_local, putnam_1962_a2_solution]

/--
If f is in the solution set, then either f satisfies the condition on (0,∞) or on (0,e) for some e>0.
This is the converse direction of the classification.
-/
@[blueprint
  (statement := /-- Every function in the solution set satisfies the condition on some interval -/)
  (proof := /-- Case analysis on which type f belongs to. Types 1,2,3 satisfy on (0,∞). Type 4 satisfies on (0,e) by definition. -/)
  (proofUses := [type_one_satisfies_global, type_two_satisfies_global, type_three_satisfies_global, type_four_satisfies_local, putnam_1962_a2_solution])]
lemma solution_satisfies_some_interval (f : ℝ → ℝ) (hf : f ∈ putnam_1962_a2_solution) :
    average_geometric_condition (Ioi 0) f ∨ (∃ e > 0, average_geometric_condition (Ioo 0 e) f) := by
  sorry_using [type_one_satisfies_global, type_two_satisfies_global, type_three_satisfies_global, type_four_satisfies_local, putnam_1962_a2_solution]

/--
The main theorem of Putnam 1962 A2.
-/
@[blueprint
  (statement := /-- The full classification theorem: (1) Every function satisfying the condition on (0,∞) agrees with a solution on [0,∞). (2) Every function satisfying the condition on (0,e) agrees with a solution on [0,e). (3) Every solution satisfies the condition on some interval. -/)
  (proof := /-- Combine the lemmas: `global_solution_membership` gives that f is in the solution set, and then `EqOn` on the relevant interval follows from the construction. The converse is `solution_satisfies_some_interval`. -/)
  (proofUses := [global_solution_membership, local_solution_membership, solution_satisfies_some_interval, average_geometric_condition, putnam_1962_a2_solution])]
theorem putnam_1962_a2
    (P : Set ℝ → (ℝ → ℝ) → Prop)
    (P_def : ∀ s f, P s f ↔ 0 ≤ f ∧ ∀ x ∈ s, 0 < x → (⨍ t in Ico (0 : ℝ) x, f t) = √(f 0 * f x)) :
    (∀ f,
      (P (Ioi 0) f → ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ici 0)) ∧
      (∀ e > 0, P (Ioo 0 e) f → ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ico 0 e))) ∧
    ∀ f ∈ putnam_1962_a2_solution, P (Ioi 0) f ∨ (∃ e > 0, P (Ioo 0 e) f) := by
  sorry_using [global_solution_membership, local_solution_membership, solution_satisfies_some_interval, average_geometric_condition, putnam_1962_a2_solution]
