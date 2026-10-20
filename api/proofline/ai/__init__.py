"""The Evidence Investigator (docs/PLAN.md Step 10). A Pydantic AI agent
that reads and proposes -- never writes, approves, closes or signs
anything. That limit comes from the `ai_assistant` role and the action
service (`proofline.security.permissions`, `proofline.actions.service`),
never from a prompt (CLAUDE.md "AI, when we get there").
"""
