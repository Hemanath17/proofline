# How AI was used

## Tools
- Claude (chat): design partner for the core model, the blueprint diagrams, the build spec and the scenario simulations; also ran the packet queries behind every number in `docs/ERRORS.md`
- ChatGPT: second opinion that criticized the design; several of its points were adopted
- Claude Code: builds the app from `docs/PLAN.md`, with project rules, hooks, skills and subagents in `.claude/`

## What I decided or corrected
- Required discussion before any design or file; rejected an early switch of the front-end framework
- Pushed for an authentic CPA workflow and judged each idea from the user's side
- Rejected a materiality threshold: any change to an approved value counts
- Challenged area-wide reopening, which led to delta approval
- Challenged carrying approvals over when only the evidence changed, which led to the relied-on-field rule
- Chose Pydantic AI for the investigator and asked for evaluation with DeepEval

## AI mistakes caught
- Wrong roles for staff (corrected against the packet)
- Overstated errors before they were checked
- An AI explanation test showed valid citations alongside unsupported claims in 4 of 10 cases, which is why a person checks meaning

## Measured result
- AI explanations of findings helped in 3 of 10 real cases; not built. Evidence: the ten-case test in the design notes
