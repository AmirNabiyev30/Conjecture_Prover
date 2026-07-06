/-
  Monotone Convergence Theorem for real sequences.

  Let f : ℕ → ℝ be a monotone sequence (i.e., either nondecreasing or nonincreasing).
  Then the following are equivalent:
    (1) f converges to a finite limit in ℝ.
    (2) f is bounded (its range is bounded above and below).
-/

import Mathlib
import Architect

open Set
open Filter

/-- A sequence `f : ℕ → ℝ` is bounded if its range is bounded above and below. -/
@[blueprint (statement := /-- A sequence `f : ℕ → ℝ` is bounded if `BddAbove (Set.range f) ∧
  BddBelow (Set.range f)`. -/)]
def IsBoundedSequence (f : ℕ → ℝ) : Prop :=
  BddAbove (Set.range f) ∧ BddBelow (Set.range f)

/-- If a monotone nondecreasing sequence `f` converges to a limit `r`, then `r` bounds `f` from
  above. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ` and `r : ℝ`, if `Monotone f` and
    `Tendsto f atTop (nhds r)`, then `∀ n, f n ≤ r`. -/)
  (proof := /-- Apply `Monotone.ge_of_tendsto hf ha` to get `f n ≤ r` for each `n`. -/)]
lemma monotone_tendsto_ge {f : ℕ → ℝ} {r : ℝ} (hf : Monotone f) (ha : Tendsto f atTop (nhds r)) (n : ℕ) :
    f n ≤ r :=
  hf.ge_of_tendsto ha n

/-- If a monotone nonincreasing sequence `f` converges to a limit `r`, then `r` bounds `f` from
  below. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ` and `r : ℝ`, if `Antitone f` and
    `Tendsto f atTop (nhds r)`, then `∀ n, r ≤ f n`. -/)
  (proof := /-- Apply `Antitone.le_of_tendsto hf ha` to get `r ≤ f n` for each `n`. -/)]
lemma antitone_tendsto_le {f : ℕ → ℝ} {r : ℝ} (hf : Antitone f) (ha : Tendsto f atTop (nhds r)) (n : ℕ) :
    r ≤ f n :=
  hf.le_of_tendsto ha n

/-- A monotone nondecreasing sequence that converges is bounded. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ`, if `Monotone f` and `∃ r, Tendsto f atTop (nhds r)`, then
    `IsBoundedSequence f`. -/)
  (proof := /-- Suppose `hf : Monotone f` and `ha : ∃ r, Tendsto f atTop (nhds r)`.
    Let `⟨r, hr⟩ := ha`. Then `f n ≤ r` for all `n` by `monotone_tendsto_ge hf hr`, so
    `r` is an upper bound, giving `BddAbove (Set.range f)`.
    Since `Monotone f`, we have `f 0 ≤ f n` for all `n`, so `f 0` is a lower bound,
    giving `BddBelow (Set.range f)`. Hence `IsBoundedSequence f`. -/)]
lemma monotone_convergent_is_bounded {f : ℕ → ℝ} (hf : Monotone f) (hlim : ∃ r, Tendsto f atTop (nhds r)) :
    IsBoundedSequence f := by
  sorry_using [monotone_tendsto_ge, IsBoundedSequence]

/-- A monotone nonincreasing sequence that converges is bounded. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ`, if `Antitone f` and `∃ r, Tendsto f atTop (nhds r)`, then
    `IsBoundedSequence f`. -/)
  (proof := /-- Suppose `hf : Antitone f` and `ha : ∃ r, Tendsto f atTop (nhds r)`.
    Let `⟨r, hr⟩ := ha`. Then `r ≤ f n` for all `n` by `antitone_tendsto_le hf hr`, so
    `r` is a lower bound, giving `BddBelow (Set.range f)`.
    Since `Antitone f`, we have `f n ≤ f 0` for all `n`, so `f 0` is an upper bound,
    giving `BddAbove (Set.range f)`. Hence `IsBoundedSequence f`. -/)]
lemma antitone_convergent_is_bounded {f : ℕ → ℝ} (hf : Antitone f) (hlim : ∃ r, Tendsto f atTop (nhds r)) :
    IsBoundedSequence f := by
  sorry_using [antitone_tendsto_le, IsBoundedSequence]

/-- A bounded monotone nondecreasing sequence converges to a finite limit. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ`, if `Monotone f` and `IsBoundedSequence f`, then
    `∃ r, Tendsto f atTop (nhds r)`. -/)
  (proof := /-- From `IsBoundedSequence f`, extract `hb : BddAbove (Set.range f)`.
    Then `Real.tendsto_of_bddAbove_monotone hb hf` gives the required limit. -/)]
lemma bounded_monotone_converges {f : ℕ → ℝ} (hf : Monotone f) (hb : IsBoundedSequence f) :
    ∃ r, Tendsto f atTop (nhds r) := by
  sorry_using [Real.tendsto_of_bddAbove_monotone, IsBoundedSequence]

/-- A bounded monotone nonincreasing sequence converges to a finite limit. -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ`, if `Antitone f` and `IsBoundedSequence f`, then
    `∃ r, Tendsto f atTop (nhds r)`. -/)
  (proof := /-- From `IsBoundedSequence f`, extract `hb : BddBelow (Set.range f)`.
    Then `Real.tendsto_of_bddBelow_antitone hb hf` gives the required limit. -/)]
lemma bounded_antitone_converges {f : ℕ → ℝ} (hf : Antitone f) (hb : IsBoundedSequence f) :
    ∃ r, Tendsto f atTop (nhds r) := by
  sorry_using [Real.tendsto_of_bddBelow_antitone, IsBoundedSequence]

/-- **Monotone Convergence Theorem for real sequences.** Let `f : ℕ → ℝ` be monotone (i.e., either
  nondecreasing or nonincreasing). Then the following are equivalent:
  * `f` converges to a finite limit in ℝ;
  * `f` is bounded (its range is bounded above and below). -/
@[blueprint
  (statement := /-- For any `f : ℕ → ℝ` that is either `Monotone f` or `Antitone f`,
    `(∃ r, Filter.Tendsto f Filter.atTop (nhds r)) ↔ IsBoundedSequence f`. -/)
  (proof := /-- By case analysis on `hf : Monotone f ∨ Antitone f`:
    * If `hf` is `Or.inl hmono` (i.e., `Monotone f`), then the forward direction is
      `monotone_convergent_is_bounded hmono` and the backward direction is
      `bounded_monotone_converges hmono`.
    * If `hf` is `Or.inr hanti` (i.e., `Antitone f`), then the forward direction is
      `antitone_convergent_is_bounded hanti` and the backward direction is
      `bounded_antitone_converges hanti`. -/)]
theorem monotone_convergence_theorem {f : ℕ → ℝ} (hf : Monotone f ∨ Antitone f) :
    (∃ r, Tendsto f atTop (nhds r)) ↔ IsBoundedSequence f := by
  sorry_using
    [monotone_convergent_is_bounded, bounded_monotone_converges,
     antitone_convergent_is_bounded, bounded_antitone_converges]
