import Mathlib
import Architect

open Real Filter
open scoped Topology

/-!
# Putnam 2025 A2

**Original formalization** (target):

```lean
noncomputable abbrev putnam_2025_a2_solution : ℝ × ℝ := sorry
-- (1 / π, 4 / π ^ 2)

theorem putnam_2025_a2 (a b : ℝ) :
  ((a, b) = putnam_2025_a2_solution) ↔
  (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
   IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := sorry
```

**Informal statement.** Find the largest real number $a$ and the smallest real
number $b$ such that $a\,x(\pi-x) \le \sin x \le b\,x(\pi-x)$ for all
$x \in [0,\pi]$.  The answer is $a = 1/\pi$ and $b = 4/\pi^2$.

**Proof strategy.**  On $(0,\pi)$ divide through by the positive quantity
$x(\pi-x)$; one must find the infimum and supremum of
$f(x) = \sin x / (x(\pi-x))$ on $(0,\pi)$.  The infimum is $1/\pi$, approached
as $x \to 0^+$ (and by symmetry as $x \to \pi^-$); the supremum is $4/\pi^2$,
attained at $x = \pi/2$.  The blueprint below decomposes this into: the two
pointwise inequalities (split at the midpoint $\pi/2$, with symmetry between the
two halves), the limit at $0$ used to prove sharpness of $1/\pi$, the value at
the midpoint used to prove sharpness of $4/\pi^2$, and the
`IsGreatest`/`IsLeast` bookkeeping.
-/

-- ---------------------------------------------------------------------------
-- Definitions
-- ---------------------------------------------------------------------------

/-- The solution pair $(a,b) = (1/\pi,\ 4/\pi^2)$ of Putnam 2025 A2. -/
@[blueprint (statement := /-- The solution pair $(a,b) = (1/\pi,\ 4/\pi^2)$ of Putnam 2025 A2. -/)]
noncomputable abbrev putnam_2025_a2_solution : ℝ × ℝ := (1 / π, 4 / π ^ 2)

/-- The set of constants $a'$ admissible for the lower inequality
$a'x(\pi-x) \le \sin x$ on $[0,\pi]$. -/
@[blueprint (statement := /-- The set of constants $a'$ such that $a'\,x(\pi-x) \le \sin x$ for all $x \in [0,\pi]$. -/)]
abbrev putnam_2025_a2_A : Set ℝ := {a' | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x}

/-- The set of constants $b'$ admissible for the upper inequality
$\sin x \le b'x(\pi-x)$ on $[0,\pi]$. -/
@[blueprint (statement := /-- The set of constants $b'$ such that $\sin x \le b'\,x(\pi-x)$ for all $x \in [0,\pi]$. -/)]
abbrev putnam_2025_a2_B : Set ℝ := {b' | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)}

/-- The ratio $f(x) = \sin x / (x(\pi-x))$, the quantity whose infimum and
supremum on $(0,\pi)$ determine the optimal constants $a$ and $b$. -/
@[blueprint (statement := /-- The ratio $f(x) = \frac{\sin x}{x(\pi-x)}$ on $(0,\pi)$; division by zero is harmless in $\mathbb{R}$. -/)]
noncomputable def putnam_2025_a2_f (x : ℝ) : ℝ := sin x / (x * (π - x))

-- ---------------------------------------------------------------------------
-- Pointwise lower inequality, split at the midpoint π/2
-- ---------------------------------------------------------------------------

/-- Lower inequality on the left half $[0,\pi/2]$:
$\frac{1}{\pi}x(\pi-x) \le \sin x$. -/
@[blueprint
  (statement := /-- On $x \in [0, \pi/2]$, $\frac{1}{\pi}x(\pi-x) \le \sin x$. -/)
  (proof := /-- Standard analytic inequality.  For $0 < x$ use `Real.sin_gt_sub_cube` to get $x - x^3/6 < \sin x$ (and handle $x = 0$ separately); then $x - x^2/\pi \le x - x^3/6$ reduces to $x \le 6/\pi$, which holds on $[0,\pi/2]$ since $\pi^2 \le 12$. -/)
  (proofUses := [])]
lemma putnam_2025_a2_lower_bound_left :
    ∀ x ∈ Set.Icc 0 (π / 2), (1 / π) * x * (π - x) ≤ sin x := by
  intro x hx
  rcases hx with ⟨hx0, hx2⟩
  by_cases hx0eq : x = 0
  · subst x
    simp
  · have hxpos : 0 < x := lt_of_le_of_ne hx0 (Ne.symm hx0eq)
    have hsin : x - x ^ 3 / 6 < sin x := Real.sin_gt_sub_cube hxpos
    have hxpi : x * π ≤ 6 := by
      nlinarith [hx2, Real.pi_pos, Real.pi_lt_d2]
    have hmain : (1 / π) * x * (π - x) ≤ x - x ^ 3 / 6 := by
      field_simp [Real.pi_ne_zero]
      nlinarith [hxpi, sq_nonneg x]
    exact le_trans hmain (le_of_lt hsin)

/-- Lower inequality on the right half $[\pi/2,\pi]$, by symmetry from the
left half. -/
@[blueprint
  (statement := /-- On $x \in [\pi/2, \pi]$, $\frac{1}{\pi}x(\pi-x) \le \sin x$. -/)
  (proof := /-- Symmetry: for $x \in [\pi/2,\pi]$ put $y = \pi - x \in [0,\pi/2]$; apply `putnam_2025_a2_lower_bound_left` at $y$ and rewrite $\sin(\pi-y) = \sin y$ via `Real.sin_pi_sub` and $(\pi-y)(\pi-(\pi-y)) = y(\pi-y)$. -/)
  (proofUses := [putnam_2025_a2_lower_bound_left])]
lemma putnam_2025_a2_lower_bound_right :
    ∀ x ∈ Set.Icc (π / 2) π, (1 / π) * x * (π - x) ≤ sin x := by
  intro x hx
  let y := π - x
  have hy_mem : y ∈ Set.Icc (0 : ℝ) (π / 2) := by
    constructor
    · linarith [hx.2]
    · linarith [hx.1]
  have hleft := putnam_2025_a2_lower_bound_left y hy_mem
  have hx_eq : x = π - y := by
    dsimp [y]
    ring
  rw [hx_eq]
  rw [Real.sin_pi_sub]
  have h : (1 / π) * (π - y) * (π - (π - y)) = (1 / π) * y * (π - y) := by
    field_simp [Real.pi_ne_zero]
    ring
  rw [h]
  exact hleft

/-- The lower inequality on the whole interval $[0,\pi]$; this is exactly
membership of $a = 1/\pi$ in `putnam_2025_a2_A`. -/
@[blueprint
  (statement := /-- For all $x \in [0,\pi]$, $\frac{1}{\pi}x(\pi-x) \le \sin x$; hence $a = 1/\pi$ is admissible. -/)
  (proof := /-- Split $[0,\pi] = [0,\pi/2] \cup [\pi/2,\pi]$ via `le_total x (π/2)` and apply `putnam_2025_a2_lower_bound_left` or `putnam_2025_a2_lower_bound_right` according to the case. -/)
  (proofUses := [putnam_2025_a2_lower_bound_left, putnam_2025_a2_lower_bound_right])]
lemma putnam_2025_a2_lower_bound :
    ∀ x ∈ Set.Icc 0 π, (1 / π) * x * (π - x) ≤ sin x := by
  intro x hx
  have hx0 : 0 ≤ x := (Set.mem_Icc.mp hx).1
  have hx1 : x ≤ π := (Set.mem_Icc.mp hx).2
  rcases le_total x (π / 2) with hxle | hxge
  · exact putnam_2025_a2_lower_bound_left x ⟨hx0, hxle⟩
  · exact putnam_2025_a2_lower_bound_right x ⟨hxge, hx1⟩

-- ---------------------------------------------------------------------------
-- Pointwise upper inequality, split at the midpoint π/2
-- ---------------------------------------------------------------------------

/-- Auxiliary function $q(x) = \frac{4}{\pi^2}x(\pi-x) - \sin x$ for the
upper inequality on $[0,\pi/2]$: proving $q \ge 0$ there is exactly the
desired bound. -/
@[blueprint (statement := /-- The function $q(x) = \frac{4}{\pi^2}x(\pi-x) - \sin x$ used to prove the upper bound on $[0,\pi/2]$. -/)]
noncomputable def putnam_2025_a2_upper_q (x : ℝ) : ℝ := (4 / π ^ 2) * (x * (π - x)) - sin x

/-- First derivative of $q$: $q'(x) = \frac{4}{\pi^2}(\pi - 2x) - \cos x$. -/
@[blueprint (statement := /-- The function $q'(x) = \frac{4}{\pi^2}(\pi-2x) - \cos x$, the derivative of `putnam_2025_a2_upper_q`. -/)]
noncomputable def putnam_2025_a2_upper_q' (x : ℝ) : ℝ := (4 / π ^ 2) * (π - 2 * x) - cos x

/-- Second derivative of $q$: $q''(x) = \sin x - \frac{8}{\pi^2}$. -/
@[blueprint (statement := /-- The function $q''(x) = \sin x - \frac{8}{\pi^2}$, the second derivative of `putnam_2025_a2_upper_q`. -/)]
noncomputable def putnam_2025_a2_upper_q'' (x : ℝ) : ℝ := sin x - 8 / π ^ 2

/-- Derivative of `putnam_2025_a2_upper_q` is `putnam_2025_a2_upper_q'`. -/
@[blueprint
  (statement := /-- For all $y \in \mathbb{R}$, $\mathrm{deriv}\,q\,y = q'(y)$. -/)
  (proof := /-- Compute $\frac{d}{dy}\left(\frac{4}{\pi^2}y(\pi-y) - \sin y\right) = \frac{4}{\pi^2}(\pi-2y) - \cos y$ by rewriting `deriv_sub`, `deriv_mul`, `deriv_const`, `deriv_id''`, `Real.deriv_sin`, supplying the `DifferentiableAt` side conditions via `fun_prop`. -/)
  (uses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q'])
  (proofUses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q'])]
lemma putnam_2025_a2_upper_q_deriv :
    ∀ y : ℝ, deriv putnam_2025_a2_upper_q y = putnam_2025_a2_upper_q' y := by
  intro y
  unfold putnam_2025_a2_upper_q putnam_2025_a2_upper_q'
  change deriv ((fun x : ℝ => 4 / Real.pi ^ 2 * (x * (Real.pi - x))) - (fun x : ℝ => Real.sin x)) y
      = 4 / Real.pi ^ 2 * (Real.pi - 2 * y) - Real.cos y
  rw [deriv_sub]
  · congr 1
    · change deriv (fun x : ℝ => 4 / Real.pi ^ 2 * (x * (Real.pi - x))) y
          = 4 / Real.pi ^ 2 * (Real.pi - 2 * y)
      rw [deriv_const_mul]
      · congr 1
        change deriv ((fun x : ℝ => x) * (fun x : ℝ => Real.pi - x)) y = Real.pi - 2 * y
        rw [deriv_mul]
        · rw [deriv_id'']
          change (fun x : ℝ => 1) y * (Real.pi - y) + y * deriv ((fun x : ℝ => Real.pi) - (fun x : ℝ => x)) y = Real.pi - 2 * y
          rw [deriv_sub]
          · rw [deriv_const, deriv_id'']
            simp
            ring
          · fun_prop
          · fun_prop
        · fun_prop
        · fun_prop
      · fun_prop
    · change deriv Real.sin y = Real.cos y
      rw [Real.deriv_sin]
  · fun_prop
  · fun_prop

/-- Derivative of `putnam_2025_a2_upper_q'` is `putnam_2025_a2_upper_q''`. -/
@[blueprint
  (statement := /-- For all $y \in \mathbb{R}$, $\mathrm{deriv}\,q'\,y = q''(y)$. -/)
  (proof := /-- Compute $\frac{d}{dy}\left(\frac{4}{\pi^2}(\pi-2y) - \cos y\right) = \sin y - \frac{8}{\pi^2}$ by rewriting `deriv_sub`, `deriv_mul`, `deriv_const`, `deriv_const_mul`, `deriv_const_sub`, `deriv_id''`, `Real.deriv_cos`. -/)
  (uses := [putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])]
lemma putnam_2025_a2_upper_q'_deriv :
    ∀ y : ℝ, deriv putnam_2025_a2_upper_q' y = putnam_2025_a2_upper_q'' y := by
  intro y
  unfold putnam_2025_a2_upper_q' putnam_2025_a2_upper_q''
  change deriv ((fun x : ℝ => 4 / Real.pi ^ 2 * (Real.pi - 2 * x)) - Real.cos) y = Real.sin y - 8 / Real.pi ^ 2
  rw [deriv_sub]
  · rw [deriv_const_mul]
    · change 4 / Real.pi ^ 2 * deriv ((fun _ : ℝ => Real.pi) - (fun x : ℝ => 2 * x)) y - deriv Real.cos y = Real.sin y - 8 / Real.pi ^ 2
      rw [deriv_sub, deriv_const, deriv_const_mul, deriv_id'', Real.deriv_cos]
      · ring
      · fun_prop
      · fun_prop
      · fun_prop
    · fun_prop
  · fun_prop
  · fun_prop

/-- Endpoint values of $q$, $q'$, $q''$ on $[0,\pi/2]$. -/
@[blueprint
  (statement := /-- $q(0) = q(\pi/2) = 0$, $q'(0) > 0$, $q'(\pi/2) = 0$, $q''(0) < 0 < q''(\pi/2)$. -/)
  (proof := /-- Unfold the definitions and use `Real.sin_pi_div_two`, `Real.cos_pi_div_two`, `field_simp`/`ring` for the algebra, `Real.pi_lt_four` for $q'(0) > 0$ ($4/\pi > 1$), and `Real.pi_gt_three` for $q''(\pi/2) > 0$ ($\pi^2 > 8$). -/)
  (uses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])]
lemma putnam_2025_a2_upper_q_endpoints :
    putnam_2025_a2_upper_q 0 = 0 ∧ putnam_2025_a2_upper_q (π / 2) = 0 ∧
      0 < putnam_2025_a2_upper_q' 0 ∧ putnam_2025_a2_upper_q' (π / 2) = 0 ∧
      putnam_2025_a2_upper_q'' 0 < 0 ∧ 0 < putnam_2025_a2_upper_q'' (π / 2) := by
  constructor
  · unfold putnam_2025_a2_upper_q; simp [Real.sin_zero]
  · constructor
    · unfold putnam_2025_a2_upper_q
      rw [Real.sin_pi_div_two]
      field_simp [Real.pi_ne_zero]
      ring
    · constructor
      · unfold putnam_2025_a2_upper_q'
        rw [Real.cos_zero]
        field_simp [Real.pi_ne_zero]
        nlinarith [Real.pi_lt_four, Real.pi_pos]
      · constructor
        · unfold putnam_2025_a2_upper_q'
          rw [Real.cos_pi_div_two]
          field_simp [Real.pi_ne_zero]
          ring
        · constructor
          · unfold putnam_2025_a2_upper_q''
            simp [Real.sin_zero]
            exact sq_pos_of_ne_zero Real.pi_ne_zero
          · unfold putnam_2025_a2_upper_q''
            rw [Real.sin_pi_div_two]
            field_simp [Real.pi_ne_zero]
            nlinarith [Real.pi_gt_three]

/-- $q''$ is strictly increasing on $[0,\pi/2]$. -/
@[blueprint
  (statement := /-- $\mathrm{StrictMonoOn}\,q''\,[0,\pi/2]$. -/)
  (proof := /-- $q''(x) = \sin x - 8/\pi^2$ is a translate of $\sin$, and $\sin$ is strictly increasing on $[-\pi/2,\pi/2] \supseteq [0,\pi/2]$ via `Real.strictMonoOn_sin`. -/)
  (uses := [putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q''])]
lemma putnam_2025_a2_upper_q''_strictMonoOn :
    StrictMonoOn putnam_2025_a2_upper_q'' (Set.Icc 0 (π / 2)) := by
  unfold putnam_2025_a2_upper_q''
  have hsub : Set.Icc 0 (π / 2) ⊆ Set.Icc (-(π / 2)) (π / 2) := by
    apply Set.Icc_subset_Icc
    · exact neg_nonpos.mpr (Real.pi_div_two_pos.le)
    · rfl
  simpa [sub_eq_add_neg] using
    (Real.strictMonoOn_sin.mono hsub).add_const (-(8 / π ^ 2))

/-- There is an inflection point $c \in (0,\pi/2)$ with $q''(c) = 0$;
$q'' \le 0$ on $[0,c]$ and $q'' \ge 0$ on $[c,\pi/2]$. -/
@[blueprint
  (statement := /-- $\exists c \in (0,\pi/2)$, $q''(c) = 0$ with $q'' \le 0$ on $[0,c]$ and $0 \le q''$ on $[c,\pi/2]$. -/)
  (proof := /-- By the intermediate value theorem (`intermediate_value_Icc`) applied to the continuous function $q''$ on $[0,\pi/2]$ with $q''(0) < 0 < q''(\pi/2)$, get $c$ with $q''(c) = 0$; strict monotonicity of $q''$ gives $0 < c < \pi/2$ and the sign profiles on the two halves. -/)
  (uses := [putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q''_strictMonoOn, putnam_2025_a2_upper_q_endpoints])]
lemma putnam_2025_a2_upper_q''_sign :
    ∃ c : ℝ, c ∈ Set.Ioo 0 (π / 2) ∧ putnam_2025_a2_upper_q'' c = 0 ∧
      (∀ y ∈ Set.Icc 0 c, putnam_2025_a2_upper_q'' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q'' y) := by
  have hcont : ContinuousOn putnam_2025_a2_upper_q'' (Set.Icc 0 (π / 2)) := by
    unfold putnam_2025_a2_upper_q''
    fun_prop
  have hle : (0 : ℝ) ≤ π / 2 := le_of_lt (by positivity)
  rcases putnam_2025_a2_upper_q_endpoints with ⟨hq0, hq2, hq'0, hq'2, hq''0lt, hq''2pos⟩
  have hmem : 0 ∈ Set.Icc (putnam_2025_a2_upper_q'' 0) (putnam_2025_a2_upper_q'' (π / 2)) :=
    ⟨le_of_lt hq''0lt, le_of_lt hq''2pos⟩
  have hzero : 0 ∈ putnam_2025_a2_upper_q'' '' Set.Icc 0 (π / 2) :=
    intermediate_value_Icc hle hcont hmem
  rcases hzero with ⟨c, hcIcc, hc0⟩
  have hcne0 : c ≠ 0 := by
    intro hc0eq
    have : putnam_2025_a2_upper_q'' 0 = 0 := by simpa [hc0eq] using hc0
    linarith
  have hcne2 : c ≠ π / 2 := by
    intro hc2eq
    have : putnam_2025_a2_upper_q'' (π / 2) = 0 := by simpa [hc2eq] using hc0
    linarith
  have hc0pos : 0 < c := lt_of_le_of_ne (Set.mem_Icc.mp hcIcc).1 (Ne.symm hcne0)
  have hc2lt : c < π / 2 := lt_of_le_of_ne (Set.mem_Icc.mp hcIcc).2 hcne2
  have hmono : MonotoneOn putnam_2025_a2_upper_q'' (Set.Icc 0 (π / 2)) :=
    putnam_2025_a2_upper_q''_strictMonoOn.monotoneOn
  refine ⟨c, Set.mem_Ioo.mpr ⟨hc0pos, hc2lt⟩, hc0, ?_, ?_⟩
  · intro y hy
    have hy0 : 0 ≤ y := (Set.mem_Icc.mp hy).1
    have hyc : y ≤ c := (Set.mem_Icc.mp hy).2
    have hyIcc : y ∈ Set.Icc 0 (π / 2) := Set.mem_Icc.mpr ⟨hy0, le_trans hyc (le_of_lt hc2lt)⟩
    have hle' : putnam_2025_a2_upper_q'' y ≤ putnam_2025_a2_upper_q'' c := hmono hyIcc hcIcc hyc
    simpa [hc0] using hle'
  · intro y hy
    have hcy : c ≤ y := (Set.mem_Icc.mp hy).1
    have hyIcc : y ∈ Set.Icc 0 (π / 2) :=
      Set.mem_Icc.mpr ⟨le_trans (le_of_lt hc0pos) hcy, (Set.mem_Icc.mp hy).2⟩
    have hle' : putnam_2025_a2_upper_q'' c ≤ putnam_2025_a2_upper_q'' y := hmono hcIcc hyIcc hcy
    simpa [hc0] using hle'

/-- On the two halves split at the inflection point, $q'$ is antitone on
$[0,c]$ and monotone on $[c,\pi/2]$. -/
@[blueprint
  (statement := /-- $\exists c \in (0,\pi/2)$, $q''(c)=0$, $q'' \le 0$ on $[0,c]$, $0 \le q''$ on $[c,\pi/2]$, $\mathrm{AntitoneOn}\,q'\,[0,c]$, $\mathrm{MonotoneOn}\,q'\,[c,\pi/2]$. -/)
  (proof := /-- From `putnam_2025_a2_upper_q''_sign` get the same $c$; apply `antitoneOn_of_deriv_nonpos` on $[0,c]$ and `monotoneOn_of_deriv_nonneg` on $[c,\pi/2]$, rewriting the derivative via `putnam_2025_a2_upper_q'_deriv` and using the sign profiles of $q''$. Continuity from `DifferentiableOn.continuousOn`. -/)
  (uses := [putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q'_deriv, putnam_2025_a2_upper_q''_sign])]
lemma putnam_2025_a2_upper_q'_mono :
    ∃ c : ℝ, c ∈ Set.Ioo 0 (π / 2) ∧ putnam_2025_a2_upper_q'' c = 0 ∧
      (∀ y ∈ Set.Icc 0 c, putnam_2025_a2_upper_q'' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q'' y) ∧
      AntitoneOn putnam_2025_a2_upper_q' (Set.Icc 0 c) ∧
      MonotoneOn putnam_2025_a2_upper_q' (Set.Icc c (π / 2)) := by
  rcases putnam_2025_a2_upper_q''_sign with ⟨c, hc, hc0, hle, hge⟩
  have hdiff : ∀ s : Set ℝ, DifferentiableOn ℝ putnam_2025_a2_upper_q' s := by
    intro s
    have hcont : ContDiff ℝ ⊤ putnam_2025_a2_upper_q' := by
      unfold putnam_2025_a2_upper_q'
      fun_prop
    have hdiffAt : Differentiable ℝ putnam_2025_a2_upper_q' := hcont.differentiable (by simp)
    exact hdiffAt.differentiableOn
  refine ⟨c, hc, hc0, hle, hge, ?_, ?_⟩
  · apply antitoneOn_of_deriv_nonpos (convex_Icc 0 c)
    · exact (hdiff (Set.Icc 0 c)).continuousOn
    · exact hdiff (interior (Set.Icc 0 c))
    · intro x hx
      rw [putnam_2025_a2_upper_q'_deriv]
      rw [interior_Icc] at hx
      exact hle x ⟨le_of_lt hx.1, le_of_lt hx.2⟩
  · apply monotoneOn_of_deriv_nonneg (convex_Icc c (π / 2))
    · exact (hdiff (Set.Icc c (π / 2))).continuousOn
    · exact hdiff (interior (Set.Icc c (π / 2)))
    · intro x hx
      rw [putnam_2025_a2_upper_q'_deriv]
      rw [interior_Icc] at hx
      exact hge x ⟨le_of_lt hx.1, le_of_lt hx.2⟩

/-- If $q'$ is antitone on $[0,c]$, $q'(0) > 0$ and $q'(c) < 0$, then there
is $\sigma \in (0,c)$ with $q'(\sigma) = 0$; $q' \ge 0$ on $[0,\sigma]$ and
$q' \le 0$ on $[\sigma,c]$. -/
@[blueprint
  (statement := /-- Second intermediate-value step for $q'$: under antitone $q'$ on $[0,c]$ with $q'(0) > 0 > q'(c)$, there is $\sigma \in (0,c)$ with $q'(\sigma) = 0$, $q' \ge 0$ on $[0,\sigma]$ and $q' \le 0$ on $[\sigma,c]$. -/)
  (proof := /-- Apply `intermediate_value_Icc` to $-q'$ on $[0,c]$ (continuous by differentiability of `putnam_2025_a2_upper_q'`) with $-q'(0) < 0 < -q'(c)$ to get $\sigma$ with $q'(\sigma) = 0$; antitone $q'$ transfers the sign to both halves, and $q'(0) \ne 0 \ne q'(c)$ gives $\sigma \in (0,c)$. -/)
  (uses := [putnam_2025_a2_upper_q'])
  (proofUses := [putnam_2025_a2_upper_q'])]
lemma putnam_2025_a2_upper_q'_sigma :
    ∀ c : ℝ, 0 < c → AntitoneOn putnam_2025_a2_upper_q' (Set.Icc 0 c) →
      0 < putnam_2025_a2_upper_q' 0 → putnam_2025_a2_upper_q' c < 0 →
      ∃ σ ∈ Set.Ioo 0 c, putnam_2025_a2_upper_q' σ = 0 ∧
        (∀ y ∈ Set.Icc 0 σ, 0 ≤ putnam_2025_a2_upper_q' y) ∧
        (∀ y ∈ Set.Icc σ c, putnam_2025_a2_upper_q' y ≤ 0) := by
  intro c hc hant h0 hcneg
  have hcontNeg : ContinuousOn (fun x : ℝ => -putnam_2025_a2_upper_q' x) (Set.Icc 0 c) := by
    unfold putnam_2025_a2_upper_q'
    fun_prop
  have hmid : (0 : ℝ) ∈ Set.Icc (-putnam_2025_a2_upper_q' 0) (-putnam_2025_a2_upper_q' c) := by
    constructor
    · exact le_of_lt (neg_lt_zero.mpr h0)
    · exact le_of_lt (neg_pos.mpr hcneg)
  have hIVT : (0 : ℝ) ∈ (fun x : ℝ => -putnam_2025_a2_upper_q' x) '' Set.Icc 0 c :=
    intermediate_value_Icc (a := 0) (b := c)
      (f := fun x : ℝ => -putnam_2025_a2_upper_q' x) hc.le hcontNeg hmid
  rcases hIVT with ⟨σ, hσin, hσneg⟩
  have hσ : putnam_2025_a2_upper_q' σ = 0 := neg_eq_zero.mp hσneg
  have hσ0 : σ ≠ 0 := by
    intro hs
    rw [hs] at hσ
    exact (ne_of_gt h0) hσ
  have hσc : σ ≠ c := by
    intro hs
    rw [hs] at hσ
    exact (ne_of_lt hcneg) hσ
  refine ⟨σ, ⟨lt_of_le_of_ne hσin.1 hσ0.symm, lt_of_le_of_ne hσin.2 hσc⟩, hσ, ?_, ?_⟩
  · intro y hy
    have hymem : y ∈ Set.Icc 0 c := ⟨hy.1, le_trans hy.2 hσin.2⟩
    have hq : putnam_2025_a2_upper_q' σ ≤ putnam_2025_a2_upper_q' y := hant hymem hσin hy.2
    rw [hσ] at hq
    exact hq
  · intro y hy
    have hymem : y ∈ Set.Icc 0 c := ⟨le_trans (lt_of_le_of_ne hσin.1 hσ0.symm).le hy.1, hy.2⟩
    have hq : putnam_2025_a2_upper_q' y ≤ putnam_2025_a2_upper_q' σ := hant hσin hymem hy.1
    rw [hσ] at hq
    exact hq

/-- $q' \le 0$ on the right half $[c,\pi/2]$ split at the inflection point. -/
@[blueprint
  (statement := /-- $\exists c \in (0,\pi/2)$ with the structural facts of `putnam_2025_a2_upper_q'_mono` and additionally $q' \le 0$ on $[c,\pi/2]$. -/)
  (proof := /-- From `putnam_2025_a2_upper_q'_mono` get $c$; $q'(\pi/2) = 0$ together with `MonotoneOn q' (Icc c (π/2))` gives $q' y \le q'(\pi/2) = 0$ for $y \in [c,\pi/2]$. -/)
  (uses := [putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q'_mono, putnam_2025_a2_upper_q_endpoints])]
lemma putnam_2025_a2_upper_q'_nonpos_right :
    ∃ c : ℝ, c ∈ Set.Ioo 0 (π / 2) ∧ putnam_2025_a2_upper_q'' c = 0 ∧
      (∀ y ∈ Set.Icc 0 c, putnam_2025_a2_upper_q'' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q'' y) ∧
      AntitoneOn putnam_2025_a2_upper_q' (Set.Icc 0 c) ∧
      MonotoneOn putnam_2025_a2_upper_q' (Set.Icc c (π / 2)) ∧
      (∀ y ∈ Set.Icc c (π / 2), putnam_2025_a2_upper_q' y ≤ 0) := by
  rcases putnam_2025_a2_upper_q'_mono with ⟨c, hc_mem, hc_eq, hqpp_left, hqpp_right, hanti, hmono⟩
  refine ⟨c, hc_mem, hc_eq, hqpp_left, hqpp_right, hanti, hmono, ?_⟩
  intro y hy
  have hq'_pi2 : putnam_2025_a2_upper_q' (π / 2) = 0 :=
    putnam_2025_a2_upper_q_endpoints.2.2.2.1
  have hmem_pi2 : π / 2 ∈ Set.Icc c (π / 2) := ⟨le_of_lt hc_mem.2, le_rfl⟩
  have hqy_le : putnam_2025_a2_upper_q' y ≤ putnam_2025_a2_upper_q' (π / 2) :=
    hmono hy hmem_pi2 hy.2
  rw [hq'_pi2] at hqy_le
  exact hqy_le

/-- On the right half $[c,\pi/2]$ split at the inflection point, $q \ge 0$. -/
@[blueprint
  (statement := /-- $\exists c \in (0,\pi/2)$ with the structural facts of `putnam_2025_a2_upper_q'_nonpos_right` and additionally $0 \le q$ on $[c,\pi/2]$. -/)
  (proof := /-- From `putnam_2025_a2_upper_q'_nonpos_right` get $c$; then `antitoneOn_of_deriv_nonpos` applied to $q$ (derivative `putnam_2025_a2_upper_q_deriv`) shows $q$ is antitone on $[c,\pi/2]$, so $q \ge q(\pi/2) = 0$. -/)
  (uses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q_deriv, putnam_2025_a2_upper_q'_nonpos_right, putnam_2025_a2_upper_q_endpoints])]
lemma putnam_2025_a2_upper_q_ge0_right :
    ∃ c : ℝ, c ∈ Set.Ioo 0 (π / 2) ∧ putnam_2025_a2_upper_q'' c = 0 ∧
      (∀ y ∈ Set.Icc 0 c, putnam_2025_a2_upper_q'' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q'' y) ∧
      AntitoneOn putnam_2025_a2_upper_q' (Set.Icc 0 c) ∧
      MonotoneOn putnam_2025_a2_upper_q' (Set.Icc c (π / 2)) ∧
      (∀ y ∈ Set.Icc c (π / 2), putnam_2025_a2_upper_q' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q y) := by
  rcases putnam_2025_a2_upper_q'_nonpos_right with ⟨c, hc, hc'', hle, hge, hanti, hmono, hnonpos⟩
  refine ⟨c, hc, hc'', hle, hge, hanti, hmono, hnonpos, ?_⟩
  intro y hy
  have hq : AntitoneOn putnam_2025_a2_upper_q (Set.Icc c (π / 2)) := by
    apply antitoneOn_of_deriv_nonpos
    · exact convex_Icc c (π / 2)
    · unfold putnam_2025_a2_upper_q
      fun_prop
    · unfold putnam_2025_a2_upper_q
      fun_prop
    · intro x hx
      rw [putnam_2025_a2_upper_q_deriv]
      exact hnonpos x (interior_subset hx)
  have hpi : (π / 2) ∈ Set.Icc c (π / 2) := by
    constructor
    · exact le_of_lt hc.2
    · exact le_rfl
  have hqy : putnam_2025_a2_upper_q (π / 2) ≤ putnam_2025_a2_upper_q y :=
    hq hy hpi hy.2
  rw [putnam_2025_a2_upper_q_endpoints.2.1] at hqy
  exact hqy

/-- On the left half $[0,c]$ split at the inflection point, $q \ge 0$. -/
@[blueprint
  (statement := /-- $\exists c \in (0,\pi/2)$ with the structural facts of `putnam_2025_a2_upper_q_ge0_right` and additionally $0 \le q$ on $[0,c]$. -/)
  (proof := /-- With the $c$ from `putnam_2025_a2_upper_q_ge0_right` (so $0 \le q(c)$): if $q'(c) \ge 0$, then antitone $q'$ on $[0,c]$ gives $q' \ge 0$ there, so $q$ is monotone and $q \ge q(0) = 0$.  If $q'(c) < 0$, `putnam_2025_a2_upper_q'_sigma` (using $q'(0) > 0$) provides $\sigma \in (0,c)$ with $q' \ge 0$ on $[0,\sigma]$ and $q' \le 0$ on $[\sigma,c]$; then $q$ is monotone on $[0,\sigma]$ (so $q \ge q(0) = 0$) and antitone on $[\sigma,c]$ (so $q \ge q(c) \ge 0$). -/)
  (uses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q', putnam_2025_a2_upper_q''])
  (proofUses := [putnam_2025_a2_upper_q_deriv, putnam_2025_a2_upper_q_endpoints,
    putnam_2025_a2_upper_q_ge0_right, putnam_2025_a2_upper_q'_sigma])]
lemma putnam_2025_a2_upper_q_ge0_left :
    ∃ c : ℝ, c ∈ Set.Ioo 0 (π / 2) ∧ putnam_2025_a2_upper_q'' c = 0 ∧
      (∀ y ∈ Set.Icc 0 c, putnam_2025_a2_upper_q'' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q'' y) ∧
      AntitoneOn putnam_2025_a2_upper_q' (Set.Icc 0 c) ∧
      MonotoneOn putnam_2025_a2_upper_q' (Set.Icc c (π / 2)) ∧
      (∀ y ∈ Set.Icc c (π / 2), putnam_2025_a2_upper_q' y ≤ 0) ∧
      (∀ y ∈ Set.Icc c (π / 2), 0 ≤ putnam_2025_a2_upper_q y) ∧
      (∀ y ∈ Set.Icc 0 c, 0 ≤ putnam_2025_a2_upper_q y) := by
  rcases putnam_2025_a2_upper_q_ge0_right with ⟨c, hc, hq''c, hq''le0_left, hq''ge0_right, hAnti, hMono, hq'le0_right, hqge0_right⟩
  have hq_cont : Continuous putnam_2025_a2_upper_q := by
    unfold putnam_2025_a2_upper_q
    fun_prop
  have hq_diff : Differentiable ℝ putnam_2025_a2_upper_q := by
    unfold putnam_2025_a2_upper_q
    fun_prop
  have hq_contOn : ∀ {a b : ℝ}, ContinuousOn putnam_2025_a2_upper_q (Set.Icc a b) := by
    intro a b
    exact hq_cont.continuousOn
  have hq_diffOn : ∀ {a b : ℝ}, DifferentiableOn ℝ putnam_2025_a2_upper_q (interior (Set.Icc a b)) := by
    intro a b
    exact hq_diff.differentiableOn
  have hq_monoOn : ∀ {a b : ℝ}, (∀ x ∈ Set.Icc a b, 0 ≤ putnam_2025_a2_upper_q' x) →
      MonotoneOn putnam_2025_a2_upper_q (Set.Icc a b) := by
    intro a b hnonneg
    refine monotoneOn_of_deriv_nonneg (convex_Icc a b) hq_contOn ?_ ?_
    · exact hq_diffOn
    · intro x hx
      have hx' : x ∈ Set.Icc a b := interior_subset hx
      have h := hnonneg x hx'
      simpa [putnam_2025_a2_upper_q_deriv] using h
  have hq_antiOn : ∀ {a b : ℝ}, (∀ x ∈ Set.Icc a b, putnam_2025_a2_upper_q' x ≤ 0) →
      AntitoneOn putnam_2025_a2_upper_q (Set.Icc a b) := by
    intro a b hnonpos
    refine antitoneOn_of_deriv_nonpos (convex_Icc a b) hq_contOn ?_ ?_
    · exact hq_diffOn
    · intro x hx
      have hx' : x ∈ Set.Icc a b := interior_subset hx
      have h := hnonpos x hx'
      simpa [putnam_2025_a2_upper_q_deriv] using h
  have hq0eq : putnam_2025_a2_upper_q 0 = 0 := putnam_2025_a2_upper_q_endpoints.1
  have hq0pos : 0 < putnam_2025_a2_upper_q' 0 := putnam_2025_a2_upper_q_endpoints.2.2.1
  have hc0 : 0 < c := hc.1
  have hcp : c < Real.pi / 2 := hc.2
  have h0mem : 0 ∈ Set.Icc 0 c := ⟨le_rfl, le_of_lt hc0⟩
  have hcmem : c ∈ Set.Icc 0 c := ⟨le_of_lt hc0, le_rfl⟩
  have hqge0c : 0 ≤ putnam_2025_a2_upper_q c := hqge0_right c ⟨le_rfl, le_of_lt hcp⟩
  have hq_ge0_left : ∀ y ∈ Set.Icc 0 c, 0 ≤ putnam_2025_a2_upper_q y := by
    by_cases hge : 0 ≤ putnam_2025_a2_upper_q' c
    · have hq'_ge0_left : ∀ y ∈ Set.Icc 0 c, 0 ≤ putnam_2025_a2_upper_q' y := by
        intro y hy
        exact le_trans hge (hAnti hy hcmem hy.2)
      have hq_mono : MonotoneOn putnam_2025_a2_upper_q (Set.Icc 0 c) := hq_monoOn hq'_ge0_left
      intro y hy
      have h := hq_mono h0mem hy hy.1
      simpa [hq0eq] using h
    · have hlt : putnam_2025_a2_upper_q' c < 0 := lt_of_not_ge hge
      rcases putnam_2025_a2_upper_q'_sigma c hc0 hAnti hq0pos hlt with ⟨σ, hσ, _hσq'eq, hσge0, hσc_le0⟩
      have hσ0 : 0 < σ := hσ.1
      have hσc : σ < c := hσ.2
      have hq_mono_0σ : MonotoneOn putnam_2025_a2_upper_q (Set.Icc 0 σ) := hq_monoOn hσge0
      have hq_anti_σc : AntitoneOn putnam_2025_a2_upper_q (Set.Icc σ c) := hq_antiOn hσc_le0
      intro y hy
      by_cases hyle : y ≤ σ
      · have hy' : y ∈ Set.Icc 0 σ := ⟨hy.1, hyle⟩
        have h0σ : 0 ∈ Set.Icc 0 σ := ⟨le_rfl, le_of_lt hσ0⟩
        have h := hq_mono_0σ h0σ hy' hy.1
        simpa [hq0eq] using h
      · have hσley : σ ≤ y := le_of_not_ge hyle
        have hy' : y ∈ Set.Icc σ c := ⟨hσley, hy.2⟩
        have hcmem' : c ∈ Set.Icc σ c := ⟨le_of_lt hσc, le_rfl⟩
        have hqy : putnam_2025_a2_upper_q c ≤ putnam_2025_a2_upper_q y := hq_anti_σc hy' hcmem' hy.2
        exact le_trans hqge0c hqy
  exact ⟨c, hc, hq''c, hq''le0_left, hq''ge0_right, hAnti, hMono, hq'le0_right, hqge0_right, hq_ge0_left⟩

/-- $q \ge 0$ on the whole interval $[0,\pi/2]$. -/
@[blueprint
  (statement := /-- For all $x \in [0,\pi/2]$, $0 \le q(x)$. -/)
  (proof := /-- From `putnam_2025_a2_upper_q_ge0_left` get the split point $c$ together with $q \ge 0$ on both $[0,c]$ and $[c,\pi/2]$; split $x$ by `by_cases x ≤ c`. -/)
  (uses := [putnam_2025_a2_upper_q])
  (proofUses := [putnam_2025_a2_upper_q_ge0_left])]
lemma putnam_2025_a2_upper_q_nonneg :
    ∀ x ∈ Set.Icc 0 (π / 2), 0 ≤ putnam_2025_a2_upper_q x := by
  intro x hx
  rcases putnam_2025_a2_upper_q_ge0_left with ⟨c, hc, hc_eq, hc_left, hc_right, hc_anti, hc_mono, hc_deriv_le, hc_q_right, hc_q_left⟩
  by_cases h : x ≤ c
  · exact hc_q_left x ⟨hx.1, h⟩
  · exact hc_q_right x ⟨le_of_not_ge h, hx.2⟩

/-- Upper inequality on the left half $[0,\pi/2]$:
$\sin x \le \frac{4}{\pi^2}x(\pi-x)$. -/
@[blueprint
  (statement := /-- On $x \in [0, \pi/2]$, $\sin x \le \frac{4}{\pi^2}x(\pi-x)$. -/)
  (proof := /-- Show $q(x) = \frac{4}{\pi^2}x(\pi-x) - \sin x \ge 0$ on $[0,\pi/2]$ via `putnam_2025_a2_upper_q_nonneg` and reassociate the product (`← mul_assoc`).  Nonnegativity of $q$ follows from the derivative sign-profile chain: $q'' = \sin - 8/\pi^2$ is strictly increasing and crosses zero at the unique $c \in (0,\pi/2)$, making $q'$ antitone on $[0,c]$ and monotone on $[c,\pi/2]$; on the right half $q \ge q(\pi/2) = 0$, and on the left half $q'(0) > 0$ with (if $q'(c) < 0$) a second IVT zero of $q'$ give $q \ge q(0) = q(c) = 0$. -/)
  (proofUses := [putnam_2025_a2_upper_q, putnam_2025_a2_upper_q_nonneg])]
lemma putnam_2025_a2_upper_bound_left :
    ∀ x ∈ Set.Icc 0 (π / 2), sin x ≤ (4 / π ^ 2) * x * (π - x) := by
  intro x hx
  have h := putnam_2025_a2_upper_q_nonneg x hx
  change 0 ≤ 4 / π ^ 2 * (x * (π - x)) - sin x at h
  nlinarith [h]

/-- Upper inequality on the right half $[\pi/2,\pi]$, by symmetry from the
left half. -/
@[blueprint
  (statement := /-- On $x \in [\pi/2, \pi]$, $\sin x \le \frac{4}{\pi^2}x(\pi-x)$. -/)
  (proof := /-- Symmetry exactly as in `putnam_2025_a2_lower_bound_right`: apply `putnam_2025_a2_upper_bound_left` to $y = \pi - x$ and rewrite with `Real.sin_pi_sub` and the identity $(\pi-y)(\pi-(\pi-y)) = y(\pi-y)$. -/)
  (proofUses := [putnam_2025_a2_upper_bound_left])]
lemma putnam_2025_a2_upper_bound_right :
    ∀ x ∈ Set.Icc (π / 2) π, sin x ≤ (4 / π ^ 2) * x * (π - x) := by
  intro x hx
  let y := π - x
  have hy_mem : y ∈ Set.Icc 0 (π / 2) := by
    constructor
    · linarith [hx.2]
    · linarith [hx.1]
  have hmain := putnam_2025_a2_upper_bound_left y hy_mem
  dsimp [y] at hmain
  rw [Real.sin_pi_sub] at hmain
  have hrewrite : (4 / π ^ 2) * (π - x) * (π - (π - x)) = (4 / π ^ 2) * x * (π - x) := by
    ring
  exact hmain.trans_eq hrewrite

/-- The upper inequality on the whole interval $[0,\pi]$; this is exactly
membership of $b = 4/\pi^2$ in `putnam_2025_a2_B`. -/
@[blueprint
  (statement := /-- For all $x \in [0,\pi]$, $\sin x \le \frac{4}{\pi^2}x(\pi-x)$; hence $b = 4/\pi^2$ is admissible. -/)
  (proof := /-- Split $[0,\pi]$ at $\pi/2$ as in `putnam_2025_a2_lower_bound` and apply `putnam_2025_a2_upper_bound_left` or `putnam_2025_a2_upper_bound_right` according to the case. -/)
  (proofUses := [putnam_2025_a2_upper_bound_left, putnam_2025_a2_upper_bound_right])]
lemma putnam_2025_a2_upper_bound :
    ∀ x ∈ Set.Icc 0 π, sin x ≤ (4 / π ^ 2) * x * (π - x) := by
  intro x hx
  by_cases h : x ≤ π / 2
  · exact putnam_2025_a2_upper_bound_left x ⟨hx.1, h⟩
  · exact putnam_2025_a2_upper_bound_right x ⟨le_of_not_ge h, hx.2⟩

-- ---------------------------------------------------------------------------
-- Limit at 0 and sharpness of the lower constant
-- ---------------------------------------------------------------------------

/-- $\lim_{x \to 0^+} f(x) = 1/\pi$ for $f(x) = \sin x/(x(\pi-x))$. -/
@[blueprint
  (statement := /-- $\lim_{x \to 0^+} \frac{\sin x}{x(\pi-x)} = \frac{1}{\pi}$. -/)
  (proof := /-- On $x > 0$, unfold `putnam_2025_a2_f` and write $f(x) = \operatorname{sinc}(x) \cdot \frac{1}{\pi - x}$.  `Real.continuous_sinc` together with `Real.sinc_zero` gives $\operatorname{sinc}(x) \to 1$ as $x \to 0$ (restricted to $x > 0$ via `tendsto_nhdsWithin_of_tendsto_nhds`), and continuity of $x \mapsto 1/(\pi-x)$ at $0$ (using $\pi \ne 0$) gives the second factor $\to 1/\pi$; multiply the two limits. -/)
  (uses := [putnam_2025_a2_f])
  (proofUses := [putnam_2025_a2_f])]
lemma putnam_2025_a2_tendsto_zero :
    Tendsto putnam_2025_a2_f (𝓝[>] 0) (𝓝 (1 / π)) := by
  have hlt : ∀ᶠ x : ℝ in 𝓝[>] (0:ℝ), x < Real.pi := by
    exact Filter.Eventually.filter_mono nhdsWithin_le_nhds (isOpen_Iio.mem_nhds (by simpa using Real.pi_pos))
  have h_eq : putnam_2025_a2_f =ᶠ[𝓝[>] (0:ℝ)] (fun x : ℝ => Real.sinc x * (1 / (Real.pi - x))) := by
    filter_upwards [self_mem_nhdsWithin, hlt] with x hx0 hxπ
    have hx : x ≠ 0 := ne_of_gt hx0
    have hxne : Real.pi - x ≠ 0 := sub_ne_zero.mpr (ne_of_gt hxπ)
    rw [show putnam_2025_a2_f x = Real.sin x / (x * (Real.pi - x)) by rfl]
    rw [Real.sinc_of_ne_zero hx]
    field_simp [hx, hxne]
  have h1 : Tendsto Real.sinc (𝓝[>] (0:ℝ)) (𝓝 (1:ℝ)) := by
    apply tendsto_nhdsWithin_of_tendsto_nhds
    simpa using (Real.continuous_sinc.tendsto 0)
  have hcont : ContinuousAt (fun x : ℝ => 1 / (Real.pi - x)) 0 := by
    exact continuousAt_const.div (continuousAt_const.sub continuousAt_id) (by simpa using Real.pi_ne_zero)
  have h2 : Tendsto (fun x : ℝ => 1 / (Real.pi - x)) (𝓝[>] (0:ℝ)) (𝓝 (1 / Real.pi)) := by
    apply tendsto_nhdsWithin_of_tendsto_nhds
    simpa using hcont.tendsto
  have hprod : Tendsto (fun x : ℝ => Real.sinc x * (1 / (Real.pi - x))) (𝓝[>] (0:ℝ)) (𝓝 (1 * (1 / Real.pi))) := h1.mul h2
  simpa using (Filter.Tendsto.congr' h_eq.symm hprod)

/-- Sharpness of the lower constant: any $a' > 1/\pi$ is violated at some
$x \in (0,\pi)$. -/
@[blueprint
  (statement := /-- If $a' > 1/\pi$ then there exists $x \in (0,\pi)$ with $\sin x < a'\,x(\pi-x)$. -/)
  (proof := /-- From `putnam_2025_a2_tendsto_zero` and $1/\pi < a'$, `Filter.Tendsto.eventually` applied to the open half-line $\{y \mid y < a'\}$ yields $\forallᶠ x$ in $\mathbb{N}^+_0$, $f\,x < a'$; the conditions $0 < x$ and $x < \pi$ are also eventually true there, so some $x \in (0,\pi)$ satisfies $f\,x < a'$.  Unfolding `putnam_2025_a2_f` and multiplying by the positive factor $x(\pi-x)$ (via `div_lt_iff₀` and `lt_div_iff₀`) gives $\sin x < a'\,x(\pi-x)$. -/)
  (uses := [putnam_2025_a2_f])
  (proofUses := [putnam_2025_a2_tendsto_zero, putnam_2025_a2_f])]
lemma putnam_2025_a2_exists_lt :
    ∀ a' : ℝ, 1 / π < a' → ∃ x ∈ Set.Ioo 0 π, sin x < a' * x * (π - x) := by
  intro a' ha'
  have hf_lt : ∀ᶠ x in nhdsWithin (0 : ℝ) (Set.Ioi 0), putnam_2025_a2_f x < a' :=
    putnam_2025_a2_tendsto_zero.eventually (eventually_lt_nhds ha')
  have hx0 : ∀ᶠ x in nhdsWithin (0 : ℝ) (Set.Ioi 0), (0 : ℝ) < x := by
    exact self_mem_nhdsWithin
  have hxπ : ∀ᶠ x in nhdsWithin (0 : ℝ) (Set.Ioi 0), x < Real.pi :=
    (eventually_lt_nhds Real.pi_pos).filter_mono nhdsWithin_le_nhds
  have hcomb : ∀ᶠ x in nhdsWithin (0 : ℝ) (Set.Ioi 0),
      (0 : ℝ) < x ∧ (x < Real.pi ∧ putnam_2025_a2_f x < a') :=
    hx0.and (hxπ.and hf_lt)
  rcases hcomb.exists with ⟨x, hx0', hxπ', hxf'⟩
  have hpos : 0 < x * (Real.pi - x) := mul_pos hx0' (sub_pos.mpr hxπ')
  have hsin : Real.sin x < a' * (x * (Real.pi - x)) := by
    have hdiv : Real.sin x / (x * (Real.pi - x)) < a' := by
      simpa [putnam_2025_a2_f] using hxf'
    exact (div_lt_iff₀ hpos).mp hdiv
  refine ⟨x, ⟨hx0', hxπ'⟩, ?_⟩
  simpa [mul_assoc] using hsin

-- ---------------------------------------------------------------------------
-- Tightness of the upper constant at the midpoint
-- ---------------------------------------------------------------------------

/-- The upper bound is attained at the midpoint $x = \pi/2$. -/
@[blueprint
  (statement := /-- $\frac{4}{\pi^2}\cdot\frac{\pi}{2}\cdot(\pi-\frac{\pi}{2}) = \sin\frac{\pi}{2}$. -/)
  (proof := /-- `Real.sin_pi_div_two` gives $\sin(\pi/2) = 1$, and ring arithmetic gives $\frac{4}{\pi^2}\cdot\frac{\pi}{2}\cdot\frac{\pi}{2} = 1$. -/)
  (proofUses := [])]
lemma putnam_2025_a2_midpoint_tight :
    (4 / π ^ 2) * (π / 2) * (π - π / 2) = sin (π / 2) := by
  rw [Real.sin_pi_div_two]
  field_simp [Real.pi_ne_zero]
  ring

-- ---------------------------------------------------------------------------
-- Maximality / minimality inside the admissible sets
-- ---------------------------------------------------------------------------

/-- Every admissible $a'$ satisfies $a' \le 1/\pi$. -/
@[blueprint
  (statement := /-- For all $a' \in$ `putnam_2025_a2_A`, $a' \le 1/\pi$: no constant larger than $1/\pi$ is admissible. -/)
  (proof := /-- By `le_of_not_gt`; assuming $1/\pi < a'$, `putnam_2025_a2_exists_lt` provides $x \in (0,\pi)$ with $\sin x < a'\,x(\pi-x)$, contradicting the membership $a' \in$ `putnam_2025_a2_A` instantiated at that $x$. -/)
  (uses := [putnam_2025_a2_A])
  (proofUses := [putnam_2025_a2_exists_lt, putnam_2025_a2_A])]
lemma putnam_2025_a2_A_le :
    ∀ a' ∈ putnam_2025_a2_A, a' ≤ 1 / π := by
  intro a' hA
  by_contra hnot
  have hgt : 1 / Real.pi < a' := lt_of_not_ge hnot
  rcases putnam_2025_a2_exists_lt a' hgt with ⟨x, hx, hlt⟩
  have hxcc : x ∈ Set.Icc 0 Real.pi := Set.Ioo_subset_Icc_self hx
  have hle : a' * x * (Real.pi - x) ≤ Real.sin x := hA x hxcc
  exact (not_lt_of_ge hle) hlt

/-- Every admissible $b'$ satisfies $4/\pi^2 \le b'$. -/
@[blueprint
  (statement := /-- For all $b' \in$ `putnam_2025_a2_B`, $4/\pi^2 \le b'$: no constant smaller than $4/\pi^2$ is admissible. -/)
  (proof := /-- From $b' \in$ `putnam_2025_a2_B` instantiate at $x = \pi/2 \in [0,\pi]$: $\sin(\pi/2) \le b'\,(\pi/2)(\pi-\pi/2)$.  Combine with `putnam_2025_a2_midpoint_tight`; since $(\pi/2)(\pi/2) > 0$ (via `Real.pi_pos`), cancel it to obtain $4/\pi^2 \le b'$. -/)
  (uses := [putnam_2025_a2_B])
  (proofUses := [putnam_2025_a2_midpoint_tight, putnam_2025_a2_B])]
lemma putnam_2025_a2_B_le :
    ∀ b' ∈ putnam_2025_a2_B, 4 / π ^ 2 ≤ b' := by
  intro b' hb'
  have hb'x : ∀ x ∈ Set.Icc 0 Real.pi, Real.sin x ≤ b' * x * (Real.pi - x) := by
    simpa [putnam_2025_a2_B] using hb'
  have hx : Real.pi / 2 ∈ Set.Icc 0 Real.pi := by
    constructor
    · exact div_nonneg (le_of_lt Real.pi_pos) (by norm_num)
    · nlinarith [Real.pi_pos]
  have hmain := hb'x (Real.pi / 2) hx
  rw [← putnam_2025_a2_midpoint_tight] at hmain
  have hmain' : (4 / Real.pi ^ 2) * ((Real.pi / 2) * (Real.pi - Real.pi / 2)) ≤
      b' * ((Real.pi / 2) * (Real.pi - Real.pi / 2)) := by
    simpa [mul_assoc] using hmain
  have hpos : 0 < (Real.pi / 2) * (Real.pi - Real.pi / 2) := by
    rw [show Real.pi - Real.pi / 2 = Real.pi / 2 by ring]
    positivity
  exact (mul_le_mul_iff_of_pos_right hpos).mp hmain'

/-- $1/\pi$ is the greatest element of `putnam_2025_a2_A`. -/
@[blueprint
  (statement := /-- $\mathrm{IsGreatest}\,(\text{`putnam_2025_a2_A`})\,(1/\pi)$. -/)
  (proof := /-- `IsGreatest` is membership plus maximality: membership $\frac{1}{\pi} \in$ `putnam_2025_a2_A` is exactly `putnam_2025_a2_lower_bound` after unfolding `putnam_2025_a2_A`; maximality is `putnam_2025_a2_A_le`. -/)
  (uses := [putnam_2025_a2_A])
  (proofUses := [putnam_2025_a2_lower_bound, putnam_2025_a2_A_le, putnam_2025_a2_A])]
lemma putnam_2025_a2_is_greatest_A :
    IsGreatest putnam_2025_a2_A (1 / π) := by
  constructor
  · simpa [putnam_2025_a2_A] using putnam_2025_a2_lower_bound
  · exact putnam_2025_a2_A_le

/-- $4/\pi^2$ is the least element of `putnam_2025_a2_B`. -/
@[blueprint
  (statement := /-- $\mathrm{IsLeast}\,(\text{`putnam_2025_a2_B`})\,(4/\pi^2)$. -/)
  (proof := /-- Membership $\frac{4}{\pi^2} \in$ `putnam_2025_a2_B` is `putnam_2025_a2_upper_bound` after unfolding `putnam_2025_a2_B`; minimality is `putnam_2025_a2_B_le`. -/)
  (uses := [putnam_2025_a2_B])
  (proofUses := [putnam_2025_a2_upper_bound, putnam_2025_a2_B_le, putnam_2025_a2_B])]
lemma putnam_2025_a2_is_least_B :
    IsLeast putnam_2025_a2_B (4 / π ^ 2) := by
  constructor
  · rw [putnam_2025_a2_B]
    intro x hx
    exact putnam_2025_a2_upper_bound x hx
  · intro b hb
    exact putnam_2025_a2_B_le b hb

-- ---------------------------------------------------------------------------
-- Uniqueness of the optimal constants
-- ---------------------------------------------------------------------------

/-- The greatest element of `putnam_2025_a2_A` (if any) is forced to be
$1/\pi$. -/
@[blueprint
  (statement := /-- For all $a : \mathbb{R}$, $\mathrm{IsGreatest}\,(\text{`putnam_2025_a2_A`})\,a \to a = 1/\pi$. -/)
  (proof := /-- Apply `IsGreatest.unique` to the given greatest element and `putnam_2025_a2_is_greatest_A`. -/)
  (uses := [putnam_2025_a2_A])
  (proofUses := [putnam_2025_a2_is_greatest_A])]
lemma putnam_2025_a2_A_unique :
    ∀ a : ℝ, IsGreatest putnam_2025_a2_A a → a = 1 / π := by
  intro a ha
  exact IsGreatest.unique ha putnam_2025_a2_is_greatest_A

/-- The least element of `putnam_2025_a2_B` (if any) is forced to be
$4/\pi^2$. -/
@[blueprint
  (statement := /-- For all $b : \mathbb{R}$, $\mathrm{IsLeast}\,(\text{`putnam_2025_a2_B`})\,b \to b = 4/\pi^2$. -/)
  (proof := /-- Apply `IsLeast.unique` to the given least element and `putnam_2025_a2_is_least_B`. -/)
  (uses := [putnam_2025_a2_B])
  (proofUses := [putnam_2025_a2_is_least_B])]
lemma putnam_2025_a2_B_unique :
    ∀ b : ℝ, IsLeast putnam_2025_a2_B b → b = 4 / π ^ 2 := by
  intro b hb
  exact IsLeast.unique hb putnam_2025_a2_is_least_B

-- ---------------------------------------------------------------------------
-- Main theorem
-- ---------------------------------------------------------------------------

/-- Putnam 2025 A2: $(a,b) = (1/\pi,\ 4/\pi^2)$ if and only if $a$ is the
largest constant with $a\,x(\pi-x) \le \sin x$ on $[0,\pi]$ and $b$ is the
smallest constant with $\sin x \le b\,x(\pi-x)$ on $[0,\pi]$. -/
@[blueprint
  (statement := /-- $(a,b) = (1/\pi,\ 4/\pi^2)$ iff $a$ is the greatest admissible lower constant and $b$ the least admissible upper constant. -/)
  (proof := /-- Forward: unfold `putnam_2025_a2_solution` to get $a = 1/\pi$ and $b = 4/\pi^2$, then substitute into `putnam_2025_a2_is_greatest_A` and `putnam_2025_a2_is_least_B` (the inline sets in the statement are defeq to the abbrevs `putnam_2025_a2_A`, `putnam_2025_a2_B`).  Backward: `putnam_2025_a2_A_unique` and `putnam_2025_a2_B_unique` give $a = 1/\pi$ and $b = 4/\pi^2$, hence $(a,b) = $ `putnam_2025_a2_solution` by `Prod.ext`. -/)
  (uses := [putnam_2025_a2_solution])
  (proofUses := [putnam_2025_a2_solution, putnam_2025_a2_is_greatest_A, putnam_2025_a2_is_least_B, putnam_2025_a2_A_unique, putnam_2025_a2_B_unique])]
theorem putnam_2025_a2 (a b : ℝ) :
  ((a, b) = putnam_2025_a2_solution) ↔
  (IsGreatest {a' : ℝ | ∀ x ∈ Set.Icc 0 π, a' * x * (π - x) ≤ sin x} a ∧
   IsLeast {b' : ℝ | ∀ x ∈ Set.Icc 0 π, sin x ≤ b' * x * (π - x)} b) := by
  constructor
  · intro h
    have ha : a = 1 / Real.pi := congrArg Prod.fst h
    have hb : b = 4 / Real.pi ^ 2 := congrArg Prod.snd h
    constructor
    · change IsGreatest putnam_2025_a2_A a
      rw [ha]
      exact putnam_2025_a2_is_greatest_A
    · change IsLeast putnam_2025_a2_B b
      rw [hb]
      exact putnam_2025_a2_is_least_B
  · intro h
    rcases h with ⟨hA, hB⟩
    rw [putnam_2025_a2_A_unique a hA, putnam_2025_a2_B_unique b hB]
