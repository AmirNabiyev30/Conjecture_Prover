import Mathlib
import Architect

open Real
open Set

noncomputable section

/--
The solution to Putnam 2025 A2: the largest `a` is `1/π` and the smallest `b` is `4/π²`.
-/
@[blueprint
  (statement := /-- The ordered pair (a,b) = (1/π, 4/π²) -/)
  (hasProof := false)]
noncomputable abbrev putnam_2025_a2_solution : ℝ × ℝ := (1 / π, 4 / π ^ 2)

@[blueprint
  (statement := /-- For all x ∈ [0,π], (1/π)·x·(π-x) ≤ sin x -/)
  (hasProof := true)
  (proof := /-- 
    Let f(x) = (1/π)·x·(π-x). Define g(x) = sin x - f(x).
    Note g(0) = g(π) = 0. Compute g'(x) = cos x - (π-2x)/π.
    Show g' has exactly one zero in (0,π) at x = π/2, where g is positive.
    Conclude g(x) ≥ 0 on [0,π].
  -/)
  (proofUses := [])]
lemma sin_lower_bound (x : ℝ) (hx : x ∈ Icc (0 : ℝ) π) : (1 / π) * x * (π - x) ≤ sin x := by
  sorry_using []

@[blueprint
  (statement := /-- For all x ∈ [0,π], sin x ≤ (4/π²)·x·(π-x) -/)
  (hasProof := true)
  (proof := /--
    Use the known inequality cos x ≤ 1 - 2x²/π² for |x| ≤ π (lemma Real.cos_le_one_sub_mul_cos_sq).
    For x ∈ [0,π], integrate this inequality from 0 to x after appropriate transformation,
    or use the double-angle identity sin x = 2 sin(x/2) cos(x/2) together with
    the inequality sin t ≤ t for t ≥ 0.
  -/)
  (proofUses := [])]
lemma sin_upper_bound (x : ℝ) (hx : x ∈ Icc (0 : ℝ) π) : sin x ≤ (4 / π ^ 2) * x * (π - x) := by
  sorry_using []

@[blueprint
  (statement := /-- The constant 1/π is an element of the set {a' | ∀ x∈[0,π], a'·x·(π-x) ≤ sin x} and is the greatest such element. -/)
  (hasProof := true)
  (proof := /--
    From sin_lower_bound, 1/π belongs to the set.
    For optimality: suppose a' > 1/π. Then as x → 0⁺, 
    sin x / (x·(π-x)) → 1/π (by sin x ∼ x as x → 0, so sin x/(x(π-x)) → 1/(π-0) = 1/π).
    Hence for a' > 1/π, eventually a'·x·(π-x) > sin x, so a' is not in the set.
  -/)
  (proofUses := [sin_lower_bound])]
lemma lower_bound_is_optimal : IsGreatest {a' : ℝ | ∀ x ∈ Icc (0 : ℝ) π, a' * x * (π - x) ≤ sin x} (1 / π) := by
  sorry_using [sin_lower_bound]

@[blueprint
  (statement := /-- The constant 4/π² is an element of the set {b' | ∀ x∈[0,π], sin x ≤ b'·x·(π-x)} and is the least such element. -/)
  (hasProof := true)
  (proof := /--
    From sin_upper_bound, 4/π² belongs to the set.
    For optimality: suppose b' < 4/π². At x = π/2,
    b'·(π/2)·(π-π/2) = b'·π²/4 < (4/π²)·π²/4 = 1 = sin(π/2).
    Hence b' is not in the set. So 4/π² is the least element.
  -/)
  (proofUses := [sin_upper_bound])]
lemma upper_bound_is_optimal : IsLeast {b' : ℝ | ∀ x ∈ Icc (0 : ℝ) π, sin x ≤ b' * x * (π - x)} (4 / π ^ 2) := by
  sorry_using [sin_upper_bound]

/--
Find the largest real number $a$ and the smallest real number $b$ such that
$$ax(\pi - x) \le \sin x \le bx(\pi - x)$$
for all $x$ in the interval $[0, \pi]$.
-/
@[blueprint
  (statement := /-- (a,b) = (1/π, 4/π²) iff a is greatest such lower bound and b is least such upper bound. -/)
  (hasProof := true)
  (proof := /-- 
    (→) If (a,b) = (1/π, 4/π²), then by lower_bound_is_optimal, a is the greatest element
    of the lower-bound set, and by upper_bound_is_optimal, b is the least element of the
    upper-bound set.
    (←) If a is greatest in the lower-bound set and b is least in the upper-bound set,
    then since 1/π ∈ lower-bound set and 4/π² ∈ upper-bound set (by sin_lower_bound and
    sin_upper_bound), we have a ≥ 1/π (since a is greatest) and also a ≤ 1/π (since 1/π
    is also in the set and a is greatest). Hence a = 1/π. Similarly b = 4/π².
  -/)
  (proofUses := [sin_lower_bound, sin_upper_bound, lower_bound_is_optimal, upper_bound_is_optimal])]
theorem putnam_2025_a2 (a b : ℝ) :
  ((a, b) = putnam_2025_a2_solution) ↔
  (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
   IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := by
  sorry_using [sin_lower_bound, sin_upper_bound, lower_bound_is_optimal, upper_bound_is_optimal]
