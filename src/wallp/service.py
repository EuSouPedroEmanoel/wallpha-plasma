import subprocess

from . import log
from .paths import LOG_FILE

UNIT = "wallp-daemon.service"
INSTALLER = "~/dev/Verity/wallp/install.sh"


def _start_service():
    rc = subprocess.run(
        ["systemctl", "--user", "enable", UNIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    rc2 = subprocess.run(
        ["systemctl", "--user", "restart", UNIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode
    if rc != 0 or rc2 != 0:
        print(f"Aviso: o serviço {UNIT} não foi (re)iniciado.")
        print(f"Instale o daemon uma vez com: {INSTALLER}")


def _stop_service():
    subprocess.run(
        ["systemctl", "--user", "stop", UNIT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _show_log(opts=None, follow=True):
    n = (opts or {}).get("log_lines") or 50
    logfile = LOG_FILE
    if not logfile.exists():
        log.err(f"nenhum log ainda ({logfile}); rode wallp -a, -r ou -c primeiro")
        return
    args = ["tail"]
    if follow:
        args.append("-f")
    subprocess.run(args + ["-n", str(n), str(logfile)])
