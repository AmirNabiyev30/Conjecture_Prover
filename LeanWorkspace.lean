import Mathlib
import Architect

open Real
open Set

/--
The solution pair for Putnam 2025 A2: the largest a and smallest b such that
a·x·(π-x) ≤ sin x ≤ b·x·(π-x) for all x ∈ [0,π] are a = 1/π and b = 4/π².
-/
@[blueprint (statement := /-- The solution pair: a = 1/π, b = 4/π². -/)]
noncomputable def putnam_2025_a2_solution : ℝ × ℝ := (1 / π, 4 / (π ^ 2))

/--
The set of lower-bound constants a' satisfying a'·x·(π-x) ≤ sin x for all x ∈ [0,π].
-/
@[blueprint (statement := /-- Lower set: {a' : ℝ | ∀ x ∈ [0,π], a'·x·(π-x) ≤ sin x} -/)]
def putnam_2025_a2_lower_set : Set ℝ :=
  {a' | ∀ x ∈ Set.Icc (0 : ℝ) π, a' * x * (π - x) ≤ sin x}

/--
The set of upper-bound constants b' satisfying sin x ≤ b'·x·(π-x) for all x ∈ [0,π].
-/
@[blueprint (statement := /-- Upper set: {b' : ℝ | ∀ x ∈ [0,π], sin x ≤ b'·x·(π-x)} -/)]
def putnam_2025_a2_upper_set : Set ℝ :=
  {b' | ∀ x ∈ Set.Icc (0 : ℝ) π, sin x ≤ b' * x * (π - x)}

/--
The candidate a = 1/π belongs to the lower set: for all x ∈ [0,π],
(1/π)·x·(π-x) ≤ sin x.
-/

@[blueprint
  (statement := /-- (1/π) ∈ lower_set, i.e. ∀ x ∈ [0,π], (1/π)·x·(π-x) ≤ sin x. -/)
  (proof := /-- This follows from the standard inequality sin x ≥ x(π-x)/π on [0,π],
  which can be proved by studying the function f(x) = sin x - x(π-x)/π and noting
  f(0) = f(π) = 0 and f is concave on [0,π] (since f''(x) = -sin x + 2/π ≤ 0
  only after checking, actually more careful analysis needed). In particular one
  can use the tangent line at 0 (slope 1) and at π (slope -1), or the fact that
  sin x ≥ (4/π²)·x·(π-x) for x ∈ [0,π] is the upper bound, and the lower bound
  requires showing sin x / (x(π-x)) ≥ 1/π with minimum at endpoints. -/)
  (proofUses := [])]
lemma lower_candidate_mem : (1 / π) ∈ putnam_2025_a2_lower_set := by
  sorry_using []

/--
The candidate b = 4/π² belongs to the upper set: for all x ∈ [0,π],
sin x ≤ (4/π²)·x·(π-x).
-/
@[blueprint
  (statement := /-- (4/π²) ∈ upper_set, i.e. ∀ x ∈ [0,π], sin x ≤ (4/π²)·x·(π-x). -/)
  (proof := /-- This is a known inequality: on [0,π], sin x ≤ (4/π²)·x·(π-x).
  Equality holds at x = π/2 and the inequality is strict elsewhere.
  One proof: the function g(x) = (4/π²)·x·(π-x) - sin x satisfies g(0) = g(π) = 0
  and g(π/2) = 0, with g''(x) = -8/π² + sin x. Since g is nonnegative at the
  endpoints and the critical point, and g' changes sign appropriately, g(x) ≥ 0. -/)
  (proofUses := [])]
lemma upper_candidate_mem : (4 / (π ^ 2)) ∈ putnam_2025_a2_upper_set := by
  sorry_using []

/--
Optimality of the lower bound: if a' belongs to the lower set, then a' ≤ 1/π.
-/
@[blueprint
  (statement := /-- ∀ a', a' ∈ lower_set → a' ≤ 1/π. -/)
  (proof := /-- For any a' in the lower set, we have a'·x·(π-x) ≤ sin x for all
  x ∈ [0,π]. For x ∈ (0,π), rearrange to a' ≤ sin x / (x·(π-x)).
  As x → 0⁺, sin x / x → 1 and 1/(π-x) → 1/π, so the RHS → 1/π.
  Since a' ≤ RHS for all x > 0, taking the limit gives a' ≤ 1/π.
  Formally, this uses `Filter.Tendsto` and the lemma that limits preserve
  non-strict inequalities. -/)
  (proofUses := [])]
lemma lower_bound_optimal : ∀ a', a' ∈ putnam_2025_a2_lower_set → a' ≤ 1 / π := by
  sorry_using []

/--
Optimality of the upper bound: if b' belongs to the upper set, then 4/π² ≤ b'.
-/
@[blueprint
  (statement := /-- ∀ b', b' ∈ upper_set → 4/π² ≤ b'. -/)
  (proof := /-- Take x = π/2 ∈ [0,π]. Then sin(π/2) = 1 and
  (π/2)·(π - π/2) = π²/4. The membership b' ∈ upper_set gives
  sin(π/2) ≤ b'·(π/2)·(π - π/2), i.e. 1 ≤ b'·π²/4, so 4/π² ≤ b'. -/)
  (proofUses := [])]
lemma upper_bound_optimal : ∀ b', b' ∈ putnam_2025_a2_upper_set → 4 / (π ^ 2) ≤ b' := by
  sorry_using []

/--
The candidate 1/π is the greatest element of the lower set.
-/
@[blueprint
  (statement := /-- IsGreatest lower_set (1/π). -/)
  (proof := /-- By `lower_candidate_mem`, 1/π ∈ lower_set.
  By `lower_bound_optimal`, 1/π is an upper bound for lower_set.
  Together these give IsGreatest. -/)
  (proofUses := [lower_candidate_mem, lower_bound_optimal])]
lemma lower_candidate_is_greatest : IsGreatest putnam_2025_a2_lower_set (1 / π) := by
  sorry_using [lower_candidate_mem, lower_bound_optimal]

/--
The candidate 4/π² is the least element of the upper set.
-/
@[blueprint
  (statement := /-- IsLeast upper_set (4/π²). -/)
  (proof := /-- By `upper_candidate_mem`, 4/π² ∈ upper_set.
  By `upper_bound_optimal`, 4/π² is a lower bound for upper_set.
  Together these give IsLeast. -/)
  (proofUses := [upper_candidate_mem, upper_bound_optimal])]
lemma upper_candidate_is_least : IsLeast putnam_2025_a2_upper_set (4 / (π ^ 2)) := by
  sorry_using [upper_candidate_mem, upper_bound_optimal]

/--
Uniqueness of greatest elements: if x and y are both greatest elements of s, then x = y.
-/
@[blueprint
  (statement := /-- If IsGreatest s x and IsGreatest s y, then x = y. -/)
  (proof := /-- From IsGreatest s x we have x ∈ s and y ≤ x (since y ∈ s from IsGreatest s y).
  From IsGreatest s y we have y ∈ s and x ≤ y. Hence x = y by antisymmetry. -/)
  (proofUses := [])]
lemma greatest_unique {α : Type} [Preorder α] {s : Set α} {x y : α}
    (hx : IsGreatest s x) (hy : IsGreatest s y) : x = y := by
  sorry_using []

/--
Uniqueness of least elements: if x and y are both least elements of s, then x = y.
-/
@[blueprint
  (statement := /-- If IsLeast s x and IsLeast s y, then x = y. -/)
  (proof := /-- From IsLeast s x we have x ∈ s and x ≤ y (since y ∈ s from IsLeast s y).
  From IsLeast s y we have y ∈ s and y ≤ x. Hence x = y by antisymmetry. -/)
  (proofUses := [])]
lemma least_unique {α : Type} [Preorder α] {s : Set α} {x y : α}
    (hx : IsLeast s x) (hy : IsLeast s y) : x = y := by
  sorry_using []

/--
Forward direction: if (a,b) equals the solution pair, then a is the greatest
element of the lower set and b is the least element of the upper set.
-/
@[blueprint
  (statement := /-- (a,b) = solution → IsGreatest lower_set a ∧ IsLeast upper_set b. -/)
  (proof := /-- If (a,b) = (1/π, 4/π²), then a = 1/π and b = 4/π².
  By `lower_candidate_is_greatest`, IsGreatest lower_set (1/π), so IsGreatest lower_set a.
  By `upper_candidate_is_least`, IsLeast upper_set (4/π²), so IsLeast upper_set b. -/)
  (proofUses := [lower_candidate_is_greatest, upper_candidate_is_least])]
lemma forward_dir (a b : ℝ) :
    ((a, b) = putnam_2025_a2_solution) →
    (IsGreatest putnam_2025_a2_lower_set a ∧ IsLeast putnam_2025_a2_upper_set b) := by
  sorry_using [lower_candidate_is_greatest, upper_candidate_is_least]

/--
Backward direction: if a is the greatest element of the lower set and b is the
least element of the upper set, then (a,b) must equal the solution pair.
-/
@[blueprint
  (statement := /-- IsGreatest lower_set a ∧ IsLeast upper_set b → (a,b) = solution. -/)
  (proof := /-- Assume IsGreatest lower_set a and IsLeast upper_set b.
  By `lower_candidate_is_greatest`, IsGreatest lower_set (1/π).
  By `greatest_unique`, a = 1/π.
  By `upper_candidate_is_least`, IsLeast upper_set (4/π²).
  By `least_unique`, b = 4/π².
  Hence (a,b) = (1/π, 4/π²) = putnam_2025_a2_solution. -/)
  (proofUses := [lower_candidate_is_greatest, upper_candidate_is_least, greatest_unique, least_unique])]
lemma backward_dir (a b : ℝ) :
    (IsGreatest putnam_2025_a2_lower_set a ∧ IsLeast putnam_2025_a2_upper_set b) →
    ((a, b) = putnam_2025_a2_solution) := by
  sorry_using [lower_candidate_is_greatest, upper_candidate_is_least, greatest_unique, least_unique]

/--
Find the largest real number a and the smallest real number b such that
a·x·(π - x) ≤ sin x ≤ b·x·(π - x) for all x ∈ [0, π].

The solution is a = 1/π, b = 4/π².
-/
@[blueprint
  (statement := /--
  (a, b) = (1/π, 4/π²) ↔
  (IsGreatest {a' : ℝ | ∀ x ∈ [0,π], a'·x·(π-x) ≤ sin x} a ∧
   IsLeast {b' : ℝ | ∀ x ∈ [0,π], sin x ≤ b'·x·(π-x)} b)
  -/)
  (proof := /-- The equivalence follows from `forward_dir` (→) and `backward_dir` (←). -/)
  (proofUses := [forward_dir, backward_dir])]
theorem putnam_2025_a2 (a b : ℝ) :
    ((a, b) = putnam_2025_a2_solution) ↔
    (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
     IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := by
  sorry_using [forward_dir, backward_dir]
