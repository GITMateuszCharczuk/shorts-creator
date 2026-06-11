# Power policy — keeping the box awake for the nightly batch (ADR 0015 D3)

The conductor runs unattended at 02:00 inside the WSL2 distro
(`shorts-batch.timer` → `shorts-batch.service`). Everything below exists so the
Windows host neither sleeps through, reboots over, nor silently drops the
distro during the 01:00–06:00 batch window. Run through this checklist once per
machine (and re-verify after major Windows updates).

1. **Disable sleep on AC power** — in an elevated PowerShell/cmd on the
   Windows host:

   ```
   powercfg /change standby-timeout-ac 0
   ```

   The box must stay awake unattended; a sleeping host suspends the WSL2 VM
   and the batch with it.

2. **Set Windows Update active hours to exclude the batch window** — configure
   *Settings → Windows Update → Advanced options → Active hours* so that
   automatic restarts can never land inside **01:00–06:00**. An update reboot
   mid-batch kills the conductor and the distro under it.

3. **Keep the distro alive: the Task Scheduler `wsl`-at-logon task (ADR 0013)**
   — register a Windows Task Scheduler task that runs `wsl` at user logon so
   the distro (and its systemd) is up whenever the host is. Without it the
   timer has no systemd to fire under.

4. **Verify the timer is enabled inside the distro:**

   ```
   systemctl is-enabled shorts-batch.timer
   ```

   must print `enabled`. (Install with `systemctl enable --now
   shorts-batch.timer` after copying the units into
   `/etc/systemd/system/`.)

5. **`TimeoutStartSec=10h` is the batch watchdog** — a hung conductor is
   killed by systemd at the 10-hour mark, its lockfile goes stale (holder pid
   dead), and the next run's stale-pid takeover acquires the lock and carries
   on. No manual cleanup is required after a hang.
