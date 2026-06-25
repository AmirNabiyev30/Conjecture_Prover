import Mathlib
import Architect

open Set
open scoped Topology

@[blueprint (statement := /-- The closed interval `[a,b]` in a preorder, viewed as the set of points `x` with `a ≤ x ≤ b`. -/)]
def closed_interval (a b : ℝ) : Set ℝ := Set.Icc a b

@[blueprint (statement := /-- The open interval `(a,b)` in a preorder, viewed as the set of points `x` with `a < x < b`. -/)]
def open_interval (a b : ℝ) : Set ℝ := Set.Ioo a b

@[blueprint (statement := /-- A point `x` is critical for a real function `f` when the derivative of `f` at `x` is zero. -/)]
def is_critical_point (f : ℝ → ℝ) (x : ℝ) : Prop := HasDerivAt f 0 x

@[blueprint
(statement := /-- For every real numbers `a b` and every function `f : ℝ → ℝ`, if `a ≤ b` and `f` is continuous on the closed interval `[a,b]`, then there exists a point `x_min` in `[a,b]` such that `f x_min ≤ f y` for every `y` in `[a,b]`, and there exists a point `x_max` in `[a,b]` such that `f y ≤ f x_max` for every `y` in `[a,b]`. -/)
(proof := /-- The closed interval `closed_interval a b` is compact in `ℝ`. By continuity of `f` on `closed_interval a b`, the image of this interval under `f` is compact, so `f` attains both a minimum and a maximum on the interval. This is exactly the extreme value theorem on a compact set. -/)]
lemma continuous_on_closed_interval_has_min_and_max
    (a b : ℝ) (f : ℝ → ℝ)
    (hab : a ≤ b) (hcont : Continuous fun x => f x) :
    ∃ x_min ∈ closed_interval a b, (∀ y ∈ closed_interval a b, f x_min ≤ f y) ∧
    ∃ x_max ∈ closed_interval a b, ∀ y ∈ closed_interval a b, f y ≤ f x_max := by
  have hmax : ∃ x_max ∈ closed_interval a b, ∀ y ∈ closed_interval a b, f y ≤ f x_max := by
    let s : Set ℝ := f '' closed_interval a b
    have hscompact : IsCompact s := by
      simpa [s, closed_interval] using (isCompact_Icc.image hcont)
    have hsnonempty : s.Nonempty := by
      refine ⟨f a, ?_⟩
      exact ⟨a, by simp [closed_interval, hab], rfl⟩
    rcases hscompact.exists_isGreatest hsnonempty with ⟨M, hM⟩
    rcases hM.1 with ⟨x, hx, rfl⟩
    refine ⟨x, hx, ?_⟩
    intro y hy
    exact hM.2 ⟨y, hy, rfl⟩
  have hmin : ∃ x_min ∈ closed_interval a b, ∀ y ∈ closed_interval a b, f x_min ≤ f y := by
    let s : Set ℝ := f '' closed_interval a b
    have hscompact : IsCompact s := by
      simpa [s, closed_interval] using (isCompact_Icc.image hcont)
    have hsnonempty : s.Nonempty := by
      refine ⟨f a, ?_⟩
      exact ⟨a, by simp [closed_interval, hab], rfl⟩
    rcases hscompact.exists_isLeast hsnonempty with ⟨m, hm⟩
    rcases hm.1 with ⟨x, hx, rfl⟩
    refine ⟨x, hx, ?_⟩
    intro y hy
    exact hm.2 ⟨y, hy, rfl⟩
  rcases hmin with ⟨x_min, hx_min, hx_min_le⟩
  exact ⟨x_min, hx_min, hx_min_le, hmax⟩

@[blueprint
(statement := /-- For every real numbers `a b x` and every function `f : ℝ → ℝ`, if `x ∈ (a,b)`, `f` has a derivative at `x`, and `x` is a local maximum of `f`, then `x` is a critical point of `f`. -/)
(proof := /-- Since `x ∈ open_interval a b`, the point `x` is interior to the domain. If `f` has a derivative at `x` and `x` is a local maximum, Fermat's theorem implies that the derivative of `f` at `x` is zero. By the definition `is_critical_point`, this means `x` is a critical point. -/)]
lemma local_max_in_open_interval_is_critical
    (a b x : ℝ) (f : ℝ → ℝ)
    (_hx : x ∈ open_interval a b)
    (hdiff : DifferentiableAt ℝ f x)
    (hmax : IsLocalMax f x) :
    is_critical_point f x := by
  rw [is_critical_point]
  have h0 : deriv f x = 0 := hmax.deriv_eq_zero
  have h1 : HasDerivAt f (deriv f x) x := hdiff.hasDerivAt
  rwa [h0] at h1

@[blueprint
(statement := /-- For every real numbers `a b x` and every function `f : ℝ → ℝ`, if `x ∈ (a,b)`, `f` has a derivative at `x`, and `x` is a local minimum of `f`, then `x` is a critical point of `f`. -/)
(proof := /-- Since `x ∈ open_interval a b`, the point `x` is interior to the domain. If `f` has a derivative at `x` and `x` is a local minimum, Fermat's theorem implies that the derivative of `f` at `x` is zero. By the definition `is_critical_point`, this means `x` is a critical point. -/)]
lemma local_min_in_open_interval_is_critical
    (a b x : ℝ) (f : ℝ → ℝ)
    (_hx : x ∈ open_interval a b)
    (hdiff : DifferentiableAt ℝ f x)
    (hmin : IsLocalMin f x) :
    is_critical_point f x := by
  rw [is_critical_point]
  have h0 : deriv f x = 0 := hmin.deriv_eq_zero
  have h1 : HasDerivAt f (deriv f x) x := hdiff.hasDerivAt
  rwa [h0] at h1

@[blueprint
(statement := /-- For every real numbers `a b x` and every function `f : ℝ → ℝ`, if `x ∈ (a,b)`, `f` has a derivative at `x`, and `x` is a local extremum of `f`, then `x` is a critical point of `f`. Here a local extremum means either a local maximum or a local minimum. -/)
(proof := /-- A local extremum is by definition a disjunction: either `IsLocalMax f x` or `IsLocalMin f x`. In the first case, apply `local_max_in_open_interval_is_critical`; in the second case, apply `local_min_in_open_interval_is_critical`. Both cases conclude `is_critical_point f x`. -/)]
lemma local_extremum_in_open_interval_is_critical
    (a b x : ℝ) (f : ℝ → ℝ)
    (hx : x ∈ open_interval a b)
    (hdiff : DifferentiableAt ℝ f x)
    (hext : IsLocalMax f x ∨ IsLocalMin f x) :
    is_critical_point f x := by
  rcases hext with hmax | hmin
  · exact local_max_in_open_interval_is_critical a b x f hx hdiff hmax
  · exact local_min_in_open_interval_is_critical a b x f hx hdiff hmin

@[blueprint
(statement := /-- For every real numbers `a b` and every function `f : ℝ → ℝ`, assume `a ≤ b`, assume `f` is continuous on `[a,b]`, and assume moreover that whenever `x ∈ (a,b)` is a local extremum of `f` and `f` is differentiable at `x`, then `x` is a critical point. Under these assumptions, `f` attains both a maximum and a minimum on `[a,b]`, and every differentiable local extremum in `(a,b)` occurs at a critical point. -/)
(proof := /-- The existence of a minimum point and a maximum point on `closed_interval a b` follows from `continuous_on_closed_interval_has_min_and_max`. For the second assertion, let `x` be a point in `open_interval a b` where `f` has a local extremum and is differentiable. Then `local_extremum_in_open_interval_is_critical` yields that `x` is a critical point. Combining these two independent conclusions proves the theorem. -/)]
theorem extreme_value_and_critical_point
    (a b : ℝ) (f : ℝ → ℝ)
    (hab : a ≤ b) (hcont : Continuous fun x => f x) :
    (∃ x_min ∈ closed_interval a b, (∀ y ∈ closed_interval a b, f x_min ≤ f y)) ∧
    (∃ x_max ∈ closed_interval a b, (∀ y ∈ closed_interval a b, f y ≤ f x_max)) ∧
    (∀ x : ℝ, x ∈ open_interval a b → DifferentiableAt ℝ f x →
      (IsLocalMax f x ∨ IsLocalMin f x) → is_critical_point f x) := by
  rcases continuous_on_closed_interval_has_min_and_max a b f hab hcont with
    ⟨x_min, hx_min, hxmin, x_max, hx_max, hxmax⟩
  refine ⟨⟨x_min, hx_min, hxmin⟩, ⟨⟨x_max, hx_max, hxmax⟩, ?_⟩⟩
  intro x hx hdiff hext
  exact local_extremum_in_open_interval_is_critical a b x f hx hdiff hext
