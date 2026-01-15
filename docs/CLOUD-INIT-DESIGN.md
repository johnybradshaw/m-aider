# Cloud-Init Design for GPU VM Initialization

## Overview

This document explains the cloud-init design for automatically setting up GPU VMs with Docker, NVIDIA drivers, and vLLM containers.

## Design Evolution

### ❌ Approach 1: Direct Start in runcmd (FAILED)
```yaml
runcmd:
  - systemctl restart docker
  - sleep 5
  - cd /opt/llm && docker compose up -d
```
**Problem:** Race condition - containers might start before NVIDIA drivers fully initialized.

### ❌ Approach 2: bootcmd (FAILED)
```yaml
bootcmd:
  - cd /opt/llm && docker compose up -d
```
**Problem:** `bootcmd` runs too early - before Docker daemon starts. Error: "Cannot connect to the Docker daemon at unix:///var/run/docker.sock"

### ✅ Approach 3: Systemd Service + Reboot (FINAL)
```yaml
write_files:
  - path: /etc/systemd/system/vllm.service
    content: |
      [Unit]
      Description=vLLM and Open WebUI containers
      After=docker.service
      Requires=docker.service

      [Service]
      Type=oneshot
      RemainAfterExit=yes
      WorkingDirectory=/opt/llm
      ExecStart=/usr/bin/docker compose up -d
      ExecStop=/usr/bin/docker compose down

      [Install]
      WantedBy=multi-user.target

runcmd:
  - nvidia-ctk runtime configure --runtime=docker
  - systemctl daemon-reload
  - systemctl enable vllm.service

power_state:
  mode: reboot
  message: Rebooting to activate NVIDIA drivers
```

## Why This Approach Works

### 1. Systemd Dependency Management
- `After=docker.service` - Ensures Docker is started first
- `Requires=docker.service` - Won't start if Docker fails
- Proper ordering guaranteed by systemd

### 2. NVIDIA Driver Installation & Activation
- NVIDIA drivers are **NOT** pre-installed on Linode GPU instances
- We install `nvidia-driver-580-server` directly for reliability
- **Why server variant?** Linode GPU instances are server hardware - server drivers are:
  - Optimized for data center/cloud environments
  - Designed for headless systems (no display)
  - Better for compute workloads (ML/AI)
  - More stable for long-running processes
- **Why not auto-detect?** `ubuntu-drivers install --gpgpu` often hangs during cloud-init
- **Why nvidia-driver-580-server?** Latest stable server driver in Ubuntu 24.04, supports RTX 4000/6000 series
- `DEBIAN_FRONTEND=noninteractive` prevents interactive prompts during cloud-init
- Drivers need reboot to fully initialize kernel modules
- Reboot ensures `nvidia-smi` and GPU access work correctly

**Available server driver versions in Ubuntu 24.04:**
- 535-server (LTS)
- 550-server
- 565-server
- 570-server
- 575-server
- **580-server** (latest - we use this)

**Trade-off**: Hardcoded driver version vs. reliability. We chose reliability.
Future: Could make driver version configurable in `.env` if needed.

### 3. Automatic Startup
- `systemctl enable` makes service start on every boot
- No manual intervention needed
- Survives reboots and crashes

### 4. Clean Lifecycle
- `Type=oneshot` - Runs once then exits
- `RemainAfterExit=yes` - Systemd considers it "running"
- `ExecStop` - Clean shutdown when VM is destroyed

## Complete Boot Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. First Boot - Cloud-Init Phase                           │
├─────────────────────────────────────────────────────────────┤
│  • Install Docker packages                                  │
│  • Install NVIDIA container toolkit                         │
│  • Configure Docker for NVIDIA runtime                      │
│  • Write vllm.service to /etc/systemd/system/              │
│  • Enable vllm.service (systemctl enable)                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Automatic Reboot (power_state)                          │
├─────────────────────────────────────────────────────────────┤
│  • Kernel reloads with NVIDIA modules                       │
│  • GPU devices become accessible                            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Second Boot - Normal Systemd Startup                    │
├─────────────────────────────────────────────────────────────┤
│  • systemd starts                                            │
│  • docker.service starts                                     │
│  • vllm.service starts (depends on docker.service)         │
│  • Containers launch via docker compose up -d              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Ready for Use                                            │
├─────────────────────────────────────────────────────────────┤
│  • vLLM downloads model (10-20 minutes)                     │
│  • API becomes available at http://localhost:8000          │
│  • Open WebUI available at http://localhost:3000           │
└─────────────────────────────────────────────────────────────┘
```

## Timing Expectations

| Phase | Duration | Notes |
|-------|----------|-------|
| Initial SSH available | 2-3 minutes | VM boots, sshd starts |
| Cloud-init completes | 5-10 minutes | Package installation |
| Automatic reboot | 1-2 minutes | Quick reboot |
| Services start | 30-60 seconds | Docker + vLLM service |
| Model download | 10-20 minutes | Depends on model size |
| **Total** | **20-35 minutes** | First-time deployment |

## Debugging

### Check Cloud-Init Status
```bash
# Check if cloud-init finished
cloud-init status

# View detailed status
cloud-init status --long

# View cloud-init output
cat /var/log/cloud-init-output.log

# Check for errors
cat /run/cloud-init/result.json
```

### Check Systemd Service
```bash
# Check if service is enabled
systemctl is-enabled vllm.service

# Check service status
systemctl status vllm.service

# View service logs
journalctl -u vllm.service

# Check Docker status
systemctl status docker
```

### Check NVIDIA Runtime
```bash
# Verify NVIDIA drivers loaded
nvidia-smi

# Check Docker can see GPUs
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi

# Verify Docker daemon config
cat /etc/docker/daemon.json
```

### Check Containers
```bash
# List containers
docker ps -a

# View vLLM logs
docker logs vllm

# View Open WebUI logs
docker logs open-webui

# Check docker-compose config
cat /opt/llm/docker-compose.yml
```

## Common Issues

### Issue: Cloud-init status: error
**Cause:** Package installation failed or syntax error in cloud-init
**Solution:** Check `/var/log/cloud-init-output.log` for specific errors

### Issue: vllm.service failed to start
**Cause:** Docker not running or docker-compose.yml syntax error
**Solution:**
```bash
systemctl status docker
journalctl -u vllm.service
```

### Issue: Containers start but GPU not accessible
**Cause:** NVIDIA runtime not configured or drivers not loaded
**Solution:**
```bash
nvidia-smi  # Should show GPUs
cat /etc/docker/daemon.json  # Should have nvidia runtime
```

### Issue: Model fails to download
**Cause:** Missing HuggingFace token or network issue
**Solution:**
```bash
cat /opt/llm/.env  # Verify HF_TOKEN is set
docker logs vllm   # Check for auth errors
```

## File Locations

| File | Purpose |
|------|---------|
| `/etc/systemd/system/vllm.service` | Systemd service definition |
| `/opt/llm/docker-compose.yml` | Docker Compose configuration |
| `/opt/llm/.env` | HuggingFace token (mode 0600) |
| `/etc/docker/daemon.json` | Docker NVIDIA runtime config |
| `/var/log/cloud-init-output.log` | Cloud-init output |
| `/run/cloud-init/result.json` | Cloud-init result/errors |

## Security Considerations

1. **Token Security**: HF token stored in `/opt/llm/.env` with mode 0600 (root only)
2. **Service Isolation**: Containers bind to 127.0.0.1 only (no public access)
3. **SSH Tunnel**: All external access goes through SSH tunnel
4. **Firewall**: Linode firewall allows SSH only
5. **No Public Endpoints**: vLLM and WebUI not exposed to internet

## Benefits of This Design

✅ **Reliable**: Systemd ensures proper startup order and dependency management
✅ **Automatic**: No manual intervention needed after VM creation
✅ **Robust**: Survives reboots and service crashes
✅ **Debuggable**: Standard systemd tools for troubleshooting
✅ **Clean**: Proper shutdown with `systemctl stop vllm.service`
✅ **Production-Ready**: Industry-standard approach for service management

## Alternative Approaches Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| Direct in runcmd | Simple | Race conditions, no restart on boot | ❌ Rejected |
| bootcmd | Runs early | Too early (before Docker) | ❌ Rejected |
| cron @reboot | No dependencies | Crude, hard to debug | ❌ Rejected |
| Custom init script | Full control | Reinventing systemd | ❌ Rejected |
| **Systemd service** | **Standard, reliable** | **Requires reboot** | ✅ **Chosen** |

## Conclusion

The systemd service + reboot approach provides the most reliable and maintainable solution for GPU VM initialization. While it adds a reboot step (1-2 minutes), this ensures NVIDIA drivers are fully active and provides a production-quality service lifecycle.
