/-
# Putnam 1972 A6 — blueprint decomposition

**Original Lean formalization (target theorem):**

```lean
theorem putnam_1972_a6
(f : ℝ → ℝ)
(n : ℤ)
(hn : n ≥ 0)
(hfintegrable: IntegrableOn f (Icc 0 1))
(hfint : ∀ i ∈ Icc 0 (n-1), ∫ x in Icc 0 1, x^i*(f x) = 0)
(hfintlast : ∫ x in Icc 0 1, x^n*(f x) = 1)
: ∃ S, S ⊆ Icc (0 : ℝ) 1 ∧ MeasurableSet S ∧ volume S > 0 ∧ ∀ x ∈ S, |f x| ≥ 2^n * (n + 1) :=
sorry
```

**Informal statement.**  Let $f$ be an integrable function on $[0,1]$ and suppose
$\int_0^1 x^i f(x)\,dx = 0$ for all $0 \le i \le n-1$ and $\int_0^1 x^n f(x)\,dx = 1$.
Then $|f(x)| \ge 2^n (n+1)$ on a set of positive measure.

**Proof strategy.**  Let $p_k(x) = (x - 1/2)^k$ and $M_k = 2^k (k+1)$.
Since $p_k - x^k$ is a polynomial of degree $< k$, the moment hypotheses force
$\int_0^1 p_k f = 1$, hence $1 \le \int_0^1 |p_k|\,|f|$.
The $L^1$-norm of $|p_k|$ on $[0,1]$ is $\int_0^1 |x-1/2|^k dx = (1/2)^k/(k+1)$,
so $M_k \int_0^1 |p_k| = 1$.  If $|f| < M_k$ almost everywhere, then
$\int_0^1 |p_k|\,|f| < M_k \int_0^1 |p_k| = 1$, contradicting the lower bound.
Hence $\{x \in [0,1] \mid |f(x)| \ge M_k\}$ has positive measure, from which a
measurable subset of positive measure is extracted; the integer $n$ is reduced to
the natural $k = n.\text{toNat}$ at the end.
-/

import Mathlib
import Architect

open EuclideanGeometry Filter Topology Set MeasureTheory

noncomputable section

/--
The shifted monic polynomial $p_k(x) = (x - 1/2)^k$ of degree $k$, centered at $1/2$.
-/
@[blueprint (statement := /-- The shifted monic polynomial $p_k(x) = (x - 1/2)^k$ of degree $k$. -/)]
def putnam1972a6_poly (k : ℕ) : ℝ → ℝ := fun x => (x - (1 / 2 : ℝ)) ^ k

/--
The claimed lower bound $M_k = 2^k (k+1)$ for the natural exponent $k$.
-/
@[blueprint (statement := /-- The claimed lower bound $M_k = 2^k(k+1)$. -/)]
def putnam1972a6_bound (k : ℕ) : ℝ := (2 : ℝ) ^ k * ((k : ℝ) + 1)

/--
If all moments $\int_0^1 x^i f = 0$ for $i < k$ and the $k$-th moment is
$\int_0^1 x^k f = 1$, then the moment of the centered polynomial is
$\int_0^1 (x - 1/2)^k f(x)\,dx = 1$.
-/
@[blueprint
  (statement := /-- If $\int_0^1 x^i f = 0$ for all $i < k$ and $\int_0^1 x^k f = 1$, then $\int_0^1 (x - 1/2)^k f = 1$. -/)
  (proof := /-- Expand $p_k(x) = (x - 1/2)^k = x^k + \sum_{i<k} c_i x^i$ by the binomial theorem (`add_pow`). All products with $f$ are integrable since $p_k$ is bounded on $[0,1]$ and $f$ is integrable, so integrate termwise by linearity: the terms $i < k$ vanish by `hmoments` and the leading term equals $1$ by `hlast`. -/)
  (title := /-- Shifted moment identity -/)
  (proofUses := [])]
lemma putnam1972a6_integral_shifted
    (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hmoments : ∀ i < k, ∫ x in Icc 0 1, x^i * f x = 0)
    (hlast : ∫ x in Icc 0 1, x^k * f x = 1) :
    ∫ x in Icc 0 1, putnam1972a6_poly k x * f x = 1 := by
  have hxpow_mul_f : ∀ i : ℕ, IntegrableOn (fun x : ℝ => x ^ i * f x) (Icc 0 1) := by
    intro i
    exact MeasureTheory.IntegrableOn.continuousOn_mul (by fun_prop) hfintegrable isCompact_Icc
  have hmain : ∀ x : ℝ,
      putnam1972a6_poly k x * f x =
        ∑ i ∈ Finset.range (k + 1), (k.choose i * (-1/2) ^ (k - i)) * (x ^ i * f x) := by
    intro x
    unfold putnam1972a6_poly
    rw [sub_eq_add_neg, add_pow]
    rw [Finset.sum_mul]
    apply Finset.sum_congr rfl
    intro i hi
    ring
  calc
    ∫ x in Icc 0 1, putnam1972a6_poly k x * f x
        = ∫ x in Icc 0 1,
            (∑ i ∈ Finset.range (k + 1), (k.choose i * (-1/2) ^ (k - i)) * (x ^ i * f x)) := by
            simp_rw [hmain]
    _ = ∑ i ∈ Finset.range (k + 1),
            ∫ x in Icc 0 1, (k.choose i * (-1/2) ^ (k - i)) * (x ^ i * f x) := by
            rw [MeasureTheory.integral_finsetSum]
            intro i hi
            exact (hxpow_mul_f i).const_mul (k.choose i * (-1/2) ^ (k - i))
    _ = 1 := by
            rw [Finset.sum_eq_single k]
            · rw [MeasureTheory.integral_const_mul]
              rw [hlast]
              simp [Nat.choose_self, pow_zero]
            · intro b hb hbk
              have hblt : b < k := by
                exact lt_of_le_of_ne (Nat.le_of_lt_succ (Finset.mem_range.mp hb)) hbk
              rw [MeasureTheory.integral_const_mul]
              rw [hmoments b hblt]
              ring
            · intro hknot
              exfalso
              exact hknot (Finset.mem_range.mpr (Nat.lt_succ_self k))

/--
From $\int_0^1 p_k f = 1$ and the triangle inequality for Bochner integrals
(`abs_integral_le_integral_abs`), we get the lower bound
$1 \le \int_0^1 |p_k(x)|\,|f(x)|\,dx$.
-/
@[blueprint
  (statement := /-- $1 \le \int_0^1 |x-1/2|^k |f(x)|\,dx$. -/)
  (proof := /-- By `putnam1972a6_integral_shifted` the integral $\int p_k f$ equals $1$, so $1 = |\int p_k f| \le \int |p_k|\,|f|$ via `MeasureTheory.abs_integral_le_integral_abs` and `abs_of_pos` on the left-hand side. -/)
  (title := /-- Lower bound on the weighted $L^1$ norm -/)
  (proofUses := [putnam1972a6_integral_shifted])]
lemma putnam1972a6_one_le_abs
    (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hmoments : ∀ i < k, ∫ x in Icc 0 1, x^i * f x = 0)
    (hlast : ∫ x in Icc 0 1, x^k * f x = 1) :
    1 ≤ ∫ x in Icc 0 1, |putnam1972a6_poly k x| * |f x| := by
  have hint : ∫ x in Icc 0 1, putnam1972a6_poly k x * f x = 1 :=
    putnam1972a6_integral_shifted f k hfintegrable hmoments hlast
  calc
    1 = |∫ x in Icc 0 1, putnam1972a6_poly k x * f x| := by
      simp [hint]
    _ ≤ ∫ x in Icc 0 1, |putnam1972a6_poly k x * f x| := by
      exact MeasureTheory.abs_integral_le_integral_abs (μ := volume.restrict (Icc 0 1))
        (f := fun x => putnam1972a6_poly k x * f x)
    _ = ∫ x in Icc 0 1, |putnam1972a6_poly k x| * |f x| := by
      congr 1
      funext x
      rw [abs_mul]

/--
The $L^1$-norm of the shifted power on $[0,1]$:
$\int_0^1 |x - 1/2|^k\,dx = (1/2)^k/(k+1)$.
-/
@[blueprint
  (statement := /-- $\int_0^1 |x - 1/2|^k\,dx = (1/2)^k/(k+1)$. -/)
  (proof := /-- Split the interval at $1/2$ and use the antiderivative $t^{k+1}/(k+1)$ of $t^k$ via `intervalIntegral.integral_comp_mul_deriv` / `integral_pow`; the two halves each contribute $(1/2)^{k+1}/(k+1)$, summing to $(1/2)^k/(k+1)$. -/)
  (title := /-- $L^1$ norm of the shifted power -/)
  (proofUses := [])]
lemma putnam1972a6_l1_shifted_power (k : ℕ) :
    ∫ x in Icc 0 1, |putnam1972a6_poly k x| = (1 / 2 : ℝ)^k / ((k : ℝ) + 1) := by
  change ∫ x in Set.Icc 0 1, |(x - (1 / 2 : ℝ)) ^ k| = (1 / 2 : ℝ) ^ k / ((k : ℝ) + 1)
  have hIcc : (∫ x in Set.Icc 0 1, |(x - (1 / 2 : ℝ)) ^ k|) =
      ∫ x in (0 : ℝ)..1, |(x - (1 / 2 : ℝ)) ^ k| := by
    rw [MeasureTheory.integral_Icc_eq_integral_Ioc]
    exact (intervalIntegral.integral_of_le (by norm_num : (0 : ℝ) ≤ 1)).symm
  rw [hIcc]
  let f : ℝ → ℝ := fun x => |(x - (1 / 2 : ℝ)) ^ k|
  have hcont : Continuous f := by
    dsimp [f]
    fun_prop
  have hsplit := intervalIntegral.integral_add_adjacent_intervals (μ := MeasureTheory.volume) (f := f)
    (a := (0 : ℝ)) (b := (1 / 2 : ℝ)) (c := 1)
    (hcont.intervalIntegrable 0 (1/2)) (hcont.intervalIntegrable (1/2) 1)
  change ∫ x in (0 : ℝ)..1, f x = (1 / 2 : ℝ) ^ k / ((k : ℝ) + 1)
  rw [← hsplit]
  have hleft : ∫ x in (0 : ℝ)..(1 / 2), f x = ∫ x in (0 : ℝ)..(1 / 2), ((1 / 2 : ℝ) - x) ^ k := by
    refine intervalIntegral.integral_congr ?_
    intro x hx
    rw [Set.uIcc_of_le (by norm_num : (0 : ℝ) ≤ 1 / 2)] at hx
    rcases hx with ⟨h0, h12⟩
    dsimp [f]
    rw [abs_pow, abs_of_nonpos (by nlinarith), neg_sub]
  have hleft_val : ∫ x in (0 : ℝ)..(1 / 2), ((1 / 2 : ℝ) - x) ^ k = (1 / 2 : ℝ) ^ (k + 1) / ((k : ℝ) + 1) := by
    rw [intervalIntegral.integral_comp_sub_left (fun t : ℝ => t ^ k) (1 / 2 : ℝ)]
    rw [integral_pow]
    norm_num
  have hright : ∫ x in (1 / 2 : ℝ)..1, f x = ∫ x in (1 / 2 : ℝ)..1, (x - (1 / 2 : ℝ)) ^ k := by
    refine intervalIntegral.integral_congr ?_
    intro x hx
    rw [Set.uIcc_of_le (by norm_num : (1 / 2 : ℝ) ≤ 1)] at hx
    rcases hx with ⟨h12, h1⟩
    dsimp [f]
    rw [abs_pow, abs_of_nonneg (by nlinarith)]
  have hright_val : ∫ x in (1 / 2 : ℝ)..1, (x - (1 / 2 : ℝ)) ^ k = (1 / 2 : ℝ) ^ (k + 1) / ((k : ℝ) + 1) := by
    rw [intervalIntegral.integral_comp_sub_right (fun t : ℝ => t ^ k) (1 / 2 : ℝ)]
    rw [integral_pow]
    norm_num
  rw [hleft, hleft_val, hright, hright_val]
  ring_nf

lemma putnam1972a6_ae_lt_mul (f : ℝ → ℝ) (k : ℕ)
    (hae : ∀ᵐ x ∂volume, x ∈ Icc 0 1 → |f x| < putnam1972a6_bound k) :
    ∀ᵐ x ∂(volume.restrict (Ioc (0 : ℝ) 1)),
      |putnam1972a6_poly k x| * |f x| < putnam1972a6_bound k * |putnam1972a6_poly k x| := by
  rw [ae_restrict_iff' measurableSet_Ioc]
  have hne : ∀ᵐ x ∂volume, x ≠ (1 / 2 : ℝ) := by
    rw [ae_iff]
    simp
  filter_upwards [hae, hne] with x hxIcc hxne
  intro hxIoc
  have hxIcc' : x ∈ Icc (0 : ℝ) 1 := Ioc_subset_Icc_self hxIoc
  have hlt : |f x| < putnam1972a6_bound k := hxIcc hxIcc'
  have hpow_ne : (x - (1 / 2 : ℝ)) ^ k ≠ 0 := pow_ne_zero k (sub_ne_zero.mpr hxne)
  have hppos : 0 < |putnam1972a6_poly k x| := by
    simpa [putnam1972a6_poly] using (abs_pos.mpr hpow_ne)
  have h := mul_lt_mul_of_pos_left hlt hppos
  simpa [mul_comm, mul_left_comm, mul_assoc] using h

lemma putnam1972a6_measure_lt_ne_zero (f : ℝ → ℝ) (k : ℕ)
    (hae : ∀ᵐ x ∂volume, x ∈ Icc 0 1 → |f x| < putnam1972a6_bound k) :
    (volume.restrict (Ioc (0 : ℝ) 1)) {x |
      |putnam1972a6_poly k x| * |f x| < putnam1972a6_bound k * |putnam1972a6_poly k x|} ≠ 0 := by
  let μ : Measure ℝ := volume.restrict (Ioc (0 : ℝ) 1)
  let S : Set ℝ := {x | |putnam1972a6_poly k x| * |f x| < putnam1972a6_bound k * |putnam1972a6_poly k x|}
  have haeS : ∀ᵐ x ∂μ, x ∈ S := by
    simpa [μ, S] using putnam1972a6_ae_lt_mul f k hae
  have hnull : μ Sᶜ = 0 := by
    exact ae_iff.mp haeS
  by_contra hne0
  have hS0 : μ S = 0 := by simpa [μ, S] using hne0
  have hle : μ Set.univ ≤ 0 := by
    calc
      μ Set.univ ≤ μ (S ∪ Sᶜ) := measure_mono (by intro x hx; by_cases hxS : x ∈ S <;> simp)
      _ ≤ μ S + μ Sᶜ := measure_union_le S Sᶜ
      _ = 0 := by simp [hS0, hnull]
  have huniv : μ Set.univ = (1 : ENNReal) := by
    simp [μ, Real.volume_Ioc]
  have h01 : (1 : ENNReal) = 0 := by
    apply le_antisymm
    · simp [huniv] at hle
    · exact zero_le
  exact one_ne_zero h01

lemma putnam1972a6_integral_abs_lt_interval (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hae : ∀ᵐ x ∂volume, x ∈ Icc 0 1 → |f x| < putnam1972a6_bound k) :
    (∫ x in (0 : ℝ)..1, |putnam1972a6_poly k x| * |f x|) <
      ∫ x in (0 : ℝ)..1, putnam1972a6_bound k * |putnam1972a6_poly k x| := by
  have hf_abs : IntegrableOn (fun x : ℝ => |f x|) (Icc 0 1) := by
    simpa [IntegrableOn, Real.norm_eq_abs] using (MeasureTheory.Integrable.norm hfintegrable)
  have hcont_poly : ContinuousOn (fun x : ℝ => |putnam1972a6_poly k x|) (Icc 0 1) := by
    unfold putnam1972a6_poly
    fun_prop
  have hf_int : IntervalIntegrable (fun x : ℝ => |putnam1972a6_poly k x| * |f x|) volume (0 : ℝ) 1 := by
    rw [intervalIntegrable_iff, Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1)]
    refine MeasureTheory.IntegrableOn.mono_set ?_ Set.Ioc_subset_Icc_self
    simpa [mul_comm] using
      (MeasureTheory.IntegrableOn.mul_continuousOn (g := fun x : ℝ => |f x|)
        (g' := fun x : ℝ => |putnam1972a6_poly k x|) hf_abs hcont_poly (isCompact_Icc))
  have hg_int : IntervalIntegrable (fun x : ℝ => putnam1972a6_bound k * |putnam1972a6_poly k x|) volume (0 : ℝ) 1 := by
    rw [intervalIntegrable_iff, Set.uIoc_of_le (by norm_num : (0 : ℝ) ≤ 1)]
    refine MeasureTheory.IntegrableOn.mono_set ?_ Set.Ioc_subset_Icc_self
    exact ContinuousOn.integrableOn_compact (isCompact_Icc) (by
      unfold putnam1972a6_poly putnam1972a6_bound
      fun_prop)
  exact intervalIntegral.integral_lt_integral_of_ae_le_of_measure_setOfPred_lt_ne_zero
    (by norm_num : (0 : ℝ) ≤ 1) hf_int hg_int
    ((putnam1972a6_ae_lt_mul f k hae).mono (fun x hx => le_of_lt hx))
    (putnam1972a6_measure_lt_ne_zero f k hae)

lemma putnam1972a6_integral_abs_lt (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hae : ∀ᵐ x ∂volume, x ∈ Icc 0 1 → |f x| < putnam1972a6_bound k) :
    ∫ x in Icc 0 1, |putnam1972a6_poly k x| * |f x| <
      putnam1972a6_bound k * ∫ x in Icc 0 1, |putnam1972a6_poly k x| := by
  have h := putnam1972a6_integral_abs_lt_interval f k hfintegrable hae
  simp only [intervalIntegral.integral_of_le (by norm_num : (0 : ℝ) ≤ 1),
    ← MeasureTheory.integral_Icc_eq_integral_Ioc] at h
  simpa [MeasureTheory.integral_const_mul] using h

/--
Normalization: $M_k \int_0^1 |p_k| = 2^k(k+1)\cdot (1/2)^k/(k+1) = 1$.
-/
@[blueprint
  (statement := /-- $M_k \int_0^1 |p_k(x)|\,dx = 1$. -/)
  (proof := /-- Substitute the explicit $L^1$ norm from `putnam1972a6_l1_shifted_power` and cancel: $2^k (k+1) \cdot (1/2)^k / (k+1) = (2 \cdot 1/2)^k \cdot (k+1)/(k+1) = 1$, using `mul_pow`, `div_mul_cancel`, and $k+1 \ne 0$. -/)
  (title := /-- Normalization -/)
  (proofUses := [putnam1972a6_l1_shifted_power])]
lemma putnam1972a6_bound_mul_l1 (k : ℕ) :
    putnam1972a6_bound k * ∫ x in Icc 0 1, |putnam1972a6_poly k x| = 1 := by
  rw [putnam1972a6_bound, putnam1972a6_l1_shifted_power]
  field_simp
  rw [← mul_pow]
  norm_num

/--
Under the moment hypotheses it is impossible that $|f(x)| < M_k$ almost
everywhere on $[0,1]$.
-/
@[blueprint
  (statement := /-- Under the moment hypotheses, $\neg \forall^{\mathrm{a.e.}} x \in [0,1],\ |f(x)| < M_k$. -/)
  (proof := /-- Assume `hae : ∀ᵐ x, x ∈ Icc 0 1 → |f x| < M_k`. Then `putnam1972a6_one_le_abs` gives $1 \le \int |p_k|\,|f|$, while `putnam1972a6_integral_abs_lt` and `putnam1972a6_bound_mul_l1` give $\int |p_k|\,|f| < M_k \int |p_k| = 1$; together $1 \le \int |p_k|\,|f| < 1$, contradiction. -/)
  (title := /-- Contradiction: $|f| < M_k$ cannot hold a.e. -/)
  (proofUses := [putnam1972a6_one_le_abs, putnam1972a6_integral_abs_lt, putnam1972a6_bound_mul_l1])]
lemma putnam1972a6_not_ae_small
    (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hmoments : ∀ i < k, ∫ x in Icc 0 1, x^i * f x = 0)
    (hlast : ∫ x in Icc 0 1, x^k * f x = 1) :
    ¬ ∀ᵐ x ∂volume, x ∈ Icc 0 1 → |f x| < putnam1972a6_bound k := by
  intro hae
  have h1 : 1 ≤ ∫ x in Icc 0 1, |putnam1972a6_poly k x| * |f x| :=
    putnam1972a6_one_le_abs f k hfintegrable hmoments hlast
  have hlt : ∫ x in Icc 0 1, |putnam1972a6_poly k x| * |f x| <
      putnam1972a6_bound k * ∫ x in Icc 0 1, |putnam1972a6_poly k x| :=
    putnam1972a6_integral_abs_lt f k hfintegrable hae
  have hlt1 : ∫ x in Icc 0 1, |putnam1972a6_poly k x| * |f x| < 1 := by
    simpa [putnam1972a6_bound_mul_l1] using hlt
  linarith

lemma putnam1972a6_measure_level_set_pos
    (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hmoments : ∀ i < k, ∫ x in Icc 0 1, x^i * f x = 0)
    (hlast : ∫ x in Icc 0 1, x^k * f x = 1) :
    volume {x | x ∈ Icc (0 : ℝ) 1 ∧ putnam1972a6_bound k ≤ |f x|} > 0 := by
  have hne : volume {x | x ∈ Icc (0 : ℝ) 1 ∧ putnam1972a6_bound k ≤ |f x|} ≠ 0 := by
    intro h
    apply putnam1972a6_not_ae_small f k hfintegrable hmoments hlast
    rw [MeasureTheory.ae_iff]
    have hset : {x | ¬ (x ∈ Icc (0 : ℝ) 1 → |f x| < putnam1972a6_bound k)} =
        {x | x ∈ Icc (0 : ℝ) 1 ∧ putnam1972a6_bound k ≤ |f x|} := by
      ext x
      simp [not_lt, and_assoc]
    rw [hset]
    exact h
  exact lt_of_le_of_ne zero_le hne.symm

lemma putnam1972a6_measurable_subset_pos
    (f : ℝ → ℝ) (s : Set ℝ) (M : ℝ)
    (hsm : MeasurableSet s)
    (hmeas : AEStronglyMeasurable f (volume.restrict s))
    (hpos : volume {x | x ∈ s ∧ M ≤ |f x|} > 0) :
    ∃ S : Set ℝ, S ⊆ s ∧ MeasurableSet S ∧ volume S > 0 ∧ ∀ x ∈ S, M ≤ |f x| := by
  let g : ℝ → ℝ := AEStronglyMeasurable.mk f hmeas
  let T : Set ℝ := {x | x ∈ s ∧ M ≤ |f x|}
  let T' : Set ℝ := {x | x ∈ s ∧ M ≤ |g x|}
  let E : Set ℝ := {x | x ∈ s ∧ f x ≠ g x}
  let N : Set ℝ := toMeasurable volume (T' \ T)
  let S : Set ℝ := T' \ N
  have hgmeas : Measurable g := hmeas.measurable_mk
  have hae : f =ᵐ[volume.restrict s] g := hmeas.ae_eq_mk
  have hae_vol : ∀ᵐ x ∂volume, x ∈ s → f x = g x := (ae_restrict_iff' hsm).mp hae
  have hE0 : volume E = 0 := by
    have h : ∀ᵐ x ∂volume, x ∉ E := by
      filter_upwards [hae_vol] with x hx
      intro hxE
      rcases hxE with ⟨hxs, hfg⟩
      exact hfg (hx hxs)
    simpa [E] using (ae_iff.mp h)
  have hTT' : T \ T' ⊆ E := by
    intro x hx
    rcases hx with ⟨hxT, hxT'⟩
    have hxs : x ∈ s := hxT.1
    have hMf : M ≤ |f x| := hxT.2
    have hnotg : ¬ M ≤ |g x| := by
      intro h
      exact hxT' ⟨hxs, h⟩
    have hlt : |g x| < M := lt_of_not_ge hnotg
    have hlt2 : |g x| < |f x| := lt_of_lt_of_le hlt hMf
    have hne : f x ≠ g x := by
      intro hfg
      rw [hfg] at hlt2
      exact (lt_irrefl (|g x|)) hlt2
    exact ⟨hxs, hne⟩
  have hT'T : T' \ T ⊆ E := by
    intro x hx
    rcases hx with ⟨hxT', hxT⟩
    have hxs : x ∈ s := hxT'.1
    have hMg : M ≤ |g x| := hxT'.2
    have hnotf : ¬ M ≤ |f x| := by
      intro h
      exact hxT ⟨hxs, h⟩
    have hlt : |f x| < M := lt_of_not_ge hnotf
    have hlt2 : |f x| < |g x| := lt_of_lt_of_le hlt hMg
    have hne : f x ≠ g x := by
      intro hfg
      rw [hfg] at hlt2
      exact (lt_irrefl (|g x|)) hlt2
    exact ⟨hxs, hne⟩
  have hT_sub : T ⊆ T' ∪ E := by
    intro x hx
    by_cases h : x ∈ T'
    · exact Or.inl h
    · exact Or.inr (hTT' ⟨hx, h⟩)
  have hvol_le : volume T ≤ volume T' := by
    calc
      volume T ≤ volume (T' ∪ E) := measure_mono hT_sub
      _ ≤ volume T' + volume E := measure_union_le T' E
      _ = volume T' := by simp [hE0]
  have hT'meas : MeasurableSet T' := by
    exact MeasurableSet.congr
      (hsm.inter (measurableSet_le (measurable_const : Measurable (fun _ : ℝ => M)) hgmeas.abs))
      (by ext x; simp [T'])
  have hNmeas : MeasurableSet N := measurableSet_toMeasurable volume (T' \ T)
  have hSmeas : MeasurableSet S := hT'meas.diff hNmeas
  have hN0 : volume N = 0 := by
    have hvolTT' : volume (T' \ T) = 0 := by
      have hle : volume (T' \ T) ≤ 0 := by
        calc
          volume (T' \ T) ≤ volume E := measure_mono hT'T
          _ = 0 := hE0
      exact le_antisymm hle (by simp)
    rw [measure_toMeasurable, hvolTT']
  have hS_sub_T : S ⊆ T := by
    intro x hx
    rcases hx with ⟨hxT', hxN⟩
    by_contra hxT
    have hx : x ∈ T' \ T := ⟨hxT', hxT⟩
    have hxN' : x ∈ N := subset_toMeasurable volume (T' \ T) hx
    exact hxN hxN'
  have hS_sub_s : S ⊆ s := by
    intro x hx
    exact (hS_sub_T hx).1
  have hS_sub_T' : S ⊆ T' := by
    intro x hx
    exact hx.1
  have hTSN : T' \ S ⊆ N := by
    intro x hx
    rcases hx with ⟨hxT', hxS⟩
    by_contra hxN
    exact hxS ⟨hxT', hxN⟩
  have hvolT' : volume T' ≤ volume S := by
    calc
      volume T' = volume (S ∪ (T' \ S)) := by
        exact congrArg volume (Set.union_sdiff_cancel hS_sub_T').symm
      _ ≤ volume S + volume (T' \ S) := measure_union_le S (T' \ S)
      _ ≤ volume S + volume N := by
        exact add_le_add le_rfl (measure_mono hTSN)
      _ = volume S := by simp [hN0]
  have hSpos : volume S > 0 := by
    exact lt_of_lt_of_le (lt_of_lt_of_le hpos hvol_le) hvolT'
  have hSprop : ∀ x ∈ S, M ≤ |f x| := by
    intro x hx
    exact (hS_sub_T hx).2
  exact ⟨S, hS_sub_s, hSmeas, hSpos, hSprop⟩

lemma putnam1972a6_pos_measure_set
    (f : ℝ → ℝ) (k : ℕ)
    (hfintegrable : IntegrableOn f (Icc 0 1))
    (hmoments : ∀ i < k, ∫ x in Icc 0 1, x^i * f x = 0)
    (hlast : ∫ x in Icc 0 1, x^k * f x = 1) :
    ∃ S : Set ℝ, S ⊆ Icc 0 1 ∧ MeasurableSet S ∧ volume S > 0 ∧
      ∀ x ∈ S, |f x| ≥ putnam1972a6_bound k := by
  exact putnam1972a6_measurable_subset_pos f (Icc 0 1) (putnam1972a6_bound k)
    measurableSet_Icc hfintegrable.aestronglyMeasurable
    (putnam1972a6_measure_level_set_pos f k hfintegrable hmoments hlast)

/--
The integer moment hypotheses (with $n \ge 0$) yield the natural moment
hypotheses for $k = n.\text{toNat}$.
-/
@[blueprint
  (statement := /-- If $\int_0^1 x^i f = 0$ for all integers $i \in [0, n-1]$ and $\int_0^1 x^n f = 1$, then $\int_0^1 x^i f = 0$ for all naturals $i < n.\mathrm{toNat}$ and $\int_0^1 x^{n.\mathrm{toNat}} f = 1$. -/)
  (proof := /-- For $i : \mathbb{N}$ with $i < n.\mathrm{toNat}$, use `Int.toNat_of_nonneg` to get $(i:\mathbb{Z}) \le n-1$ (as $i+1 \le n$ for integers) and $0 \le i$, so `hfint` applies; rewrite $x^{(i:\mathbb{Z})} = x^i$ by `zpow_natCast`. For the last moment rewrite $x^n = x^{n.\mathrm{toNat}}$ using $(n.\mathrm{toNat}:\mathbb{Z}) = n$ and `zpow_natCast`. -/)
  (title := /-- Integer to natural moments -/)
  (proofUses := [])]
lemma putnam1972a6_to_nat (f : ℝ → ℝ) (n : ℤ) (hn : 0 ≤ n)
    (hfint : ∀ i ∈ Icc 0 (n - 1), ∫ x in Icc 0 1, x^i * f x = 0)
    (hfintlast : ∫ x in Icc 0 1, x^n * f x = 1) :
    (∀ i < n.toNat, ∫ x in Icc 0 1, x^i * f x = 0) ∧
      ∫ x in Icc 0 1, x^(n.toNat) * f x = 1 := by
  have hnz : (n.toNat : ℤ) = n := Int.toNat_of_nonneg hn
  constructor
  · intro i hi
    have hz : (i : ℤ) ∈ Icc 0 (n - 1) := by
      constructor
      · exact_mod_cast (Nat.zero_le i)
      · have hi' : (i : ℤ) < n := by
          have hi'' : (i : ℤ) < (n.toNat : ℤ) := by exact_mod_cast hi
          simpa [hnz] using hi''
        omega
    have h := hfint (i : ℤ) hz
    have hfun : (fun x : ℝ => x ^ i * f x) = (fun x : ℝ => x ^ (i : ℤ) * f x) := by
      funext x
      exact congrArg (fun t : ℝ => t * f x) (zpow_natCast x (i : ℕ)).symm
    rw [hfun]
    exact h
  · have hfun2 : (fun x : ℝ => x ^ n.toNat * f x) = (fun x : ℝ => x ^ n * f x) := by
      funext x
      apply congrArg (fun t : ℝ => t * f x)
      rw [← zpow_natCast x n.toNat, hnz]
    rw [hfun2]
    exact hfintlast

/--
The integer-valued bound $2^n (n+1)$ (with $n : \mathbb{Z}$, $n \ge 0$) coincides
with the natural bound $M_{n.\text{toNat}}$.
-/
@[blueprint
  (statement := /-- For $n \ge 0$, $2^n (n+1) = M_{n.\mathrm{toNat}}$ as real numbers. -/)
  (proof := /-- $(n.\mathrm{toNat}:\mathbb{Z}) = n$ by `Int.toNat_of_nonneg`, so `zpow_natCast` gives $(2:\mathbb{R})^n = (2:\mathbb{R})^{n.\mathrm{toNat}}$; also $\uparrow(n+1) = \uparrow n + 1 = \uparrow n.\mathrm{toNat} + 1$ by `Int.cast_add`. -/)
  (title := /-- Bound conversion -/)
  (proofUses := [])]
lemma putnam1972a6_bound_of_int (n : ℤ) (hn : 0 ≤ n) :
    (2 : ℝ)^n * (n + 1) = putnam1972a6_bound n.toNat := by
  have h1 : (n.toNat : ℤ) = n := Int.toNat_of_nonneg hn
  conv_lhs =>
    rw [← h1]
    rw [zpow_natCast]
  rw [show ((↑(↑n.toNat : ℤ) : ℝ) = (↑n.toNat : ℝ)) by exact_mod_cast rfl]
  rfl

/--
**Putnam 1972 A6.**  Let $f$ be integrable on $[0,1]$ with
$\int_0^1 x^i f(x)\,dx = 0$ for $0 \le i \le n-1$ and $\int_0^1 x^n f(x)\,dx = 1$.
Then $|f(x)| \ge 2^n (n+1)$ on a set of positive measure.
-/
@[blueprint
  (statement := /-- Putnam 1972 A6: if all moments below $n$ vanish and the $n$-th moment equals $1$, then $|f(x)| \ge 2^n(n+1)$ on a set of positive measure. -/)
  (proof := /-- Apply `putnam1972a6_to_nat` to obtain the natural moment hypotheses for $k = n.\mathrm{toNat}$, apply `putnam1972a6_pos_measure_set` to obtain the measurable positive-measure set $S$ with $|f(x)| \ge M_{n.\mathrm{toNat}}$ on $S$, and rewrite the bound using `putnam1972a6_bound_of_int`. -/)
  (title := /-- Putnam 1972 A6 -/)
  (proofUses := [putnam1972a6_to_nat, putnam1972a6_pos_measure_set, putnam1972a6_bound_of_int])]
theorem putnam_1972_a6
(f : ℝ → ℝ)
(n : ℤ)
(hn : n ≥ 0)
(hfintegrable: IntegrableOn f (Icc 0 1))
(hfint : ∀ i ∈ Icc 0 (n-1), ∫ x in Icc 0 1, x^i*(f x) = 0)
(hfintlast : ∫ x in Icc 0 1, x^n*(f x) = 1)
: ∃ S, S ⊆ Icc (0 : ℝ) 1 ∧ MeasurableSet S ∧ volume S > 0 ∧ ∀ x ∈ S, |f x| ≥ 2^n * (n + 1) := by
  rcases putnam1972a6_to_nat f n hn hfint hfintlast with ⟨hmoments, hlast⟩
  rcases putnam1972a6_pos_measure_set f n.toNat hfintegrable hmoments hlast with ⟨S, hSsub, hSmeas, hSvol, hSbound⟩
  refine ⟨S, hSsub, hSmeas, hSvol, ?_⟩
  intro x hx
  rw [putnam1972a6_bound_of_int n hn]
  exact hSbound x hx

end
