import json
import os
import re
import urllib.request
from pathlib import Path

from . import entries, log, media

try:
    HEAVY_LIMIT = int(os.environ.get("WALLP_YT_CACHE_MB", "500")) * 1024 * 1024
except ValueError:
    HEAVY_LIMIT = 500 * 1024 * 1024

def _hum_size(n):
    if n is None:
        return "-"
    if n < 1024:
        return f"{n} B"
    if n < 1024*1024:
        return f"{n/1024:.1f} KB"
    if n < 1024*1024*1024:
        return f"{n/1024/1024:.1f} MB"
    return f"{n/1024/1024/1024:.2f} GB"

def _short_path(p):
    try:
        pp = Path(str(p)).expanduser()
        if not pp.name:
            return str(p)
        if pp.parent and pp.parent.name and pp.parent.name not in (".", "/"):
            return f"{pp.parent.name}/{pp.name}"
        return pp.name
    except Exception:
        return str(p)


def _local_version():
    try:
        import importlib.metadata
        for pkg in ("wallp", "wallp-plasma"):
            try:
                v = importlib.metadata.version(pkg)
                if v:
                    return v
            except Exception:
                continue
    except Exception:
        pass
    try:
        p = Path(__file__).parents[2] / "pyproject.toml"
        if p.is_file():
            txt = p.read_text()
            m = re.search(r'version\s*=\s*"([^"]+)"', txt)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None


def _latest_tag(repo):
    try:
        url = f"https://api.github.com/repos/EuSouPedroEmanoel/{repo}/releases/latest"
        with urllib.request.urlopen(url, timeout=1.5) as r:
            data = json.loads(r.read().decode())
            tag = data.get("tag_name", "")
            return tag.lstrip("v")
    except Exception:
        return None


def _warn_updates():
    try:
        is_plasma = "wallp-plasma" in str(Path(__file__).resolve())
        local = _local_version()
        if not local:
            return
        latest_plasma = _latest_tag("wallp-plasma")
        if latest_plasma:
            plasma_local = None
            if not is_plasma:
                for cand in [Path.home() / "dev/wallp/wallp-plasma/pyproject.toml", Path.home() / ".local/share/wallp-plasma/pyproject.toml"]:
                    if cand.is_file():
                        try:
                            txt2 = cand.read_text()
                            m2 = re.search(r'version\s*=\s*"([^"]+)"', txt2)
                            if m2:
                                plasma_local = m2.group(1)
                                break
                        except Exception:
                            continue
                if plasma_local is None:
                    plasma_local = latest_plasma
                check_ver = plasma_local
            else:
                check_ver = local
            try:
                lv = tuple(int(x) for x in check_ver.split(".") if x.isdigit())
                lt = tuple(int(x) for x in latest_plasma.split(".") if x.isdigit())
                if lt > lv:
                    print(f"⚠️  atualização disponível: wallp-plasma {latest_plasma} > {check_ver} — curl -fsSL https://raw.githubusercontent.com/EuSouPedroEmanoel/wallp-plasma/master/quick-install.sh | bash -s -- -y")
            except Exception:
                pass
        if not is_plasma:
            latest_cli = _latest_tag("wallp-cli")
            if latest_cli and local:
                try:
                    lv = tuple(int(x) for x in local.split(".") if x.isdigit())
                    lt = tuple(int(x) for x in latest_cli.split(".") if x.isdigit())
                    if lt > lv:
                        print(f"⚠️  atualização disponível: wallp-cli {latest_cli} > {local} — curl -fsSL https://raw.githubusercontent.com/EuSouPedroEmanoel/wallp-cli/master/quick-install.sh | bash -s -- -y")
                except Exception:
                    pass
    except Exception:
        pass


def _profile_mode(opts):
    entries_list = entries.load_checked()
    if entries_list is None:
        import sys; sys.exit(1)
    if not entries_list and not entries.LISTAS:
        log.err("nenhum wallpaper no yml. Rode: wallp --init")
        import sys; sys.exit(1)

    # coleta todos os entries + listas nomeadas
    all_entries = list(entries_list)
    for lst in entries.LISTAS.values():
        if lst not in all_entries:
            all_entries.append(lst)
            # adiciona subs expostos para checagem de arquivos
            for s in lst.get("sub_entries") or []:
                if s not in all_entries:
                    all_entries.append(s)
                if s.get("is_list"):
                    for ss in s.get("sub_entries") or []:
                        if ss not in all_entries:
                            all_entries.append(ss)

    print(f"wallp --profile — varredura de {len(all_entries)} entradas (limite pesado {_hum_size(HEAVY_LIMIT)}):\n")

    heavy = []
    missing = []
    zero_dir = []
    ok = []

    for e in all_entries:
        nome = e.get("nome") or "(sem nome)"
        is_yt = e.get("is_yt")
        is_dir = e.get("is_dir")
        is_list = e.get("is_list")
        local = e.get("local") or ""
        arquivo = e.get("arquivo") or local

        # yt: não tem tamanho local, checa cache
        if is_yt:
            # yt sem arquivo local é esperado; só avisa se yt_dir tem algo pesado?
            # aqui só conta como ok, pesado será no yt buffer
            ok.append((e, None, "yt"))
            continue
        if is_list:
            # lista: checa cada sub
            subs = e.get("sub_entries") or []
            sub_heavy = False
            for s in subs:
                if s.get("is_yt"):
                    continue
                p = Path(str(s.get("arquivo") or s.get("local") or "")).expanduser()
                if not p.exists():
                    # dir lista pode ter local que é dir existente mas arquivo é calculado depois
                    if s.get("is_dir"):
                        if not Path(str(s.get("local"))).expanduser().is_dir():
                            missing.append((s, p))
                    else:
                        missing.append((s, p))
                else:
                    try:
                        sz = p.stat().st_size if p.is_file() else None
                        if sz and sz > HEAVY_LIMIT:
                            heavy.append((s, sz))
                            sub_heavy = True
                    except OSError:
                        pass
            if not sub_heavy and e not in missing:
                ok.append((e, None, "lista"))
            continue

        # arquivo ou diretório
        if is_dir:
            p = Path(str(local)).expanduser()
            if not p.is_dir():
                missing.append((e, p))
                continue
            files = e.get("files") or []
            if not files:
                zero_dir.append((e, p))
                continue
            total = 0
            max_sz = 0
            max_file = None
            for f in files:
                try:
                    sz = Path(f).stat().st_size
                    total += sz
                    if sz > max_sz:
                        max_sz = sz; max_file = f
                except OSError:
                    missing.append((e, Path(f)))
            if max_sz > HEAVY_LIMIT:
                heavy.append((e, max_sz))
            elif total > HEAVY_LIMIT * 2:
                heavy.append((e, total))
            else:
                ok.append((e, total, "dir"))
        else:
            p = Path(str(arquivo)).expanduser()
            # local pode ser com ~ ou absoluto
            q = Path(str(local)).expanduser()
            target = p if p.exists() else q
            if not target.exists():
                missing.append((e, target))
                continue
            try:
                sz = target.stat().st_size
                if sz > HEAVY_LIMIT:
                    heavy.append((e, sz))
                else:
                    ok.append((e, sz, "file"))
            except OSError as ex:
                missing.append((e, target))

    # report — mostra só pasta pai + arquivo (curto)
    if heavy:
        print(f"⚠️  PESADOS >{_hum_size(HEAVY_LIMIT)} ({len(heavy)}):")
        for e, sz in heavy:
            print(f"  - {e['nome']:<20} {_hum_size(sz):>9}  {_short_path(e.get('local'))}")
            print(f"    -> {_hum_size(sz)} — considere comprimir: ffmpeg -i input.mp4 -vf scale=-2:1080 -c:v libx264 -crf 23 -c:a aac -b:a 128k output.mp4")
        print()

    if missing:
        print(f"❌ FALTANDO ({len(missing)}):")
        for e, p in missing:
            print(f"  - {e.get('nome','?'):<20}  {_short_path(p)}  (local: {_short_path(e.get('local'))})")
        print()

    if zero_dir:
        print(f"⚠️  DIRETÓRIO VAZIO ({len(zero_dir)}):")
        for e, p in zero_dir:
            print(f"  - {e['nome']:<20}  {_short_path(p)}")
        print()

    if not heavy and not missing and not zero_dir:
        print("✓ Tudo ok — nenhum vídeo pesado, nenhum arquivo faltando.\n")
    else:
        print(f"Resumo: {len(heavy)} pesados, {len(missing)} faltando, {len(zero_dir)} vazios, {len(ok)} ok.\n")

    # yt buffer
    try:
        from .yt import yt_dir, _yt_total_bytes
        yt_total = _yt_total_bytes()
        print(f"YT buffer: {_hum_size(yt_total)} / {_hum_size(HEAVY_LIMIT)} em {yt_dir()} (WALLP_YT_CACHE_MB={HEAVY_LIMIT//1024//1024})")
        if yt_total > HEAVY_LIMIT:
            print("  ⚠️ buffer acima do limite — rode wallp -x cache para limpar")
        print()
    except Exception:
        pass

    print("Dica: wallp -ps 10  mostra próximos da agenda com tamanho/duração/loop/integro")
    _warn_updates()
    # retorna código 1 se tem pesados/faltando para uso em CI
    if heavy or missing:
        import sys
        # não falha, só avisa; quem quiser pode usar --check estrito
        pass
