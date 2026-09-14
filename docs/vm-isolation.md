# Local VM execution contract

`POST /v1/vm/run` runs one-shot Docker containers on the host where the API process has access to `/var/run/docker.sock`.

## Localhost-only

The route rejects clients whose TCP peer is not loopback (`127.0.0.1`, `::1`). This does not replace binding the API to localhost; it adds a guard so remote callers cannot trigger container execution if the server is mis-exposed.

## Runtime limits

- Maximum wall time: 10 minutes (`executionState: timeout` when exceeded; partial logs are returned).
- Stdout and stderr: 512 KiB each; `stdoutTruncated` / `stderrTruncated` flag overflow.
- Memory: 1 GiB, CPU: 1 core, PID limit: 256.

## Isolation (best-effort)

Containers run with `cap_drop=ALL`, `no-new-privileges`, read-only root filesystem, workspace mounted read-write at `/workspace`, and bridge networking. Trusted local code can still reach the network and write into the workspace volume. Do not expose the API beyond localhost.

## Languages

Supported: `bash`, `python`, `node`, `bun`, `rust`, `c`, `go`.

## Output files

Each path in `outputFiles` appears in the response. Present files include a download path; missing files return `error: not_found` and are omitted from the download manifest.
