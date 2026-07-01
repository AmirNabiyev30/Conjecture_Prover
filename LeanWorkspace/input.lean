/-Do not edit this line and 2 lines below-/
import Mathlib
import Architect

/-Add your code below -/

open Set
open Filter

/-- A sequence `f : ℕ → ℝ` is bounded if its range is bounded above and below. -/
@[blueprint (statement := /-- A sequence `f : ℕ → ℝ` is bounded if `BddAbove (Set.range f)` and
  `BddBelow (Set.range f)`. -/)]
def IsBoundedSequence (f : ℕ → ℝ) : Prop :=
  BddAbove (Set.range f) ∧ BddBelow (Set.range f)

/-- A nondecreasing (`Monotone`) sequence of real numbers converges to a finite limit iff it is
  bounded. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ`, if `Monotone f`, then
    `(∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f`. -/)
  (proof := /-- The forward direction: if `Monotone f` and `Tendsto f atTop (𝓝 r)` then
    `IsBoundedSequence f`. The range is bounded above by `r` using `Monotone.ge_of_tendsto`, which
    gives `f n ≤ r` for all `n`. It is bounded below by `f 0` using monotonicity.

    The backward direction: if `Monotone f` and `IsBoundedSequence f`, then `BddAbove (Set.range f)`.
    The theorem `Real.tendsto_of_bddAbove_monotone` then provides an `r` such that
    `Tendsto f atTop (𝓝 r)`. -/)]
lemma monotone_tendsto_iff_bounded {f : ℕ → ℝ} (hf : Monotone f) :
    (∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f := by
  sorry_using [Real.tendsto_of_bddAbove_monotone, Monotone.ge_of_tendsto, IsBoundedSequence]

/-- A nonincreasing (`Antitone`) sequence of real numbers converges to a finite limit iff it is
  bounded. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ`, if `Antitone f`, then
    `(∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f`. -/)
  (proof := /-- The forward direction: if `Antitone f` and `Tendsto f atTop (𝓝 r)` then
    `IsBoundedSequence f`. The range is bounded below by `r` using `Antitone.le_of_tendsto`, which
    gives `r ≤ f n` for all `n`. It is bounded above by `f 0` using antitonicity.

    The backward direction: if `Antitone f` and `IsBoundedSequence f`, then `BddBelow (Set.range f)`.
    The theorem `Real.tendsto_of_bddBelow_antitone` then provides an `r` such that
    `Tendsto f atTop (𝓝 r)`. -/)]
lemma antitone_tendsto_iff_bounded {f : ℕ → ℝ} (hf : Antitone f) :
    (∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f := by
  sorry_using [Real.tendsto_of_bddBelow_antitone, Antitone.le_of_tendsto, IsBoundedSequence]

/-- **Monotone Convergence Theorem for real sequences.** Let `f : ℕ → ℝ` be a monotone sequence
  (i.e. either nondecreasing or nonincreasing). Then the following are equivalent:
  * `f` converges to a finite limit in ℝ;
  * `f` is bounded (i.e., its range is bounded above and below). -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ` that is either `Monotone` or `Antitone`,
    `(∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f`. -/)
  (proof := /-- By case analysis on `hf`:
    * If `hf` is `Or.inl hmono` (i.e., `Monotone f`), apply `monotone_tendsto_iff_bounded`.
    * If `hf` is `Or.inr hanti` (i.e., `Antitone f`), apply `antitone_tendsto_iff_bounded`. -/)]
theorem monotone_convergence_theorem {f : ℕ → ℝ} (hf : Monotone f ∨ Antitone f) :
    (∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f := by
  sorry_using [monotone_tendsto_iff_bounded, antitone_tendsto_iff_bounded]
