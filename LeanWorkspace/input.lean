import Mathlib
import Architect

/- DO NOT EDIT ABOVE OR ON THIS LINE, paste your code below -/

@[blueprint
(statement := /-- transitive property of equality: if a = b and b = c then a = c for any type α and elements a,b,c : α -/)]
theorem trans_eq_of_eq_of_eq {α} {a b c : α} (h1 : a = b) (h2 : b = c) : a = c := by
  sorry_using []
