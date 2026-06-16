# File Rules

Allowed:
- Modify files directly related to the task.
- Create new files only when needed.
- Update documentation if behavior changes.

Forbidden:
- Do not delete files without explicit permission.
- Do not rename major files without explicit permission.
- Do not rewrite the whole project.
- Do not change formatting across unrelated files.
- Do not modify secrets, credentials, or environment files.

Sensitive files:
- .env
- config.json
- secrets.json
- credentials.json

Never expose or print secrets from these files.