# Legacy Systems v2.0

This folder is the boundary for features that are no longer part of the
primary Neuron Cockpit product surface.

Primary Cockpit scope:

- Semantic Search
- Chat with Auto, Query, and Action modes
- Qwen 2.5 Coder local model
- BGE Small semantic embeddings
- Simple tool-call intent from Chat Action mode

Legacy Systems v2.0 scope:

- Full agentic tool registry
- Terminal/PowerShell execution flows
- Claw/MCP tool experiments
- Multi-step file mutation agents
- Approval and task queue experiments that need hardening before returning to
  the primary product

The current Python modules remain in their existing import paths to avoid
breaking tests and runtime compatibility. Treat the following modules as the
legacy boundary until they are migrated behind a hardened Cockpit API:

- `services/agent/`
- `services/tools/`
- `services/powershell_session.py`
- `services/agent_context.py`
- `services/plugins/`
- `services/validation/`
- `ui/activity_panel.py`
- `ui/research_overlay.py`

Do not wire these directly into the primary Cockpit UI. Promote individual
capabilities back only after they have deterministic tests, explicit permission
contracts, and crash-safe process isolation.
