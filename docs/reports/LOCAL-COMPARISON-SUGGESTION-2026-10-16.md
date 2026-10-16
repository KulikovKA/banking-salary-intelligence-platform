# Single comparison suggestion

The live welcome screen now has one suggestion, `Сравнить 4 банка`.
It submits an explicit comparison of Сбер, ВТБ, Альфа-Банк and Кубань Кредит.
The other three live suggestions were removed.

Validation: frontend lint, typecheck and production build passed; the existing
offline browser suite passed all 4 scenarios. The comparison scenario checks
that exactly one suggestion remains and verifies its submitted question.
No backend changes or real provider calls were needed for this task.
