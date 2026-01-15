## Architecture Document for `linode_coder`

### Overview

`linode_coder` is a command-line interface (CLI) tool designed to manage virtual machine (VM) sessions on Linode for deploying and running large language models (LLMs). The tool provides functionalities such as creating, managing, and monitoring VM sessions, switching models, and validating performance.

### Key Components

1. **CLI Interface (`src/linode_coder/cli.py`)**:
   - Entry point for the application.
   - Uses the `click` library to define and handle CLI commands.

2. **Commands (`src/linode_coder/commands/`)**:
   - Each command is defined in its own module within the `commands` package.
   - Commands include `check`, `cleanup`, `down`, `extend`, `list`, `status`, `switch-model`, `up`, `use`, `validate`, `validate-perf`, and `wizard`.

3. **Configuration Management (`src/linode_coder/config.py`)**:
   - Loads and validates configuration settings from `.env` files.
   - Provides methods to retrieve configuration values such as GPU count and hourly cost.

4. **GPU Utilities (`src/linode_coder/gpu_utils.py`)**:
   - Contains classes and functions to monitor GPU status on remote hosts.
   - Includes `GPUInfo` dataclass and `GPUMonitor` class.

5. **Healing Mechanism (`src/linode_coder/healing.py`)**:
   - Detects and fixes common issues with the vLLM container.
   - Includes `HealingAction` dataclass and `VLLMHealer` class.

6. **Linode Client (`src/linode_coder/linode_client.py`)**:
   - Manages Linode instances for vLLM deployment.
   - Includes `LinodeManager` class.

7. **Session Management (`src/linode_coder/session.py`)**:
   - Manages VM sessions.
   - Includes `Session` dataclass and `SessionManager` class.

8. **SSH Utilities (`src/linode_coder/ssh_utils.py`)**:
   - Provides a simple SSH client for executing commands on remote hosts.
   - Includes `SSHClient` class.

9. **Watchdog (`src/linode_coder/watchdog.py`)**:
   - Monitors VM activity and auto-destructs if idle.
   - Includes `Watchdog` class.

### Component Interactions

1. **CLI Interface**:
   - Parses user input and invokes the appropriate command handler.
   - Utilizes configuration management to load necessary settings.

2. **Commands**:
   - Each command interacts with other components as needed.
   - For example, the `up` command uses the `LinodeManager` to create a new instance and the `SessionManager` to create a new session.

3. **Configuration Management**:
   - Provides configuration settings to other components.
   - Used by `LinodeManager` to generate cloud-init scripts and by `SessionManager` to calculate costs.

4. **GPU Utilities**:
   - Used by `Healing` and `Watchdog` to monitor GPU status.
   - Provides detailed information about GPU usage and health.

5. **Healing Mechanism**:
   - Detects and fixes issues with the vLLM container.
   - Invoked by `Watchdog` when issues are detected.

6. **Linode Client**:
   - Manages Linode instances.
   - Used by `SessionManager` to create, retrieve, and delete instances.

7. **Session Management**:
   - Manages VM sessions.
   - Used by various commands to create, retrieve, and delete sessions.

8. **SSH Utilities**:
   - Provides SSH access to remote hosts.
   - Used by `Healing` and `Watchdog` to execute commands on remote hosts.

9. **Watchdog**:
   - Monitors VM activity.
   - Uses `GPUUtils` to check GPU status and `Healing` to fix issues.
   - Auto-destructs VMs if they become idle.

### Workflow

1. **User Interaction**:
   - User runs a command via the CLI.
   - CLI parses the command and invokes the corresponding handler.

2. **Command Execution**:
   - Command handlers interact with other components as needed.
   - For example, the `up` command creates a new Linode instance and session.

3. **Configuration Loading**:
   - Configuration settings are loaded from `.env` files.
   - Settings are used by various components to perform their tasks.

4. **Session Management**:
   - Sessions are created, retrieved, and deleted using the `SessionManager`.
   - Sessions store information about VM instances, including IP addresses, model IDs, and costs.

5. **Linode Management**:
   - Linode instances are managed using the `LinodeManager`.
   - Instances are created, retrieved, and deleted as needed.

6. **Monitoring and Healing**:
   - The `Watchdog` monitors VM activity and invokes the `Healing` mechanism if issues are detected.
   - GPU status is monitored using the `GPUUtils`.

7. **SSH Access**:
   - SSH access is provided by the `SSHClient`.
   - Used by `Healing` and `Watchdog` to execute commands on remote hosts.

### Testing

- Unit tests are provided for various components.
- Tests are located in the `tests` directory.
- Key components tested include `Config`, `Session`, `SessionManager`, and `switch-model` command.

### Deployment

- The project is deployed using Docker.
- Docker Compose is used to manage the deployment process.
- Configuration files and environment variables are used to customize the deployment.

### Conclusion

This architecture document provides an overview of the `linode_coder` project, detailing its key components, interactions, and workflow. The modular design allows for easy maintenance and extension of the tool.
