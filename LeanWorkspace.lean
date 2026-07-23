import Mathlib
import Architect
open Set MeasureTheory

/-!
# Putnam 1962 A2

**Problem statement (informal):**
Find every real-valued function f whose domain is an interval I (finite or infinite) having
0 as a left-hand endpoint, such that for every positive member x of I the average of f over
the closed interval [0, x] is equal to the geometric mean of the numbers f(0) and f(x).

**Formalization approach:**
The predicate `P s f` means: (i) f is nonnegative on its domain, and (ii) for every x ∈ s,
the average of f over `Ico 0 x` (i.e., `[0, x)`) equals `Real.sqrt (f 0 * f x)`.

The solution set S consists of functions belonging to one of four families:
  1. f(x) = a / (1 - c*x)²  for some a ≥ 0, c ∈ ℝ (domain: ℝ if c ≤ 0; (-∞, 1/c) if c > 0)
  2. f(x) = a / (1 - c*x)² for x < 1/c and 0 elsewhere, with a ≥ 0, c > 0
  3. Any nonnegative f with f(x) = 0 for all x > 0
  4. Nonnegative f with f(0) = 0 and such that for some e > 0, the average over [0,x] is 0
     for all x ∈ (0, e)
-/

set_option linter.unusedVariables false

/-- The solution set S for Putnam 1962 A2. A function f belongs to S iff it is of
    one of the four types described in the problem solution. -/
@[blueprint (statement := /-- The solution set of all functions $f: \mathbb{R} \to \mathbb{R}$ satisfying the functional equation on $(0,\infty)$ or on a right-neighborhood of $0$. -/)]
def putnam_1962_a2_solution : Set (ℝ → ℝ) :=
  {f | (∃ a c : ℝ, 0 ≤ a ∧ f = (fun x : ℝ ↦ a / ((1 : ℝ) - c * x) ^ 2)) ∨
      (∃ a c : ℝ, 0 ≤ a ∧ 0 < c ∧ f = (fun x : ℝ ↦ if x < (1 : ℝ) / c then a / ((1 : ℝ) - c * x) ^ 2 else 0)) ∨
      (0 ≤ f ∧ ∀ x : ℝ, 0 < x → f x = 0) ∨
      (∃ e : ℝ, 0 < e ∧ f 0 = 0 ∧ 0 ≤ f ∧ ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0)}

/-- The condition that the average of f over [0,x] equals the geometric mean of f(0) and f(x),
    for all x ∈ s. -/
@[blueprint (statement := /-- For a set $s\subseteq\mathbb{R}_{>0}$ and $f:\mathbb{R}\to\mathbb{R}$, $P(s,f)$ holds iff $f$ is nonnegative and for every $x\in s$, the average of $f$ over $[0,x]$ equals $\sqrt{f(0)f(x)}$. -/)]
def averageGeometricCondition (s : Set ℝ) (f : ℝ → ℝ) : Prop :=
  0 ≤ f ∧ ∀ x ∈ s, (⨍ t in Ico (0 : ℝ) x, f t) = Real.sqrt (f 0 * f x)

/-! ## Helper definitions for analyzing the functional equation -/

/-- The primitive (integral) of f from 0 to x: F(x) = ∫_0^x f(t) dt. -/
@[blueprint (statement := /-- The definite integral of $f$ from $0$ to $x$: $F(x)=\int_0^x f(t)\,dt$. -/)]
noncomputable def primitive (f : ℝ → ℝ) (x : ℝ) : ℝ := ∫ t in (0 : ℝ)..x, f t

/-- The average function: A_f(x) = (1/x) * ∫_0^x f(t) dt, defined for x ≠ 0.
    This equals ⨍ t in Ico 0 x, f t when x > 0. -/
@[blueprint (statement := /-- The average of $f$ over $[0,x]$, defined as $\frac{1}{x}\int_0^x f(t)\,dt$ for $x>0$. -/)]
noncomputable def averageOnIco (f : ℝ → ℝ) (x : ℝ) : ℝ := ⨍ t in Ico (0 : ℝ) x, f t

/-! ## Lemma: Relating the average to the primitive -/

@[blueprint
  (statement := /-- For $x>0$, the average of $f$ over $[0,x]$ equals $\frac{1}{x}\int_0^x f(t)\,dt$. More precisely, $\int_0^x f(t)\,dt = x \cdot \operatorname{avg}_{[0,x]} f$. -/)
  (proof := /-- From the definition, `⨍ t in Ico 0 x, f t = (volume (Ico 0 x))⁻¹ • ∫ t in Ico 0 x, f t`.
    Since `volume (Ico 0 x) = x` for $x>0$, and `∫ t in Ico 0 x, f t = ∫_0^x f(t)\,dt`, we get the result. -/)
  (proofUses := [])]
lemma average_eq_integral_div_x (f : ℝ → ℝ) (x : ℝ) (hx : 0 < x) : (⨍ t in Ico (0 : ℝ) x, f t) = (∫ t in (0 : ℝ)..x, f t) / x := by
  sorry_using []

/-- If the average of f over [0,x] equals some value c, then the integral of f from 0 to x is c*x. -/
@[blueprint
  (statement := /-- If $\operatorname{avg}_{[0,x]} f = c$, then $\int_0^x f(t)\,dt = c\cdot x$ for $x>0$. -/)
  (proof := /-- Multiply both sides of `average_eq_integral_div_x` by $x$. -/)
  (proofUses := [average_eq_integral_div_x])]
lemma integral_eq_average_mul_x (f : ℝ → ℝ) (x : ℝ) (c : ℝ) (hx : 0 < x) (havg : (⨍ t in Ico (0 : ℝ) x, f t) = c) :
    (∫ t in (0 : ℝ)..x, f t) = c * x := by
  sorry_using [average_eq_integral_div_x]

/-! ## Case analysis based on whether f(0) is zero or positive -/

@[blueprint
  (statement := /-- If $P((0,\infty),f)$ or $P((0,e),f)$, then $f$ is nonnegative and
    $\forall x\in s$, $\operatorname{avg}_{[0,x]} f = \sqrt{f(0)f(x)}$. -/)
  (proof := /-- Immediate from the definition of $P$. -/)
  (proofUses := [])]
lemma P_implies_nonneg_and_eq (s : Set ℝ) (f : ℝ → ℝ) (hP : averageGeometricCondition s f) (x : ℝ) (hx : x ∈ s) :
    0 ≤ f ∧ (⨍ t in Ico (0 : ℝ) x, f t) = Real.sqrt (f 0 * f x) := by
  sorry_using []

/-- The geometric mean is zero iff at least one of the factors is zero. -/
@[blueprint
  (statement := /-- $\sqrt{a\cdot b}=0$ iff $a=0$ or $b=0$ for nonnegative $a,b$. -/)
  (proof := /-- Since $a,b\ge0$, $\sqrt{ab}=0 \iff ab=0 \iff a=0\lor b=0$. -/)
  (proofUses := [])]
lemma sqrt_eq_zero_iff (a b : ℝ) (ha : 0 ≤ a) (hb : 0 ≤ b) : Real.sqrt (a * b) = 0 ↔ a = 0 ∨ b = 0 := by
  sorry_using []

/-! ### Subcase: f(0) = 0 -/

@[blueprint
  (statement := /-- If $f(0)=0$, $f\ge0$, and the average of $f$ over $[0,x]$ equals $\sqrt{f(0)f(x)}=0$ for all $x\in s$, then $\int_0^x f(t)\,dt = 0$ for all $x\in s$. -/)
  (proof := /-- From $P(s,f)$, the average is zero, so the integral is zero by `integral_eq_average_mul_x`. -/)
  (proofUses := [integral_eq_average_mul_x])]
lemma integral_zero_when_f0_zero (f : ℝ → ℝ) (x : ℝ) (s : Set ℝ) (hf0 : f 0 = 0) (h_nonneg : 0 ≤ f)
    (h_avg : ∀ x ∈ s, (⨍ t in Ico (0 : ℝ) x, f t) = 0) (hx : x ∈ s) (hx_pos : 0 < x) :
    (∫ t in (0 : ℝ)..x, f t) = 0 := by
  sorry_using [integral_eq_average_mul_x]

@[blueprint
  (statement := /-- If $f\ge0$ and $\int_0^x f(t)\,dt = 0$ for some $x>0$, then $f(t)=0$ for almost every $t\in[0,x]$. Combined with nonnegativity, $f(t)=0$ for all $t\in[0,x]$. -/)
  (proof := /-- Since $f\ge0$, the integral being zero implies $f=0$ a.e. on $[0,x]$, and by nonnegativity, $f(t)=0$ for all $t$ in $[0,x]$. -/)
  (proofUses := [])]
lemma nonneg_integral_zero_implies_zero (f : ℝ → ℝ) (t x : ℝ) (hf_nonneg : 0 ≤ f) (hx_pos : 0 < x)
    (h_int : (∫ t' in (0 : ℝ)..x, f t') = 0) (ht_mem : t ∈ Icc (0 : ℝ) x) : f t = 0 := by
  sorry_using []

@[blueprint
  (statement := /-- If $f$ satisfies $P((0,e),f)$ for some $e>0$ and $f(0)=0$, then $f(x)=0$ for all $x\in(0,e)$. -/)
  (proof := /-- From `integral_zero_when_f0_zero` and `nonneg_integral_zero_implies_zero`. -/)
  (proofUses := [integral_zero_when_f0_zero, nonneg_integral_zero_implies_zero])]
lemma f_zero_on_Ioo_when_f0_zero_and_P (f : ℝ → ℝ) (e : ℝ) (he : 0 < e) (hf0 : f 0 = 0)
    (hP : averageGeometricCondition (Ioo (0 : ℝ) e) f) : ∀ x ∈ Ioo (0 : ℝ) e, f x = 0 := by
  sorry_using [integral_zero_when_f0_zero, nonneg_integral_zero_implies_zero]

@[blueprint
  (statement := /-- If $f$ satisfies $P((0,\infty),f)$ and $f(0)=0$, then $f(x)=0$ for all $x>0$. -/)
  (proof := /-- Same argument but over $(0,\infty)$. -/)
  (proofUses := [integral_zero_when_f0_zero, nonneg_integral_zero_implies_zero])]
lemma f_zero_on_Ioi_when_f0_zero_and_P (f : ℝ → ℝ) (hf0 : f 0 = 0) (hP : averageGeometricCondition (Ioi (0 : ℝ)) f) :
    ∀ x > 0, f x = 0 := by
  sorry_using [integral_zero_when_f0_zero, nonneg_integral_zero_implies_zero]

/-! ### Subcase: f(0) > 0 -/

/-- When f(0) = a > 0, define g(x) = √(f(x)). The functional equation becomes
    avg_{[0,x]} f = √(a) * √(f(x)). -/

@[blueprint
  (statement := /-- If $f(0)=a>0$, $f\ge0$, and $\operatorname{avg}_{[0,x]} f = \sqrt{a\cdot f(x)}$, then defining $g(x)=\sqrt{f(x)}$, we have $\operatorname{avg}_{[0,x]} g^2 = \sqrt{a}\, g(x)$. -/)
  (proof := /-- Since $f = g^2$, substitute into the equation. -/)
  (proofUses := [])]
lemma rewrite_with_sqrt (f : ℝ → ℝ) (a x : ℝ) (ha_pos : 0 < a) (hf0 : f 0 = a) (hf_nonneg : 0 ≤ f)
    (h_eq : (⨍ t in Ico (0 : ℝ) x, f t) = Real.sqrt (a * f x)) (hx_pos : 0 < x) :
    (⨍ t in Ico (0 : ℝ) x, (fun t' => (Real.sqrt (f t')) ^ 2) t) = Real.sqrt a * Real.sqrt (f x) := by
  sorry_using []

/-- The differential equation: if u(x) = avg_{[0,x]} f then u satisfies
    x*u'(x) = u(x)*(u(x)/a - 1) whenever f is differentiable. -/

@[blueprint
  (statement := /-- Let $u(x)=\operatorname{avg}_{[0,x]} f$ and $a=f(0)$. If $f$ satisfies the equation, then $x\,u'(x) = u(x)(u(x)/a - 1)$ wherever $u$ is differentiable. -/)
  (proof := /-- From $F(x)=x\,u(x)$ and $f=F'$, substitute into $u(x)^2 = a\,f(x)$. -/)
  (proofUses := [])]
lemma ode_from_functional_equation (f : ℝ → ℝ) (a x : ℝ) (ha_pos : 0 < a) (hf0 : f 0 = a)
    (h_nonneg : 0 ≤ f) (hP : ∀ x > 0, (⨍ t in Ico (0 : ℝ) x, f t) = Real.sqrt (a * f x))
    (h_diff : DifferentiableOn ℝ f (Ioi 0)) (hx_pos : 0 < x) :
    x * deriv (fun y : ℝ => (⨍ t in Ico (0 : ℝ) y, f t)) x = (⨍ t in Ico (0 : ℝ) x, f t) * ((⨍ t in Ico (0 : ℝ) x, f t) / a - 1) := by
  sorry_using []

/-! ### Identifying the explicit solutions -/

/-- Solution family 1: f(x) = a / (1 - c*x)^2, with a ≥ 0 and c ∈ ℝ. -/
@[blueprint (statement := /-- The function $f_{a,c}(x)=\frac{a}{(1-cx)^2}$ defined for all $x\in\mathbb{R}$ where $1-cx\neq0$. -/)]
noncomputable def sol_family1 (a c : ℝ) : ℝ → ℝ := fun x => a / ((1 : ℝ) - c * x) ^ 2

/-- Solution family 2: truncation of family 1 for c > 0. -/
@[blueprint (statement := /-- For $c>0$, the truncated function $f_{a,c}(x)=\frac{a}{(1-cx)^2}$ for $x<1/c$, and $0$ for $x\ge 1/c$. -/)]
noncomputable def sol_family2 (a c : ℝ) : ℝ → ℝ := fun x => if x < (1 : ℝ) / c then a / ((1 : ℝ) - c * x) ^ 2 else 0

/-- Verify that family 1 satisfies the functional equation on (0,∞) when c ≤ 0,
    or on (0, 1/c) when c > 0. -/
@[blueprint
  (statement := /-- For any $a\ge0$, the function $f_{a,c}(x)=a/(1-cx)^2$ satisfies
    $\operatorname{avg}_{[0,x]} f_{a,c} = \sqrt{f_{a,c}(0)\cdot f_{a,c}(x)}$ for all $x$ in its domain. -/)
  (proof := /-- Direct computation: compute the integral $\int_0^x a/(1-ct)^2 dt = ax/(1-cx)$, then the average is $a/(1-cx)$, and $\sqrt{f(0)f(x)} = \sqrt{a\cdot a/(1-cx)^2} = a/|1-cx|$. For $cx<1$ we have $1-cx>0$, so $a/(1-cx) = a/|1-cx|$. -/)
  (proofUses := [])]
lemma family1_satisfies_P (a c : ℝ) (ha_nonneg : 0 ≤ a) (x : ℝ) (hx_pos : 0 < x)
    (h_domain : 1 - c * x ≠ 0) : averageGeometricCondition (Ioi (0 : ℝ)) (sol_family1 a c) := by
  sorry_using []

/-- Verify that family 2 satisfies the functional equation. -/
@[blueprint
  (statement := /-- For $a\ge0$, $c>0$, the truncated function satisfies the condition on $(0,1/c)$. -/)
  (proof := /-- For $x<1/c$, the function equals family 1, so the same computation works. For $x\ge 1/c$, the average over $[0,x]$ is not defined in the sense of the condition (since $x$ is outside the domain). Actually family 2 is defined for all $\mathbb{R}$ but only meant to satisfy the condition on $(0,1/c)$. -/)
  (proofUses := [family1_satisfies_P])]
lemma family2_satisfies_P_on_Ioo (a c : ℝ) (ha_nonneg : 0 ≤ a) (hc_pos : 0 < c) :
    averageGeometricCondition (Ioo (0 : ℝ) ((1 : ℝ) / c)) (sol_family2 a c) := by
  sorry_using [family1_satisfies_P]

/-- Verify that family 3 (zero on positive reals) satisfies the condition. -/
@[blueprint
  (statement := /-- Any nonnegative function with $f(x)=0$ for all $x>0$ satisfies the condition (since both sides are zero). -/)
  (proof := /-- Then $f(0)$ may be arbitrary but $\sqrt{f(0)\cdot0}=0$. The average of zero over $[0,x]$ is zero. -/)
  (proofUses := [])]
lemma family3_satisfies_P (f : ℝ → ℝ) (hf_nonneg : 0 ≤ f) (hf_zero : ∀ x > 0, f x = 0) :
    averageGeometricCondition (Ioi (0 : ℝ)) f := by
  sorry_using []

/-- Verify that family 4 (f(0)=0, nonnegative, average zero on a neighborhood) satisfies the condition. -/
@[blueprint
  (statement := /-- If $f(0)=0$, $f\ge0$, and $\operatorname{avg}_{[0,x]}f =0$ for all $x\in(0,e)$, then the condition holds on $(0,e)$. -/)
  (proof := /-- Since $f(0)=0$, $\sqrt{0\cdot f(x)}=0$. And the average is zero by hypothesis. -/)
  (proofUses := [])]
lemma family4_satisfies_P (f : ℝ → ℝ) (e : ℝ) (he : 0 < e) (hf0 : f 0 = 0) (hf_nonneg : 0 ≤ f)
    (h_avg_zero : ∀ x ∈ Ioo (0 : ℝ) e, (⨍ t in Ico (0 : ℝ) x, f t) = 0) : averageGeometricCondition (Ioo (0 : ℝ) e) f := by
  sorry_using []

/-! ## Forward direction: every solution belongs to one of the four families -/

/-- If f satisfies P on (0,∞) and f(0) > 0, then f is of the form a/(1-cx)²
    (family 1) for some c ∈ ℝ, a = f(0). -/
@[blueprint
  (statement := /-- If $P((0,\infty),f)$ and $f(0)=a>0$, then $f$ is of the form $f(x)=a/(1-cx)^2$ for some $c\in\mathbb{R}$. -/)
  (proof := /-- Solve the ODE $x\,u'(x)=u(x)(u(x)/a-1)$ with $u(0+)=a$. The solutions are $u(x)=a/(1-cx)$, giving $f(x)=u(x)^2/a = a/(1-cx)^2$. -/)
  (proofUses := [ode_from_functional_equation])]
lemma family1_from_P_on_Ioi (f : ℝ → ℝ) (a : ℝ) (ha_pos : 0 < a) (hf0 : f 0 = a)
    (h_nonneg : 0 ≤ f) (hP : averageGeometricCondition (Ioi (0 : ℝ)) f) (h_diff : DifferentiableOn ℝ f (Ioi 0)) :
    ∃ c : ℝ, f = sol_family1 a c := by
  sorry_using [ode_from_functional_equation]

/-- If f satisfies P on (0,e) for some e > 0 and f(0) > 0, then either f is of the form
    a/(1-cx)² on (0,e) (family 1), or the truncated version (family 2) if c > 0 and e > 1/c. -/
@[blueprint
  (statement := /-- If $P((0,e),f)$ and $f(0)=a>0$, then either $f$ equals family 1 on $(0,e)$, or $e>1/c$ and $f$ equals family 2 on $(0,e)$. -/)
  (proof := /-- The ODE solution is $u(x)=a/(1-cx)$ as long as $1-cx>0$. If $c\le0$, this holds for all $x>0$. If $c>0$, it holds for $x<1/c$, and for $x\ge 1/c$ the average would need to be $0$, but $f(0)=a>0$ makes this impossible unless we truncate. -/)
  (proofUses := [ode_from_functional_equation, family1_satisfies_P])]
lemma family1_or_family2_from_P_on_Ioo (f : ℝ → ℝ) (a : ℝ) (ha_pos : 0 < a) (hf0 : f 0 = a)
    (h_nonneg : 0 ≤ f) (e : ℝ) (he : 0 < e) (hP : averageGeometricCondition (Ioo (0 : ℝ) e) f)
    (h_diff : DifferentiableOn ℝ f (Ioo 0 e)) :
    (∃ c : ℝ, f = sol_family1 a c) ∨ (∃ c : ℝ, 0 < c ∧ (1 : ℝ) / c ≤ e ∧ (∀ x ∈ Ioo (0 : ℝ) e, f x = sol_family2 a c x)) := by
  sorry_using [ode_from_functional_equation, family1_satisfies_P]

/-! ## Main theorem -/

@[blueprint
  (statement := /-- The solution set $S$ (putnam_1962_a2_solution) is exactly the set of functions $f$ such that either $P((0,\infty),f)$ or there exists $e>0$ with $P((0,e),f)$. Moreover, if $P((0,\infty),f)$ then $f$ agrees with some $g\in S$ on $[0,\infty)$, and if $P((0,e),f)$ for all $e>0$ then $f$ agrees with some $g\in S$ on $[0,e)$. -/)
  (proof := /-- 
    **Forward direction**: Given f such that P holds on (0,∞) or on (0,e):
      - If f(0) = 0, then family 3 or 4 applies (depending on domain size).
      - If f(0) > 0, use the ODE analysis to identify family 1 or 2.
    **Backward direction**: Every g ∈ S satisfies P on the appropriate domain, as shown by the family lemmas.
  -/)
  (proofUses := [
    f_zero_on_Ioi_when_f0_zero_and_P, f_zero_on_Ioo_when_f0_zero_and_P,
    family1_from_P_on_Ioi, family1_or_family2_from_P_on_Ioo,
    family1_satisfies_P, family2_satisfies_P_on_Ioo,
    family3_satisfies_P, family4_satisfies_P
  ])]
theorem putnam_1962_a2
    (P : Set ℝ → (ℝ → ℝ) → Prop)
    (P_def : ∀ s f, P s f ↔ 0 ≤ f ∧ ∀ x ∈ s, (⨍ t in Ico 0 x, f t) = Real.sqrt (f 0 * f x)) :
    (∀ f,
      (P (Ioi 0) f → ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ici 0)) ∧
      (∀ e > 0, P (Ioo 0 e) f → ∃ g ∈ putnam_1962_a2_solution, EqOn f g (Ico 0 e))) ∧
    ∀ f ∈ putnam_1962_a2_solution, P (Ioi 0) f ∨ (∃ e > 0, P (Ioo 0 e) f) := by
  sorry_using [
    f_zero_on_Ioi_when_f0_zero_and_P, f_zero_on_Ioo_when_f0_zero_and_P,
    family1_from_P_on_Ioi, family1_or_family2_from_P_on_Ioo,
    family1_satisfies_P, family2_satisfies_P_on_Ioo,
    family3_satisfies_P, family4_satisfies_P
  ]
