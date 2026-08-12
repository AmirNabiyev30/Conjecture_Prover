import Mathlib
import Architect

open Real

/-
Putnam 2025 A2.

Find the largest real number `a` and the smallest real number `b` such that

  a * x * (π - x) ≤ sin x ≤ b * x * (π - x)

for all `x ∈ [0, π]`.

Original Lean target:

  theorem putnam_2025_a2 (a b : ℝ) :
    ((a, b) = putnam_2025_a2_solution) ↔
    (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
     IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := sorry

The optimal pair is `(1 / π, 4 / π ^ 2)`.
-/

@[blueprint (statement := /-- The solution pair for Putnam 2025 A2: the largest admissible lower constant is \(1/\pi\) and the smallest admissible upper constant is \(4/\pi^2\). -/)]
noncomputable abbrev putnam_2025_a2_solution : ℝ × ℝ :=
  (1 / π, 4 / π ^ 2)

@[blueprint (statement := /-- The set of lower constants \(a'\) satisfying \(a' x(\pi-x) \le \sin x\) for every \(x \in [0,\pi]\). -/)]
def putnam_2025_a2_lowerSet : Set ℝ :=
  {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x}

@[blueprint (statement := /-- The set of upper constants \(b'\) satisfying \(\sin x \le b' x(\pi-x)\) for every \(x \in [0,\pi]\). -/)]
def putnam_2025_a2_upperSet : Set ℝ :=
  {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)}

@[blueprint
  (statement := /-- For every \(x \in [0,\pi]\), the factor \(x(\pi-x)\) is nonnegative. -/)
  (proof := /-- If \(x \in [0,\pi]\), then both \(x \ge 0\) and \(\pi-x \ge 0\); the product of two nonnegative reals is nonnegative. -/)
  (proofUses := [])]
lemma putnam_2025_a2_x_pi_minus_x_nonneg {x : ℝ} (hx : x ∈ Set.Icc 0 π) :
    0 ≤ x * (π - x) := by
  sorry_using []

@[blueprint
  (statement := /-- For every \(x \in [0,\pi]\), one has \((1/\pi)x(\pi-x) \le \sin x\). -/)
  (proof := /-- This is the sharp lower comparison for sine on \([0,\pi]\). It follows from the concavity of \(\sin\) on \([0,\pi]\) together with its behavior at the endpoints \(0\) and \(\pi\). -/)
  (proofUses := [])]
lemma putnam_2025_a2_sin_lower_bound {x : ℝ} (hx : x ∈ Set.Icc 0 π) :
    (1 / π) * x * (π - x) ≤ sin x := by
  sorry_using []

@[blueprint
  (statement := /-- For every \(x \in [0,\pi]\), one has \(\sin x \le (4/\pi^2)x(\pi-x)\). -/)
  (proof := /-- This is the sharp upper comparison for sine on \([0,\pi]\), with equality at \(x=\pi/2\). -/)
  (proofUses := [])]
lemma putnam_2025_a2_sin_upper_bound {x : ℝ} (hx : x ∈ Set.Icc 0 π) :
    sin x ≤ (4 / π ^ 2) * x * (π - x) := by
  sorry_using []

@[blueprint
  (statement := /-- If \(a' \le 1/\pi\), then \(a'\) belongs to the lower set: the inequality \(a' x(\pi-x) \le \sin x\) holds on all of \([0,\pi]\). -/)
  (proof := /-- For \(x \in [0,\pi]\) the factor \(x(\pi-x)\) is nonnegative by `putnam_2025_a2_x_pi_minus_x_nonneg`, so multiplying `a' ≤ 1/π` by it gives \(a' x(\pi-x) \le (1/\pi)x(\pi-x)\). Then apply `putnam_2025_a2_sin_lower_bound`. -/)
  (proofUses := [putnam_2025_a2_lowerSet, putnam_2025_a2_x_pi_minus_x_nonneg, putnam_2025_a2_sin_lower_bound])]
lemma putnam_2025_a2_mem_lowerSet_of_le {a' : ℝ} (ha : a' ≤ 1 / π) :
    a' ∈ putnam_2025_a2_lowerSet := by
  sorry_using [putnam_2025_a2_lowerSet, putnam_2025_a2_x_pi_minus_x_nonneg, putnam_2025_a2_sin_lower_bound]

@[blueprint
  (statement := /-- If \(a'\) belongs to the lower set, then \(a' \le 1/\pi\). -/)
  (proof := /-- The membership assumption says \(a' \le \sin x/(x(\pi-x))\) for every \(x \in (0,\pi)\). Letting \(x \to 0^+\) and using \(\sin x/(x(\pi-x)) \to 1/\pi\) gives the conclusion. -/)
  (proofUses := [putnam_2025_a2_lowerSet])]
lemma putnam_2025_a2_le_of_mem_lowerSet {a' : ℝ} (ha : a' ∈ putnam_2025_a2_lowerSet) :
    a' ≤ 1 / π := by
  sorry_using [putnam_2025_a2_lowerSet]

@[blueprint
  (statement := /-- If \(b' \ge 4/\pi^2\), then \(b'\) belongs to the upper set: the inequality \(\sin x \le b' x(\pi-x)\) holds on all of \([0,\pi]\). -/)
  (proof := /-- For \(x \in [0,\pi]\) the factor \(x(\pi-x)\) is nonnegative by `putnam_2025_a2_x_pi_minus_x_nonneg`, so multiplying `4/π^2 ≤ b'` by it and applying `putnam_2025_a2_sin_upper_bound` gives the desired inequality. -/)
  (proofUses := [putnam_2025_a2_upperSet, putnam_2025_a2_x_pi_minus_x_nonneg, putnam_2025_a2_sin_upper_bound])]
lemma putnam_2025_a2_mem_upperSet_of_ge {b' : ℝ} (hb : 4 / π ^ 2 ≤ b') :
    b' ∈ putnam_2025_a2_upperSet := by
  sorry_using [putnam_2025_a2_upperSet, putnam_2025_a2_x_pi_minus_x_nonneg, putnam_2025_a2_sin_upper_bound]

@[blueprint
  (statement := /-- If \(b'\) belongs to the upper set, then \(4/\pi^2 \le b'\). -/)
  (proof := /-- Evaluate the membership inequality at \(x=\pi/2\): since \(\sin(\pi/2)=1\) and \(x(\pi-x)=\pi^2/4\), one obtains \(1 \le b' \pi^2/4\), hence \(4/\pi^2 \le b'\). -/)
  (proofUses := [putnam_2025_a2_upperSet])]
lemma putnam_2025_a2_ge_of_mem_upperSet {b' : ℝ} (hb : b' ∈ putnam_2025_a2_upperSet) :
    4 / π ^ 2 ≤ b' := by
  sorry_using [putnam_2025_a2_upperSet]

@[blueprint
  (statement := /-- The lower set is exactly the interval \((-\infty, 1/\pi]\). -/)
  (proof := /-- Combine the two implications: membership gives \(a' \le 1/\pi\) by `putnam_2025_a2_le_of_mem_lowerSet`, and conversely \(a' \le 1/\pi\) gives membership by `putnam_2025_a2_mem_lowerSet_of_le`. -/)
  (proofUses := [putnam_2025_a2_lowerSet, putnam_2025_a2_mem_lowerSet_of_le, putnam_2025_a2_le_of_mem_lowerSet])]
lemma putnam_2025_a2_lowerSet_eq :
    putnam_2025_a2_lowerSet = Set.Iic (1 / π) := by
  sorry_using [putnam_2025_a2_lowerSet, putnam_2025_a2_mem_lowerSet_of_le, putnam_2025_a2_le_of_mem_lowerSet]

@[blueprint
  (statement := /-- The upper set is exactly the interval \([4/\pi^2, \infty)\). -/)
  (proof := /-- Combine the two implications: membership gives \(4/\pi^2 \le b'\) by `putnam_2025_a2_ge_of_mem_upperSet`, and conversely \(4/\pi^2 \le b'\) gives membership by `putnam_2025_a2_mem_upperSet_of_ge`. -/)
  (proofUses := [putnam_2025_a2_upperSet, putnam_2025_a2_mem_upperSet_of_ge, putnam_2025_a2_ge_of_mem_upperSet])]
lemma putnam_2025_a2_upperSet_eq :
    putnam_2025_a2_upperSet = Set.Ici (4 / π ^ 2) := by
  sorry_using [putnam_2025_a2_upperSet, putnam_2025_a2_mem_upperSet_of_ge, putnam_2025_a2_ge_of_mem_upperSet]

@[blueprint
  (statement := /-- For every real \(a\), the statement `IsGreatest putnam_2025_a2_lowerSet a` is equivalent to \(a = 1/\pi\). -/)
  (proof := /-- Rewrite the lower set as `Set.Iic (1/π)` using `putnam_2025_a2_lowerSet_eq`; the greatest element of `Set.Iic (1/π)` is exactly `1/π`. -/)
  (proofUses := [putnam_2025_a2_lowerSet_eq])]
lemma putnam_2025_a2_isGreatest_lowerSet_iff (a : ℝ) :
    IsGreatest putnam_2025_a2_lowerSet a ↔ a = 1 / π := by
  sorry_using [putnam_2025_a2_lowerSet_eq]

@[blueprint
  (statement := /-- For every real \(b\), the statement `IsLeast putnam_2025_a2_upperSet b` is equivalent to \(b = 4/\pi^2\). -/)
  (proof := /-- Rewrite the upper set as `Set.Ici (4/π^2)` using `putnam_2025_a2_upperSet_eq`; the least element of `Set.Ici (4/π^2)` is exactly `4/π^2`. -/)
  (proofUses := [putnam_2025_a2_upperSet_eq])]
lemma putnam_2025_a2_isLeast_upperSet_iff (b : ℝ) :
    IsLeast putnam_2025_a2_upperSet b ↔ b = 4 / π ^ 2 := by
  sorry_using [putnam_2025_a2_upperSet_eq]

@[blueprint
  (statement := /-- For all reals \(a,b\), the pair \((a,b)\) equals `putnam_2025_a2_solution` exactly when \(a=1/\pi\) and \(b=4/\pi^2\). -/)
  (proof := /-- Unfold `putnam_2025_a2_solution` and use `Prod.ext_iff`: two ordered pairs are equal iff their components are equal. -/)
  (proofUses := [putnam_2025_a2_solution])]
lemma putnam_2025_a2_pair_eq_solution_iff (a b : ℝ) :
    (a, b) = putnam_2025_a2_solution ↔ a = 1 / π ∧ b = 4 / π ^ 2 := by
  sorry_using [putnam_2025_a2_solution]

@[blueprint
  (statement := /-- Putnam 2025 A2: the pair \((a,b)\) is the optimal solution iff \(a\) is the greatest admissible lower constant and \(b\) is the least admissible upper constant. -/)
  (proof := /-- The left side is equivalent to \(a=1/\pi \wedge b=4/\pi^2\) by `putnam_2025_a2_pair_eq_solution_iff`. By definition the displayed membership sets are `putnam_2025_a2_lowerSet` and `putnam_2025_a2_upperSet`; the two components on the right are equivalent to \(a=1/\pi\) and \(b=4/\pi^2\) by `putnam_2025_a2_isGreatest_lowerSet_iff` and `putnam_2025_a2_isLeast_upperSet_iff`. -/)
  (proofUses := [putnam_2025_a2_lowerSet, putnam_2025_a2_upperSet, putnam_2025_a2_pair_eq_solution_iff, putnam_2025_a2_isGreatest_lowerSet_iff, putnam_2025_a2_isLeast_upperSet_iff])]
theorem putnam_2025_a2 (a b : ℝ) :
    ((a, b) = putnam_2025_a2_solution) ↔
    (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
     IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := by
  sorry_using [putnam_2025_a2_lowerSet, putnam_2025_a2_upperSet, putnam_2025_a2_pair_eq_solution_iff, putnam_2025_a2_isGreatest_lowerSet_iff, putnam_2025_a2_isLeast_upperSet_iff]
