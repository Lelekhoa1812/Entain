# Release and Handover Prompt

```text
Review the repo from the perspective of a hiring manager or teammate who needs confidence that this can be shipped and maintained.

Assume the implementation is done and the developer already understands the technical foundations.
Focus on whether the repo tells a clear story about:
- what was built;
- how it is validated;
- how it is run locally;
- how outputs are interpreted;
- what evidence exists that the developer used AI responsibly and still owned the work.

Return:
1. missing release or handover detail;
2. any confusing documentation or command flow;
3. any final verification step that should be added before handoff.

Do not ask for tutorial-level explanations.
```

I used this as the final sanity check before wrapping up. It was less about code and more about whether the repo tells a clean enough story for someone else to trust it.

This prompt exists to support the final review loop. It is meant to surface anything that would make a reviewer less confident in the delivery, without turning the conversation into a basic training session.
