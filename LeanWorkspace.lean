import Mathlib
import Architect

/-- A sequence `a : ℕ → ℝ` is non-decreasing if `a n ≤ a (n+1)` for all `n`. -/
@[blueprint (statement := /-- A sequence `a : ℕ → ℝ` is non-decreasing if `a n ≤ a (n+1)` for all `n`. -/)]
def non_decreasing (a : ℕ → ℝ) : Prop :=
  ∀ n : ℕ, a n ≤ a (n + 1)

/-- A sequence `a : ℕ → ℝ` is non-increasing if `a (n+1) ≤ a n` for all `n`. -/
@[blueprint (statement := /-- A sequence `a : ℕ → ℝ` is non-increasing if `a (n+1) ≤ a n` for all `n`. -/)]
def non_increasing (a : ℕ → ℝ) : Prop :=
  ∀ n : ℕ, a (n + 1) ≤ a n

/-- A sequence `a : ℕ → ℝ` is monotone if it is either non-decreasing or non-increasing. -/
@[blueprint (statement := /-- A sequence `a : ℕ → ℝ` is monotone if it is either non-decreasing or non-increasing. -/)]
def monotone_sequence (a : ℕ → ℝ) : Prop :=
  non_decreasing a ∨ non_increasing a

/-- A sequence `a : ℕ → ℝ` is bounded if there exists `M : ℝ` such that `|a n| ≤ M` for all `n`. -/
@[blueprint (statement := /-- A sequence `a : ℕ → ℝ` is bounded if there exists `M : ℝ` such that `|a n| ≤ M` for all `n`. -/)]
def bounded_sequence (a : ℕ → ℝ) : Prop :=
  ∃ M : ℝ, ∀ n : ℕ, |a n| ≤ M

/-- A sequence `a : ℕ → ℝ` has limit `L : ℝ` if for every `ε > 0` there exists `N` such that for all `n ≥ N`, `|a n - L| < ε`. -/
@[blueprint (statement := /-- A sequence `a : ℕ → ℝ` has limit `L : ℝ` if for every `ε > 0` there exists `N` such that for all `n ≥ N`, `|a n - L| < ε`. -/)]
def has_limit (a : ℕ → ℝ) (L : ℝ) : Prop :=
  ∀ ε : ℝ, 0 < ε → ∃ N : ℕ, ∀ n : ℕ, N ≤ n → |a n - L| < ε

/-- If a non-decreasing sequence `a : ℕ → ℝ` is bounded above, then it converges to its supremum. -/
@[blueprint
  (statement := /-- Let `a : ℕ → ℝ` be a non-decreasing sequence that is bounded above. Then `a` has a finite limit (namely, `sup` of its values). -/)
  (proof := /-- Let `S := sup_{n} a n`. Since `a` is bounded above, `S` is finite. For any `ε > 0`, `S - ε` is not an upper bound, so there exists `N` with `S - ε < a N`. By monotonicity, for all `n ≥ N`, `S - ε < a n ≤ S`, hence `|a n - S| < ε`. Thus `a` converges to `S`. -/)]
lemma non_decreasing_bounded_above_converges (a : ℕ → ℝ) (h_nondec : non_decreasing a) (h_bounded : bounded_sequence a) :
  ∃ L : ℝ, has_limit a L := by
  sorry_using [non_decreasing, bounded_sequence, has_limit]

/-- If a non-increasing sequence `a : ℕ → ℝ` is bounded below, then it converges to its infimum. -/
@[blueprint
  (statement := /-- Let `a : ℕ → ℝ` be a non-increasing sequence that is bounded below. Then `a` has a finite limit (namely, `inf` of its values). -/)
  (proof := /-- Let `I := inf_{n} a n`. Since `a` is bounded below, `I` is finite. For any `ε > 0`, `I + ε` is not a lower bound, so there exists `N` with `a N < I + ε`. By monotonicity, for all `n ≥ N`, `I ≤ a n ≤ a N < I + ε`, hence `|a n - I| < ε`. Thus `a` converges to `I`. -/)]
lemma non_increasing_bounded_below_converges (a : ℕ → ℝ) (h_noninc : non_increasing a) (h_bounded : bounded_sequence a) :
  ∃ L : ℝ, has_limit a L := by
  sorry_using [non_increasing, bounded_sequence, has_limit]

/-- A convergent sequence is bounded. -/
@[blueprint
  (statement := /-- If a sequence `a : ℕ → ℝ` has a limit `L : ℝ`, then `a` is bounded. -/)
  (proof := /-- Choose `ε = 1`. There exists `N` such that for all `n ≥ N`, `|a n - L| < 1`. Then for `n ≥ N`, `|a n| ≤ |a n - L| + |L| < 1 + |L|`. For `n < N`, we have finitely many values, so take the maximum of their absolute values and `1 + |L|` as the bound. -/)]
lemma convergent_implies_bounded (a : ℕ → ℝ) (L : ℝ) (h_lim : has_limit a L) : bounded_sequence a := by
  sorry_using [has_limit, bounded_sequence]

/-- If a monotone sequence `a : ℕ → ℝ` is bounded, then it has a finite limit. -/
@[blueprint
  (statement := /-- Let `a : ℕ → ℝ` be monotone and bounded. Then `a` has a finite limit. -/)
  (proof := /-- By `monotone_sequence`, either `a` is non-decreasing or non-increasing. In the non-decreasing case, `non_decreasing_bounded_above_converges` gives a limit. In the non-increasing case, `non_increasing_bounded_below_converges` gives a limit. -/)]
lemma monotone_bounded_implies_convergent (a : ℕ → ℝ) (h_mono : monotone_sequence a) (h_bounded : bounded_sequence a) :
  ∃ L : ℝ, has_limit a L := by
  sorry_using [monotone_sequence, non_decreasing_bounded_above_converges, non_increasing_bounded_below_converges, bounded_sequence]

/-- Monotone Convergence Theorem: For a monotone sequence of real numbers, the following are equivalent:
   (1) The sequence has a finite limit in ℝ.
   (2) The sequence is bounded. -/
@[blueprint
  (statement := /-- Let `a : ℕ → ℝ` be a monotone sequence. Then `a` has a finite limit if and only if `a` is bounded. -/)
  (proof := /-- (→) If `a` has a limit, then `convergent_implies_bounded` shows `a` is bounded.
     (←) If `a` is bounded, then `monotone_bounded_implies_convergent` shows `a` has a finite limit. -/)]
theorem monotone_convergence_theorem (a : ℕ → ℝ) (h_mono : monotone_sequence a) :
  ((∃ L : ℝ, has_limit a L) ↔ bounded_sequence a) := by
  sorry_using [monotone_bounded_implies_convergent, convergent_implies_bounded, bounded_sequence, has_limit]
