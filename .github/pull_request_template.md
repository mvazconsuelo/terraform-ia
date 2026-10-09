## What changes and why

<!-- One or two lines. The pipeline comments the plan, the cost and the verdict. -->

## Kind of change

- [ ] Tooling, rules, docs or CI (nothing to deploy)
- [ ] A module (nothing deploys until a root uses it)
- [ ] Infrastructure values or a root (the owner runs `plan` and then `apply` by hand)

## Checklist

- [ ] A module or a rule has its test (`tests/terraform/` or `tests/reviewer/`)
- [ ] Documentation changed in English and in Spanish
- [ ] No key, token or state file in the change
- [ ] Module calls pass values as they are (no `for`, `try` or `merge`)
