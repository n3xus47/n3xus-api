# Configure n3xusAPI for an agent

Read this file when setting up the skill, changing the API deployment, or diagnosing a connection/authentication error.

## Agent environment

The agent process reads these variables from its environment:

| Variable | Value | Purpose |
| --- | --- | --- |
| `N3XUS_API_BASE_URL` | `http://127.0.0.1:8000` | Base URL of the API. Set this to the URL reachable by the agent. |
| `N3XUS_API_REPO` | Absolute path to the checkout | Repository used to start the local stack. When the skill is loaded from this checkout, the agent can infer the root from `.agents/skills/n3xusapi/`. |
| `N3XUS_API_API_KEY` | Unset by default | Optional client credential. Set it only when the API server has `N3XUS_API_API_KEY` enabled. |

Example for a local checkout:

```sh
export N3XUS_API_BASE_URL="http://127.0.0.1:8000"
export N3XUS_API_REPO="/absolute/path/to/n3xus-api"
# Set only when API-key authentication is enabled:
# export N3XUS_API_API_KEY="your-local-key"
```

Keep the API key in the agent's secret/environment settings. Do not commit it to the repository, put it in a prompt, or print it in command output.

## Select a service

1. If `N3XUS_API_BASE_URL` points to an existing service, check `GET $N3XUS_API_BASE_URL/v1/health` and use that service. Do not start a second local stack.
2. If using the default local URL and it is unavailable, resolve `N3XUS_API_REPO` and run `scripts/ensure-local-stack.sh` from that repository root.
3. The startup script starts Ollama and SearxNG, ensures the configured model is installed, starts the API, and waits for `/v1/health`. The model defaults to `qwen3.5:27b`; set `N3XUS_API_OLLAMA_MODEL` in the server environment before startup to select another Ollama model.
4. If the health check still fails, report the observed startup or HTTP error. Do not switch to direct HTTP requests to the target website.

## Server configuration

Server settings use the `N3XUS_API_` prefix and can be read from a server-side `.env` file. The API key is optional. Other integrations are opt-in: SMTP (`N3XUS_API_SMTP_URL`), local image generation (`N3XUS_API_STABLE_DIFFUSION_URL`), and Meta Ads Library (`N3XUS_API_META_ADS_ACCESS_TOKEN`). Keep service secrets on the API host, separate from the agent's client configuration. See the repository [README configuration table](../../../../README.md#konfiguracja) for supported settings.

The default Compose port is bound to `127.0.0.1:8000`. If an agent runs in a different container or machine, configure a reachable `N3XUS_API_BASE_URL` and deploy the API with appropriate network controls; the default URL is loopback on the agent host.
