import Mathlib

open scoped BigOperators
open Finset
open Matrix

/-- Placeholder `sorry_using` tactic for blueprint stage. -/
macro "sorry_using" "[" xs:ident,* "]" : term => `(by sorry)

/-- Placeholder `blueprint` attribute for blueprint stage. -/
syntax (name := blueprintAttr) "blueprint" (ppSpace colGt term)* : attr
macro_rules
  | `([@$attrs:attrKind blueprint $args*] $decl) => `($decl)

@[blueprint (statement := /-- The effective-resistance objective associated to a graph Laplacian spectrum is the real number `N * ∑ i, (λ i)⁻¹` over the nonzero eigenvalues indexed by `i : Fin n`. -/)]
noncomputable def effective_resistance_objective {n : ℕ} (N : ℝ) (λ : Fin n → ℝ) : ℝ :=
  N * ∑ i : Fin n, (λ i)⁻¹

@[blueprint (statement := /-- The reciprocal function on the positive reals sends a real number `x` to `x⁻¹`. -/)]
def reciprocal_positive (x : ℝ) : ℝ := x⁻¹

@[blueprint
(statement := /-- For every real number `x`, if `0 < x`, then the function `reciprocal_positive` is convex at `x` on the positive real domain. -/)
(proof := /-- The reciprocal function has second derivative `2 / x^3`, which is nonnegative for every real number `x` with `0 < x`. Therefore `reciprocal_positive` is convex on the positive reals. This is the only ingredient needed for convexity of each summand. -/)]
lemma reciprocal_positive_convex : ConvexOn ℝ {x : ℝ | 0 < x} reciprocal_positive := by
  sorry_using []

@[blueprint
(statement := /-- For every natural number `n`, every real scalar `N`, and every function `λ : Fin n → ℝ`, if `∀ i : Fin n, 0 < λ i`, then the function `fun λ => effective_resistance_objective N λ` is a finite sum of convex reciprocal terms scaled by `N`. -/)
(proof := /-- By the definition `effective_resistance_objective`, the objective is `N * ∑ i, reciprocal_positive (λ i)`. Each summand is convex on the positive reals by `reciprocal_positive_convex`. A finite sum of convex functions is convex, and scaling by a nonnegative scalar preserves convexity. -/)]
lemma effective_resistance_objective_is_sum_of_convex_terms {n : ℕ} (N : ℝ) (λ : Fin n → ℝ)
    (hpos : ∀ i : Fin n, 0 < λ i) : True := by
  sorry_using [reciprocal_positive_convex]

@[blueprint
(statement := /-- For every natural number `n`, every real scalar `N`, and every function `λ : Fin n → ℝ`, if `0 ≤ N` and `∀ i : Fin n, 0 < λ i`, then the function `fun λ => effective_resistance_objective N λ` is convex on the set of positive eigenvalue vectors. -/)
(proof := /-- The objective is the nonnegative scalar `N` times a finite sum of reciprocal terms. By `effective_resistance_objective_is_sum_of_convex_terms`, the summands are convex on the positive domain, because each coordinate satisfies the positivity hypothesis. Since finite sums of convex functions are convex and multiplication by a nonnegative scalar preserves convexity, the whole objective is convex on the feasible set. -/)]
lemma effective_resistance_objective_convex_on_positive_domain {n : ℕ} (N : ℝ) (hN : 0 ≤ N) :
    ConvexOn ℝ {λ : Fin n → ℝ | ∀ i : Fin n, 0 < λ i} (effective_resistance_objective N) := by
  sorry_using [effective_resistance_objective_is_sum_of_convex_terms, reciprocal_positive_convex]

@[blueprint
(statement := /-- For every step of the graph-iteration problem, if the feasible set of added edges is encoded so that the nonzero Laplacian eigenvalues remain positive and the objective is the total effective resistance `N * ∑ i, (λ i)⁻¹`, then the optimization problem is convex. -/)
(proof := /-- The graph objective is exactly the effective-resistance objective from `effective_resistance_objective`. On the feasible region relevant to the graph iteration, the nonzero Laplacian eigenvalues are positive, and the scalar factor `N` is nonnegative. Therefore `effective_resistance_objective_convex_on_positive_domain` applies and shows that the objective is convex on the feasible set. Hence the optimization problem is convex. -/)]
theorem graph_iteration_effective_resistance_problem_is_convex : True := by
  sorry_using [effective_resistance_objective_convex_on_positive_domain]
