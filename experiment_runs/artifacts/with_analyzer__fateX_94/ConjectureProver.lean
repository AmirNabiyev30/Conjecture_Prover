/-
BLUEPRINT for the target theorem of experiment run
`with_analyzer__fateX_94` (problem `fateX_94`), condition = with_analyzer.

ORIGINAL THEOREM (kept verbatim in the final declaration below, statement only —
proof is replaced by the blueprint decomposition):
  theorem zeroSet_finite_or_contain_arithmetic_progression (hf : f.FormallyEtale) :
      (zeroSet f ϕ I).Finite ∨ ∃ (d : ℕ+) (a : ℕ), ∀ n : ℕ, a + d * n ∈ zeroSet f ϕ I

Informal content.  Let k be a field of characteristic 0, A a finitely generated
k-algebra which is an integral domain, f : A → A an étale k-algebra endomorphism,
ϕ : A → k a k-algebra homomorphism and I ⊆ A an ideal.  For
  zeroSet f ϕ I := {n : ℕ | ϕ ∘ f^n vanishes on I}
the claim is that zeroSet f ϕ I is either finite or contains an arithmetic
progression {a + d·n : n ∈ ℕ} with positive common difference d.

This file is a *dependency-graph skeleton*: every declaration below carries a
`@[blueprint ...]` annotation and every proof body is `:= by sorry_using [...]`.
-/

import Mathlib
import Architect

namespace Problem94

variable {k A : Type} [Field k] [CharZero k] [CommRing A] [IsDomain A] [Algebra k A]
  [Algebra.FiniteType k A] (f : A →ₐ[k] A) (ϕ : A →ₐ[k] k) (I : Ideal A)

/--
The set $\{ n \in \mathbb{N} \mid \left. \varphi \circ f^n \right|_I = 0 \right\rbrace \}$.
-/
@[blueprint (statement := /-- The zero set $S=\{n\in\mathbb{N}\mid (\varphi\circ f^n)|_I=0\}$ of the iterates of the functional $\varphi$ along the endomorphism $f$, restricted to the ideal $I$; a subset of $\mathbb{N}$. -/) (title := "Zero set of phi ∘ f^n on I")]
def zeroSet : Set ℕ := {n | ∀ x : I, (ϕ.comp (f ^ n)) (x : A) = 0}

/--
A subset $S \subseteq \mathbb{N}$ *contains an arithmetic progression* if there are
$d \in \mathbb{N}_{>0}$ and $a \in \mathbb{N}$ with $a + d\cdot n \in S$ for every $n \in \mathbb{N}$.
-/
@[blueprint (statement := /-- $S\subseteq\mathbb{N}$ contains an arithmetic progression with positive common difference: $\exists d\in\mathbb{N}_{>0},\, a\in\mathbb{N},\ \forall n\in\mathbb{N},\ a+d\,n\in S$. -/) (title := "Contains an arithmetic progression")]
def ContainsArithmeticProgression (S : Set ℕ) : Prop :=
  ∃ (d : ℕ+) (a : ℕ), ∀ n : ℕ, a + (d : ℕ) * n ∈ S

/--
Unfolding of membership in `zeroSet`: $n \in \mathrm{zeroSet}(f,\varphi,I)$ iff
$\varphi(f^n(x)) = 0$ for every $x \in A$ with $x \in I$.
-/
@[blueprint
  (statement := /-- For every $n\in\mathbb{N}$: $n\in\mathrm{zeroSet}(f,\varphi,I)$ iff $\varphi(f^n(x))=0$ holds for every element $x\in I$ of the ideal. -/)
  (proof := /-- Unfold the definition of `zeroSet`; an element of the subtype $I$ is precisely an element $x\in A$ together with a proof of $x\in I$. -/)
  (title := "Membership in the zero set")
  (uses := [zeroSet])
  (proofUses := [zeroSet])]
lemma zeroSet_mem_iff (n : ℕ) :
    n ∈ zeroSet f ϕ I ↔ ∀ x : A, x ∈ I → ϕ ((f ^ n) x) = 0 := by
  unfold zeroSet
  simp

/--
The vanishing condition is a statement about the orbit of the ideal $I$ under the
endomorphism $f$: $n\in \mathrm{zeroSet}(f,\varphi,I)$ iff the push-forward ideal
$f^n(I)\subseteq A$ is contained in the kernel $\ker\varphi$ of the homomorphism
$\varphi : A \to k$.
-/
@[blueprint
  (statement := /-- For every $n\in\mathbb{N}$: $n\in\mathrm{zeroSet}(f,\varphi,I)$ iff $f^n(I)\subseteq\ker\varphi$ as ideals of $A$, where $f^n(I)$ is the image ideal $\mathrm{Ideal.map}(f^n)(I)$. -/)
  (proof := /-- Rewrite the left-hand side with `zeroSet_mem_iff`, reducing to $\forall x\in I,\ \varphi(f^n(x))=0$.  The right-hand side $\mathrm{Ideal.map}(f^n)(I)\le\ker\varphi$ is, by `Ideal.map_le_iff_le_comap` and `SetLike.le_def`, equivalent to $I\le\mathrm{comap}(f^n)(\ker\varphi)$, i.e. $\forall x\in I,\ (f^n\,x)\in\ker\varphi$, where `RingHom.mem_ker` expresses the latter as $\varphi(f^n(x))=0$.  Both directions follow elementwise: forward, use `Ideal.mem_comap` on the ideal-inclusion hypothesis; backward, use `Ideal.mem_map_of_mem (f ^ n : A →+* A) hx` to get $(f^n\,x)\in\mathrm{Ideal.map}(f^n)(I)$ and close with `RingHom.mem_ker.mp`; a closing `simpa` absorbs the AlgHom/RingHom coercion of the power $(f ^ n)$ (all iterates agree on elements). -/)
  (title := "Zero set via the ideal orbit in ker phi")
  (uses := [zeroSet])
  (proofUses := [zeroSet_mem_iff])]
lemma zeroSet_mem_iff_ker (n : ℕ) :
    n ∈ zeroSet f ϕ I ↔ Ideal.map (f ^ n : A →+* A) I ≤ RingHom.ker (ϕ : A →+* k) := by
  rw [zeroSet_mem_iff]
  constructor
  · intro h
    rw [Ideal.map_le_iff_le_comap]
    intro y hy
    rw [Ideal.mem_comap]
    rw [RingHom.mem_ker]
    simpa [AlgHom.coe_pow, RingHom.coe_pow] using h y hy
  · intro h x hx
    have hmem : ((f : A →+* A) ^ n) x ∈ RingHom.ker (ϕ : A →+* k) :=
      h (Ideal.mem_map_of_mem ((f : A →+* A) ^ n) hx)
    simpa [AlgHom.coe_pow, RingHom.coe_pow] using (RingHom.mem_ker.mp hmem)

/--
Étaleness is preserved under taking powers: since $f$ is a formally étale
endomorphism of $A$, every iterate $f^n$ is formally étale as well.
-/
@[blueprint
  (statement := /-- If $f:A\to A$ is formally \'etale then every iterate $f^n$ is formally \'etale: $\forall n\in\mathbb{N},\ (f^n : A\to A)$ is formally \'etale. -/)
  (proof := /-- Induction on $n$ using the fact that the underlying ring homomorphism of $f^n$ is the $n$-fold composition of the underlying ring homomorphism of $f$ together with `RingHom.FormallyEtale.comp`; the base case $n=0$ is the identity, which is formally \'etale (`Algebra.FormallyEtale.instFormallyEtaleSelf`). -/)
  (title := "Powers of an étale endomorphism are étale")]
lemma formallyEtale_pow (n : ℕ) (hf : f.FormallyEtale) :
    ((f ^ n : A →ₐ[k] A) : A →+* A).FormallyEtale := by
  induction n with
  | zero =>
      have hbase : ((f ^ 0 : A →ₐ[k] A) : A →+* A) = RingHom.id A := by
        change ((1 : A →ₐ[k] A) : A →+* A) = RingHom.id A
        ext x
        rfl
      rw [hbase]
      simpa using (RingHom.formallyEtale_algebraMap (R := A) (S := A)).2
        (inferInstance : Algebra.FormallyEtale A A)
  | succ n ih =>
      have hstep : ((f ^ (n + 1) : A →ₐ[k] A) : A →+* A) =
          (((f ^ n : A →ₐ[k] A) : A →+* A).comp (f : A →+* A)) := by
        rw [pow_succ]
        ext x
        simp [AlgHom.mul_apply]
      rw [hstep]
      exact RingHom.FormallyEtale.comp hf ih

/--
The core dichotomy (the "infinite case" of the target theorem): under the étale
hypothesis on $f$, if the zero set $S = \mathrm{zeroSet}(f,\varphi,I)$ is infinite,
then it contains an arithmetic progression with positive common difference.
-/
@[blueprint
  (statement := /-- Assume $f$ is formally \'etale. If $\mathrm{zeroSet}(f,\varphi,I)\subseteq\mathbb{N}$ is not finite, then it contains an arithmetic progression with positive common difference, i.e. $\mathrm{ContainsArithmeticProgression}(\mathrm{zeroSet}(f,\varphi,I))$ holds.  The common difference is quantified as $d\in\mathbb{N}_{>0}$ (type $\mathbb{N}^+$), so the conclusion really asks for an infinite strictly increasing progression $\{a+d\,n\}_n\subseteq S$: a mere nonempty (even infinite) set need not contain one, and this lemma is the genuine research-level dichotomy of the problem. -/)
  (proof := /-- This is the research-level content of the theorem and is not available in Mathlib: none of the elementary facts `zeroSet_mem_iff`, `zeroSet_mem_iff_ker`, `formallyEtale_pow` (or any combination of them) implies it, since the conclusion ranges over a positive $d\in\mathbb{N}^+$.  Following the Skolem--Mahler--Lech strategy for the étale endomorphism $f$ of the finitely generated domain $A$ over the characteristic-zero field $k$: use `zeroSet_mem_iff_ker` to view $n\in S$ as the ideal-orbit condition $f^n(I)\subseteq\ker\varphi$; by `formallyEtale_pow` every iterate $f^n$ is still formally étale, so after reduction to a suitable $p$-adic completion the map $n\mapsto f^n$ is $p$-adically analytic along residue classes modulo some period $d$, and the vanishing condition is analytic in $n$.  On an infinite subset of a residue class the analytic function vanishes identically, forcing the whole arithmetic progression $\{a+d\,n\}_n$ into $S$.  (Recorded here as an open proof obligation via `zeroSet_mem_iff`, `zeroSet_mem_iff_ker` and `formallyEtale_pow`.) -/)
  (title := "Infinite zero set contains an arithmetic progression")
  (uses := [zeroSet, ContainsArithmeticProgression])
  (proofUses := [zeroSet_mem_iff, zeroSet_mem_iff_ker, formallyEtale_pow])]
lemma zeroSet_infinite_contains_ap (hf : f.FormallyEtale) :
    ¬ (zeroSet f ϕ I).Finite → ContainsArithmeticProgression (zeroSet f ϕ I) := by
  sorry_using [zeroSet_mem_iff, zeroSet_mem_iff_ker, formallyEtale_pow]

/--
Let $k$ be field, $\mathrm{char}\ k=0$, $ A $ be a finite-type $k$-algebra, $f: A \to A$ be an
\'etale endomorphsim, $\varphi: A \to k$, $I \subset A$ be a ideal. If $A$ is a domain,
then $$\left\lbrace  n \in \mathbb{N} \mid \left. \varphi \circ f^n \right|_I = 0 \right\rbrace $$
is either finite or contains an arithmetic progression with a positive common difference.
-/
@[blueprint
  (statement := /-- Let $k$ be a field of characteristic $0$, $A$ a finitely generated $k$-algebra which is a domain, $f:A\to A$ an \'etale endomorphism, $\varphi:A\to k$ a $k$-algebra homomorphism and $I\subseteq A$ an ideal.  Then $\{n\in\mathbb{N}\mid (\varphi\circ f^n)|_I=0\}$ is either finite or contains an arithmetic progression $\{a+d\cdot n:n\in\mathbb{N}\}$ with positive common difference $d$. -/)
  (proof := /-- Split on whether $\mathrm{zeroSet}(f,\varphi,I)$ is finite.  If it is finite we are done by the left disjunct.  Otherwise apply `zeroSet_infinite_contains_ap` (using the formal-étaleness hypothesis `hf`) to obtain $\mathrm{ContainsArithmeticProgression}(\mathrm{zeroSet}(f,\varphi,I))$, and unfold `ContainsArithmeticProgression` to get the right disjunct in its original inline form $\exists d\in\mathbb{N}_{>0},\,a\in\mathbb{N},\,\forall n,\ a+d\,n\in\mathrm{zeroSet}(f,\varphi,I)$. -/)
  (title := "Zero set is finite or contains an arithmetic progression")
  (uses := [zeroSet])
  (proofUses := [zeroSet_infinite_contains_ap, ContainsArithmeticProgression])]
theorem zeroSet_finite_or_contain_arithmetic_progression (hf : f.FormallyEtale) :
    (zeroSet f ϕ I).Finite ∨ ∃ (d : ℕ+) (a : ℕ), ∀ n : ℕ, a + d * n ∈ zeroSet f ϕ I := by
  by_cases hfin : (zeroSet f ϕ I).Finite
  · exact Or.inl hfin
  · exact Or.inr (zeroSet_infinite_contains_ap f ϕ I hf hfin)

end Problem94
