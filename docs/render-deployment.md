# Render Deployment
## Goal

Publish the Enterprise AI Service Desk Agent on GitHub and deploy a public Streamlit URL plus a FastAPI API on Render.

## 1. GitHub

```bash
git init
git add .
git commit -m "Initial enterprise AI agent POC"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/enterprise-ai-agent.git
git push -u origin main
```

Never commit `.env` or any API key.

## 2. Render Blueprint

In Render:

**New → Blueprint → connect the GitHub repository**

Render reads the root `render.yaml`.

The Blueprint creates:

- `enterprise-ai-agent-api`
- `enterprise-ai-agent-ui`
- `enterprise-ai-agent-db`
- `enterprise-ai-agent-cache`

The API receives the database and Key Value connection strings through Render's service references. The UI receives the API's public URL through `RENDER_EXTERNAL_URL`.

## 3. Secret

When Render asks for:

```text
GROQ_API_KEY
```

paste the key there.

Do not add it to `render.yaml`, GitHub, Dockerfiles, or the README.

## 4. URLs after deployment

Render gives the UI a public URL similar to:

```text
https://enterprise-ai-agent-ui.onrender.com
```


The API will have another public URL:

```text
https://enterprise-ai-agent-api.onrender.com
```

Useful API pages:

```text
/health
/status
/docs
/metrics
```

## 5. demo

Use:

```text

```

Demo:

1. VPN troubleshooting question
2. Agentic RAG explanation
3. Ticket creation request
4. Human approval
5. Ticket list
6. RBAC test
7. Prompt-injection guardrail
8. `/metrics`
9. `/docs`
10. GitHub + Render architecture

## 6. Free-tier caveat

Render's free services are excellent for a short portfolio/demo deployment, but they are not production hosting. Free Postgres currently expires after 30 days and free Key Value is in-memory. Free web services can also spin down while idle.

For a permanent production deployment, move the database/cache to appropriate paid or external managed infrastructure and use SSO, secrets management, migrations, monitoring and stronger security controls.
