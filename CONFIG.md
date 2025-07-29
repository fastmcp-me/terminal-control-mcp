# Configuration

You can configure the server using a `terminal-control.toml` file in the project root or by setting environment variables. Environment variables always take precedence over the settings in the TOML file.

## Configuration Options

| Setting                      | TOML Key                         | Environment Variable                       | Default     | Description                                                                 |
| ---------------------------- | -------------------------------- | ------------------------------------------ | ----------- | --------------------------------------------------------------------------- |
| **Web Interface**            |                                  |                                            |             |                                                                             |
| Enable Web Interface         | `web.enabled`                    | `TERMINAL_CONTROL_WEB_ENABLED`             | `true`      | Enable or disable the web interface.                                        |
| Host                         | `web.host`                       | `TERMINAL_CONTROL_WEB_HOST`                | `0.0.0.0`   | The host address to bind the web server to.                                 |
| Port                         | `web.port`                       | `TERMINAL_CONTROL_WEB_PORT`                | `8080`      | The port to run the web server on.                                          |
| External Host                | `web.external_host`              | `TERMINAL_CONTROL_EXTERNAL_HOST`           | `null`      | The public-facing hostname for generating URLs (e.g., `dev.example.com`).   |
| **Security**                 |                                  |                                            |             |                                                                             |
| Security Level               | `security.level`                 | `TERMINAL_CONTROL_SECURITY_LEVEL`          | `high`      | The security level: `off`, `low`, `medium`, or `high`.                      |
| Max Calls Per Minute         | `security.max_calls_per_minute`  | `TERMINAL_CONTROL_MAX_CALLS_PER_MINUTE`    | `60`        | The maximum number of tool calls allowed per minute.                        |
| Max Sessions                 | `security.max_sessions`          | `TERMINAL_CONTROL_MAX_SESSIONS`            | `50`        | The maximum number of concurrent terminal sessions.                         |
| **Session**                  |                                  |                                            |             |                                                                             |
| Default Shell                | `session.default_shell`          | `TERMINAL_CONTROL_DEFAULT_SHELL`           | `bash`      | The default shell to use for new sessions (e.g., `bash`, `zsh`).            |
| Session Timeout              | `session.timeout`                | `TERMINAL_CONTROL_SESSION_TIMEOUT`         | `30`        | The timeout in seconds for a new session to start.                          |
| **Terminal**                 |                                  |                                            |             |                                                                             |
| Width                        | `terminal.width`                 | `TERMINAL_CONTROL_TERMINAL_WIDTH`          | `120`       | The width of the terminal in columns.                                       |
| Height                       | `terminal.height`                | `TERMINAL_CONTROL_TERMINAL_HEIGHT`         | `30`        | The height of the terminal in rows.                                         |
| **Logging**                  |                                  |                                            |             |                                                                             |
| Log Level                    | `logging.level`                  | `TERMINAL_CONTROL_LOG_LEVEL`               | `INFO`      | The log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR`.                      |

## Example `terminal-control.toml`

```toml
# Web interface settings
[web]
enabled = true
host = "0.0.0.0"
port = 8080

# Security settings
[security]
level = "high"
max_calls_per_minute = 60
max_sessions = 50

# Session settings
[session]
default_shell = "bash"
timeout = 30

# Logging settings
[logging]
level = "INFO"
```
