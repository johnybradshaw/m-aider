# New Features - Python Version

This document describes the newly implemented features in the Python version of the Linode LLM Coder.

## 🧙 Interactive Wizard

The wizard provides a guided setup experience with dynamic selections based on your needs.

### Usage

```bash
source venv/bin/activate
coder wizard
```

### Features

1. **Capability Selection**
   - Small models (7B-14B) - Budget-friendly
   - Medium models (30B-32B) - Balanced
   - Large models (70B+) - Maximum capability
   - Custom - Specify your own model

2. **Region Selection**
   - Choose from available Linode regions
   - Considers latency for your use case

3. **GPU Type Selection**
   - Filtered by capability requirements
   - Shows GPU count, VRAM, and hourly cost
   - Recommends cheapest suitable option

4. **Model Configuration**
   - Default recommendations for each capability
   - Option to specify custom model
   - Configure context length

5. **Credential Management**
   - Preserves existing credentials
   - Prompts for missing requirements
   - Supports 1Password CLI references

### Example Session

```
╭───────────────────────────╮
│ LLM Deployment Wizard     │
╰───────────────────────────╯

Step 1: What capability do you need?

  1) Small models (7B-14B) - Fast, budget-friendly ($0.52-1.50/hr)
  2) Medium models (30B-32B) - Balanced performance ($1.04-3.00/hr)
  3) Large models (70B+) - Maximum capability ($3.00-6.00/hr)
  4) Custom - I'll specify my own model

Choice: 2

Step 2: Select your region

  1) us-east - Newark, NJ
  2) us-ord - Chicago, IL
  3) fr-par - Paris, FR

Choice: 3

Step 3: Select VM type

  1) 2x RTX 4000 Ada (40GB) - $1.04/hr ← Recommended
  2) 1x RTX 6000 Ada (48GB) - $1.50/hr
  3) 2x RTX 6000 Ada (96GB) - $3.00/hr

Choice: 1

Step 4: Model configuration

  Default model: Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
  Context: 32768 tokens

Use custom model instead? [y/N]: n

╭─────────────────────────────╮
│ Configuration Summary       │
╰─────────────────────────────╯

  Region:       fr-par
  VM Type:      g2-gpu-rtx4000a2-s
  GPUs:         2
  Total VRAM:   40GB
  Hourly Cost:  $1.04/hr

  Model:        Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
  Served as:    coder
  Context:      32768 tokens

Save configuration to .env? [Y/n]: y

✓ Configuration saved!

Next steps:
  coder validate    # Verify configuration
  coder up          # Deploy VM and launch
```

## ✅ Readiness Checks

The `coder up` command now includes comprehensive readiness validation.

### Cloud-Init Status Check

```
Waiting for cloud-init to complete...
Installing Docker, NVIDIA drivers, and starting containers

✓ Cloud-init completed successfully
```

**What it checks:**
- Waits for cloud-init to finish (max 30 minutes)
- Verifies successful completion
- Detects and reports errors
- Shows how to check logs if failed

**How it works:**
1. Cloud-init installs Docker and NVIDIA container toolkit
2. Creates systemd service (`vllm.service`) and enables it
3. VM reboots to activate NVIDIA drivers
4. After reboot, systemd automatically starts containers via `vllm.service`

### vLLM API Readiness Check

```
Waiting for vLLM API...
This may take 10-20 minutes while the model downloads and loads

✓ vLLM API is ready!
✓ Generated .aider.model.metadata.json
```

**What it checks:**
- vLLM API is responding (http://localhost:8000/v1)
- Model is loaded and listed
- Test completion request succeeds
- Generates aider metadata automatically

### Workflow

```
Creating Linode: llm-session-123
✓ Created Linode: 89975086 (172.233.255.17)

Waiting for SSH... (this may take 10-15 minutes)
✓ SSH ready

Waiting for cloud-init to complete...
Installing Docker, NVIDIA toolkit, and configuring services
VM will reboot to activate NVIDIA drivers...
✓ Cloud-init completed successfully

Setting up SSH tunnel...
✓ SSH tunnel established

Waiting for vLLM API...
This may take 10-20 minutes while the model downloads and loads
✓ vLLM API is ready!
✓ Generated .aider.model.metadata.json

✓ Your VM is ready! ($1.04/hour)
```

### Error Detection

**Cloud-init failed:**
```
✗ Cloud-init timeout or failed
Check logs with: ssh root@172.233.255.17 'cat /var/log/cloud-init-output.log'
```

**vLLM timeout:**
```
⚠ vLLM API timeout - model may still be loading
Check status with: ssh root@172.233.255.17 'docker logs -f $(docker ps -q)'
```

## 🤖 Auto-Launch Aider

Automatically launch aider when your VM is ready.

### Usage

```bash
source venv/bin/activate
coder up --launch-aider

# Or short form:
coder up -a
```

### What it does

1. **Sets environment variables:**
   ```bash
   OPENAI_API_BASE=http://localhost:8000/v1
   OPENAI_API_KEY=sk-dummy
   AIDER_MODEL=openai/coder
   ```

2. **Launches aider automatically:**
   - Uses `os.execvpe()` to replace the process
   - Environment is inherited properly
   - No need to manually source `.aider-env`

3. **Falls back gracefully:**
   ```
   ✗ aider not found in PATH

   Install aider with: pip install aider-chat

   Then run:
     source .aider-env
     aider --model "$AIDER_MODEL"
   ```

### Complete Workflow

```bash
# One command from configuration to coding:
coder wizard              # Configure (one-time)
coder up --launch-aider   # Deploy and launch aider

# You're now in aider, ready to code!
# VM will auto-destroy after idle timeout if watchdog enabled
```

## 🐕 Watchdog (Auto-Destroy)

Automatically destroy idle VMs to prevent unexpected costs.

### Configuration

Add to `.env`:

```bash
WATCHDOG_ENABLED=true
WATCHDOG_TIMEOUT_MINUTES=30      # Auto-destroy after 30min idle
WATCHDOG_WARNING_MINUTES=5       # Warn 5min before destruction
```

### How It Works

1. **Background Process:**
   - Starts when `coder up` completes
   - Runs independently of your session
   - PID saved to `~/.cache/linode-vms/<session>/watchdog.pid`

2. **Activity Detection:**
   - Checks vLLM container logs every 60 seconds
   - Looks for API requests (POST/GET)
   - Resets idle timer when activity found

3. **Warning Notification:**
   ```
   🔔 VM 'my-session' will be destroyed in 5 minutes due to inactivity
   ```
   - macOS: Uses `osascript` for native notifications
   - Linux: Uses `notify-send` for desktop notifications

4. **Auto-Destruction:**
   - Destroys VM via Linode API
   - Cleans up session directory
   - Shows total cost

### Output

```
Starting watchdog...
VM will auto-destroy after 30 minutes of inactivity

✓ Watchdog started (PID: 12345)
  • Idle timeout: 30 minutes
  • Warning: 5 minutes before destruction
```

### Features

**Desktop Notifications:**
- Warning 5 minutes before destruction
- Final notification when destroying
- Works on macOS and Linux

**Activity Monitoring:**
- Checks Docker logs for API requests
- 60-second check interval
- Automatic timer reset on activity

**Graceful Shutdown:**
- Stops watchdog when you run `coder down`
- Cleans up PID file
- Shows session cost summary

### Security

**Client-Side Only:**
- API token never leaves your machine
- Watchdog runs on your computer, not the VM
- No additional security risk

**Blast Radius:**
- Only affects the specific VM
- No access to other resources
- Safe from compromised VMs

## 🎯 Combined Workflow

All features work together for the ultimate UX:

### First Time Setup

```bash
# Install
./install-python-coder.sh
source venv/bin/activate

# Configure (one-time, interactive)
coder wizard

# Enable watchdog in .env
echo "WATCHDOG_ENABLED=true" >> .env
```

### Daily Usage

```bash
# One command to deploy and start coding:
source venv/bin/activate
coder up --launch-aider

# The system will:
# 1. Create VM
# 2. Wait for SSH
# 3. Wait for cloud-init
# 4. Setup SSH tunnel
# 5. Wait for vLLM to load model
# 6. Generate aider metadata
# 7. Start watchdog
# 8. Launch aider automatically

# You're now coding!
# VM will auto-destroy after 30min idle
```

### When Done

```bash
# Just exit aider
# Watchdog will destroy VM after 30min idle

# Or destroy immediately:
coder down
```

## 📊 Feature Comparison

| Feature | Bash | Python |
|---------|------|--------|
| **VM Creation** | ⚠️ Manual API fixes | ✅ SDK handles automatically |
| **Wizard** | ❌ Stub only | ✅ Fully implemented |
| **Cloud-init Check** | ❌ Manual | ✅ Automatic |
| **vLLM Readiness** | ❌ Manual | ✅ Automatic |
| **Aider Metadata** | ⚠️ Manual generation | ✅ Auto-generated |
| **Auto-Launch Aider** | ❌ Not available | ✅ Available |
| **Watchdog** | ✅ Bash script | ✅ Python process |
| **Activity Detection** | ✅ SSH logs | ✅ SSH logs |
| **Notifications** | ✅ osascript/notify-send | ✅ osascript/notify-send |
| **Session Management** | ✅ | ✅ |
| **GPU Validation** | ✅ Basic scripts | ✅ Rich CLI commands |

## 🚀 Quick Start Examples

### Example 1: Quick Setup

```bash
source venv/bin/activate

# Interactive wizard
coder wizard

# Deploy with all features
coder up --launch-aider
```

### Example 2: Manual Configuration

```bash
# Edit .env manually
cat > .env <<EOF
REGION=fr-par
TYPE=g2-gpu-rtx4000a2-s
FIREWALL_ID=123456
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_TENSOR_PARALLEL_SIZE=2
VLLM_MAX_MODEL_LEN=32768
WATCHDOG_ENABLED=true
WATCHDOG_TIMEOUT_MINUTES=30
EOF

# Deploy
coder up --launch-aider
```

### Example 3: Multiple Sessions

```bash
# Create first session
coder up dev-session

# Create second session
coder up test-session

# List all
coder list

# Switch between them
coder use dev-session
coder use test-session
```

## 📝 Documentation

- **NEW-FEATURES.md** - This file (new features guide)
- **PYTHON-MIGRATION.md** - Migration guide
- **VALIDATION-COMMANDS.md** - Validation quick reference
- **VALIDATION-GUIDE.md** - Comprehensive validation guide
- **CLAUDE.md** - Main documentation

## ⏭️ Next Steps

After using these features:

1. **Validate GPU Performance:**
   ```bash
   coder check                  # Quick health check
   coder validate-perf          # Comprehensive analysis
   ```

2. **Monitor Costs:**
   ```bash
   coder list                   # See all VMs and costs
   coder status                 # Check specific session
   ```

3. **Manage Sessions:**
   ```bash
   coder down                   # Destroy current session
   coder down my-session        # Destroy specific session
   ```

## 🐛 Troubleshooting

### Wizard Issues

**Problem:** Wizard crashes or shows errors

**Solution:**
```bash
# Check if linode_api4 is installed
pip list | grep linode

# Reinstall if needed
pip install -e .
```

### Readiness Check Timeout

**Problem:** Cloud-init or vLLM times out

**Solution:**
```bash
# SSH to VM and check status
ssh root@<IP>

# Check cloud-init
cloud-init status

# Check Docker containers
docker ps
docker logs <container-id>

# Check for errors
cat /var/log/cloud-init-output.log
```

### Auto-Launch Aider Fails

**Problem:** aider not found in PATH

**Solution:**
```bash
# Install aider
pip install aider-chat

# Verify it's in PATH
which aider

# Or use manual method
source .aider-env
aider --model "$AIDER_MODEL"
```

### Watchdog Not Working

**Problem:** VM not destroyed after timeout

**Solution:**
```bash
# Check if watchdog is running
ps aux | grep watchdog

# Check PID file
cat ~/.cache/linode-vms/<session>/watchdog.pid

# Verify WATCHDOG_ENABLED in .env
grep WATCHDOG .env

# Manual destruction
coder down
```

## 🎉 Summary

The Python version now includes:

✅ **Interactive wizard** - Guided setup for new users
✅ **Cloud-init checks** - Verify VM initialization succeeded
✅ **vLLM readiness** - Wait for model to load before completion
✅ **Auto-generate aider metadata** - No more token limit errors
✅ **Auto-launch aider** - One command from deploy to coding
✅ **Watchdog** - Auto-destroy idle VMs to save money

All features work together for a seamless experience from configuration to coding!
