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

## Initialize and update the local stack

After cloning the repository, run this once to create `.env`, fetch current Docker images and the latest version of the configured Ollama model, build the API image, and start the services:

```sh
npm run setup
```

Run `npm run setup` again when you want to check for upstream image/model updates. Docker and Ollama reuse unchanged layers and model data. The default model is `qwen3.5:4b`; setup migrates the previous default `qwen3.5:27b` but preserves a model explicitly selected in the shell or `.env`. Set `N3XUS_API_OLLAMA_MODEL` to choose another model.

For normal skill use, start an initialized stack without network updates or rebuilds:

```sh
npm start
```

This fast path uses `docker compose up --no-build --pull never`, checks that the configured model is already installed, and waits for `/v1/health`. If setup has not run or local prerequisites are missing, it exits with a `npm run setup` instruction. The skill uses this fast path only when the default local API is unavailable.

## Select a service

1. If `N3XUS_API_BASE_URL` points to an existing service, check `GET $N3XUS_API_BASE_URL/v1/health` and use that service. Do not start a second local stack.
2. If using the default local URL and it is unavailable, resolve `N3XUS_API_REPO` and run `npm start` (or `scripts/ensure-local-stack.sh`) from that repository root.
3. The fast start script uses installed images and the configured model, starts the services, and waits for `/v1/health`. Run `npm run setup` when the local stack has not been initialized or when you want the latest upstream images/model.
4. If the health check still fails, report the observed startup or HTTP error. Do not switch to direct HTTP requests to the target website.

## Server configuration

Server settings use the `N3XUS_API_` prefix and can be read from a server-side `.env` file. The API key is optional. Other integrations are opt-in: SMTP (`N3XUS_API_SMTP_URL`), local image generation (`N3XUS_API_STABLE_DIFFUSION_URL`), and Meta Ads Library (`N3XUS_API_META_ADS_ACCESS_TOKEN`). Keep service secrets on the API host, separate from the agent's client configuration. See the repository [README configuration table](../../../../README.md#konfiguracja) for supported settings.

The default Compose port is bound to `127.0.0.1:8000`. If an agent runs in a different container or machine, configure a reachable `N3XUS_API_BASE_URL` and deploy the API with appropriate network controls; the default URL is loopback on the agent host.
