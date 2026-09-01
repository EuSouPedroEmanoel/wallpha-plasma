from datetime import timedelta
from pathlib import Path
import yaml
from . import log
from .media import VIDEO_EXTS, day_shuffled, get_salt, list_dir_files, list_tree_files, match_tipo
from .parse import DEFAULT_TEMPO, _dia_rank, fmt_dia, is_loop_n, matches_day, parse_dia, parse_hora, parse_loop, parse_tempo
from .paths import DEFAULT_CONFIG
LISTAS = {}
TEMPLATE = """\
# wallp — agenda de wallpapers
# cada item tem:
#   nome:    nome (usado no `wallp -c <nome>`)
#   local:   caminho do wallpaper (vídeo, imagem ou pasta com type: diretório)
#   type:    diretório (opcional) — local é uma pasta; tempo = intervalo entre arquivos
#   loop:    true/N/false (opcional) — diretório/lista: true cicla infinito, N cicla
#            N vezes e termina, false mostra 1x; em vídeo/youtube: true trava o
#            playback em loop infinito (não pode ter tempo junto)
#   hora:    HH:MM, "9h", "9h30m" ou range "9h-10h" (opcional)
#            sem range, exige a tag tempo (fim = início + tempo)
#   tempo:   duração ativo: 30m, 2h, 1d, 1h30m10s (opcional)
#   dia:     (opcional) só roda em dias específicos:
#              seg|ter|qua|qui|sex|sab|dom  = toda semana nesse dia
#              N (1-31)                      = todo dia N do mês
#              DD-MM                         = todo ano nesse dia (ex.: 01-04)
#              DD-MM-AAAA                    = só nesse dia (ex.: 20-12-2026)
#            sem dia, vale todos os dias
#   default: true (opcional) — o padrão, preenche os intervalos vazios.
#            Precisa de um default global (sem dia) pra rodar `wallp -a`;
#            defaults com `dia` valem só no dia deles (o mais específico vence).
#   shuffled: true (opcional, em diretórios) — ordem aleatória (mesma o dia todo,
#            muda à meia-noite; o sorteio usa um salt em shuffle.json)
#   list:    lista de sub-itens (opcional) — cada sub-item é um wallpaper completo
#            (nome/local/type/tempo/hora/dia...). Com hora/tempo na lista, ela vira um
#            item da agenda que cicla os sub-itens; sem, os sub-itens entram direto
#            na agenda (a lista é só o nome do grupo). Listas podem ter listas dentro
#            (sub-item com `list:`); subs sem `dia` herdam o `dia` da lista.
#            `wallp -c <nome-da-lista>` roda só a lista; `wallp -a <nome>` roda ela
#            persistente.
#   No dia: rotação sem hora do dia mais específico roda primeiro; se terminar (sem
#   loop), segue pro genérico e depois pros defaults, até o default global.
#   repetir: true (opcional) — o vídeo repete a reprodução (loop de playback)
#            até o tempo do item acabar (não ignora o tempo)
#   som: true/false (opcional) — vídeo com som (padrão false = mudo)
#   integro: true (opcional) — o vídeo toca inteiro; com tempo, se terminar antes fica
#            no último frame até o tempo acabar; repetir: true faz repetir até completar
#            o tempo. Em diretório, tempo vira opcional e a troca é quando o vídeo
#            termina (sem repetir)
- nome: manha
  type: diretório
  local: ~/Vídeos/Wallpaper
  tempo: 30m
  loop: true
  shuffled: true
  integro: true
  som: true
  hora: "8h-11h"

- nome: tarde
  local: ~/Vídeos/Wallpaper/sem título.mp4
  tempo: 2h

- nome: padrao
  local: ~/Vídeos/Wallpaper/Celeste Animated Wallpaper - Farewell.mp4
  default: true

# exemplo de lista (agrupamento: sub-itens entram na agenda com as horas deles)
# - nome: Lista de exemplo
#   list:
#     - nome: manha
#       type: diretório
#       local: ~/Vídeos/Wallpaper
#       tempo: 30m
#       loop: true
#       shuffled: true
#       hora: "8h-11h"
#     - nome: tarde
#       type: diretório
#       local: ~/Vídeos/Wallpaper
#       tempo: 30m
#       loop: true
#       shuffled: true
#       hora: "12h-18h"
"""


def init_template(path=None):
    path = Path(path or DEFAULT_CONFIG)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    path.write_text(TEMPLATE, encoding="utf-8")
    return True


def load(path=None):
    path = Path(path or DEFAULT_CONFIG)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or []
    return load_entries(raw)


def load_checked(path=None):
    """Carrega o yml; em erro de validação/YAML, loga e retorna None."""
    try:
        return load(path) if path is not None else load()
    except Exception as e:
        log.err(str(e))
        return None


def load_entries(raw):
    global LISTAS
    if not isinstance(raw, list):
        raise ValueError("o yml deve ser uma lista de wallpapers")
    LISTAS = {}
    entries = []
    globals_dflt = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        if item.get("list") is not None:
            nome_lista = str(item.get("nome") or "").strip()
            lista = _build_list(item, nome_lista)
            LISTAS[nome_lista or f"lista{len(LISTAS) + 1}"] = lista
            for sub in _expand_list(lista):
                entries.append(sub)
                if sub["default"] and sub.get("dia") is None:
                    globals_dflt += 1
            continue
        if not item.get("local"):
            continue
        entries.append(_normalize(item))
        if entries[-1]["default"] and entries[-1].get("dia") is None:
            globals_dflt += 1
    if globals_dflt > 1:
        log.err("mais de um default global (default: true sem dia); usando o primeiro")
    return entries


def _build_list(item, nome, inherited_dia=None):
    """Normaliza recursivamente um item com `list:`.
    Lista com hora/tempo/default = unidade (um slot); sem = agrupamento (subs na agenda).
    Subs sem `dia` herdam o `dia` da lista; o próprio vence.
    Listas aninhadas: unidade vira sub-item; agrupamento achata os subs no nível acima."""
    raw = item["list"]
    if not isinstance(raw, list):
        raise ValueError(f"campo 'list' de '{nome}' deve ser uma lista de wallpapers")
    hora_start, hora_end = parse_hora(item.get("hora"))
    raw_tempo = item.get("tempo")
    tempo = parse_tempo(raw_tempo)
    loop = parse_loop(item.get("loop", False))
    shuffled = bool(item.get("shuffled", False))
    dia_raw = item.get("dia")
    if dia_raw is None and inherited_dia is not None:
        dia = inherited_dia
    else:
        dia = parse_dia(dia_raw)
    is_default = bool(
        item.get("default") or item.get("padrao") or item.get("padrão") or item.get("type") == "default"
    )
    if is_default and hora_start is not None:
        raise ValueError(f"lista default '{nome}' não pode ter hora")

    subs = []
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            continue
        if s.get("list") is not None:
            sub_nome = str(s.get("nome") or f"{nome}#{i + 1}").strip()
            sub_lista = _build_list(s, sub_nome, dia)
            if sub_lista["hora_start"] is not None or sub_lista["tempo"] is not None or sub_lista["default"]:
                subs.append(sub_lista)
            else:
                subs.extend(sub_lista["sub_entries"])
            continue
        if not s.get("local"):
            continue
        s2 = dict(s)
        if tempo is not None and s2.get("tempo") is None and s2.get("hora") is None and not (
            s2.get("default") or s2.get("padrao") or s2.get("padrão")
        ):
            s2["tempo"] = raw_tempo
        if s2.get("dia") is None:
            sub = _normalize(s2, dia)
        else:
            sub = _normalize(s2)
        if not sub["nome"]:
            sub["nome"] = f"{nome}#{i + 1}"
        subs.append(sub)

    if not subs:
        raise ValueError(f"lista '{nome}' sem itens válidos")

    lista = {
        "nome": nome,
        "local": None,
        "default": is_default,
        "is_dir": False,
        "is_yt": False,
        "is_list": True,
        "hora_start": hora_start,
        "hora_end": hora_end,
        "tempo": tempo,
        "loop": loop,
        "shuffled": shuffled,
        "repetir": False,
        "som": None,
        "integro": False,
        "dia": dia,
        "files": None,
        "file_index": 0,
        "arquivo": None,
        "sub_entries": subs,
        "sub_index": 0,
        "sub_nome": None,
    }
    return lista


def _expand_list(lista):
    """Unidade vira 1 entry; agrupamento achata os sub-itens (recursivo)."""
    if lista["hora_start"] is not None or lista["tempo"] is not None or lista["default"]:
        return [lista]
    out = []
    for s in lista["sub_entries"]:
        if s.get("is_list"):
            out += _expand_list(s)
        else:
            out.append(s)
    return out


def find_list(nome):
    """Lista registrada por nome (do `list:` no yml)."""
    return LISTAS.get(str(nome).strip())


def _normalize(item, dia_override=None):
    """Normaliza um wallpaper (arquivo/diretório/youtube).
    dia_override: `dia` já parseado herdado da lista (próprio item vence)."""
    raw_local = str(item["local"]).strip()
    raw_type = str(item.get("type") or "").strip().lower()
    is_yt = raw_type in ("youtube", "yt")
    is_yt_list = raw_type in ("youtube-list", "yt-list", "youtubelist", "youtube_list", "yt_playlist")
    if is_yt_list:
        is_yt = True
    local = raw_local if (is_yt or is_yt_list) else str(Path(raw_local).expanduser())
    p = Path(local)
    nome = str(item.get("nome") or p.stem).strip()
    is_default = bool(
        item.get("default") or item.get("padrao") or item.get("padrão") or item.get("type") == "default"
    )
    raw_type = str(item.get("type") or "").strip().lower()
    is_dir = (not is_yt) and (raw_type in ("diretório", "diretorio", "directory") or p.is_dir())
    shuffled = bool(item.get("shuffled", False))
    repetir = bool(item.get("repetir") or item.get("repeat", False))
    som = bool(item.get("som") or item.get("som") or item.get("sound", False))
    integro = bool(item.get("integro") or item.get("integrado") or item.get("integred", False))
    hora_start, hora_end = parse_hora(item.get("hora"))
    tempo = parse_tempo(item.get("tempo"))
    loop = parse_loop(item.get("loop", False))
    dia = dia_override if dia_override is not None else parse_dia(item.get("dia"))

    e = {
        "nome": nome,
        "local": local,
        "default": is_default,
        "is_dir": is_dir,
        "is_yt": is_yt,
        "is_yt_list": is_yt_list,
        "is_list": False,
        "hora_start": hora_start,
        "hora_end": hora_end,
        "tempo": tempo,
        "loop": loop,
        "shuffled": shuffled,
        "repetir": repetir,
        "som": som,
        "integro": integro,
        "dia": dia,
        "files": None,
        "file_index": 0,
        "arquivo": local,
    }

    if is_default and hora_start is not None:
        raise ValueError(f"wallpaper default '{nome}' não pode ter hora")
    is_video = is_yt or p.suffix.lower() in VIDEO_EXTS
    if not is_dir and is_video and loop and tempo is not None:
        raise ValueError(
            f"vídeo '{nome}' não pode ter loop e tempo juntos — loop trava o vídeo infinitamente"
        )
    if hora_start is not None and hora_end is None and tempo is None and not (is_dir and integro) and not loop:
        raise ValueError(f"hora '{item['hora']}' sem range exige a tag tempo ('{nome}')")
    if is_yt:
        if hora_start is None and tempo is None and not is_default and not loop and not integro:
            raise ValueError(f"youtube '{nome}' precisa de hora, tempo ou default")
    elif is_dir:
        files = list_dir_files(local)
        if not files:
            raise ValueError(f"diretorio sem mídia ou inexistente: {local}")
        if tempo is None and not integro:
            raise ValueError(f"diretorio '{nome}' precisa da tag tempo")
        if integro:
            only = [f for f in files if match_tipo(f, "video")]
            if not only:
                raise ValueError(f"diretorio integro '{nome}' não tem vídeos")
        if shuffled:
            files = day_shuffled(files, get_salt())
        e["files"] = files
        e["arquivo"] = files[0]
    else:
        if hora_start is None and tempo is None and not is_default and not loop:
            raise ValueError(f"arquivo '{nome}' precisa de hora, tempo ou default")
    return e


def _dir_tempo(e):
    """Tempo de um diretório: o do yml, ou 30m de estimativa se integro sem tempo."""
    return e["tempo"] or parse_tempo(DEFAULT_TEMPO)


def _sub_dur(s, e):
    """Tempo de um sub-item de lista: o dele, ou o da lista, ou 30m."""
    return s["tempo"] or e["tempo"] or parse_tempo(DEFAULT_TEMPO)


def _list_total(e, day=None):
    """Duração total de uma lista = soma dos tempos dos sub-itens.
    Com `day`, só os sub-itens ativos naquele dia contam (os outros somem)."""
    subs = e["sub_entries"]
    if day is not None:
        subs = [s for s in subs if matches_day(s, day)] or subs
    return sum((_sub_dur(s, e) for s in subs), timedelta(0))


def _sub_index(subs, sub):
    return next((i for i, s in enumerate(subs) if s["nome"] == sub["nome"] and s["local"] == sub["local"]), 0)


def _apply_sub(out, sub):
    for k in ("local", "is_dir", "is_yt", "files", "file_index", "arquivo", "repetir", "som", "integro", "tempo", "shuffled", "dia", "loop"):
        out[k] = sub[k]
    return out


def format_entry(e):
    hora = ""
    if e["hora_start"] is not None:
        hora = f", hora={e['hora_start'].strftime('%H:%M')}"
        if e["hora_end"] is not None:
            hora += f"-{e['hora_end'].strftime('%H:%M')}"
    tempo = f", tempo={e['tempo']}" if e["tempo"] else ""
    dia = f", dia={fmt_dia(e.get('dia'))}" if e.get("dia") else ""
    dft = ", default" if e["default"] else ""
    shf = ", shuffled" if e.get("shuffled") else ""
    rep = ", repetir" if e.get("repetir") else ""
    snd = ", som" if e.get("som") else ""
    itg = ", integro" if e.get("integro") else ""
    _loop = e.get("loop")
    lp = ", loop" if _loop is True else (f", loop={_loop}" if is_loop_n(_loop) else "")
    if e.get("is_list"):
        sub = f"/{e['sub_nome']}" if e.get("sub_nome") else f" [{len(e.get('sub_entries') or [])} itens]"
        arq = e["arquivo"] or e["local"] or ""
        return f"{e['nome']}{sub} -> {arq}{hora}{tempo}{dia}{shf}{lp}{rep}{snd}{itg}{dft}"
    arq = e["arquivo"] if e["is_dir"] else e["local"]
    if e["is_yt"]:
        arq = e["local"]
        itg = ""
        return f"{e['nome']} -> {arq}{hora}{tempo}{dia}{lp}{rep}{snd}{dft}"
    return f"{e['nome']} -> {arq}{hora}{tempo}{dia}{shf}{lp}{rep}{snd}{itg}{dft}"


def list_media_queue(lista, tipo=None):
    """Arquivos de mídia de uma lista (achata sub-diretórios e sub-listas recursivamente)."""
    files = []
    for s in lista.get("sub_entries") or []:
        if s.get("is_list"):
            files += list_media_queue(s, tipo)
            continue
        if s["is_yt"]:
            continue
        if s["is_dir"]:
            files += [f for f in list_tree_files(s["local"]) if match_tipo(f, tipo)]
        elif match_tipo(s["local"], tipo):
            files.append(s["local"])
    return files


def check_global_default(entries):
    """Valida o default global do -a: exatamente 1 item default sem `dia`."""
    globals_dflt = [e for e in entries if e["default"] and e.get("dia") is None]
    if not globals_dflt:
        raise ValueError("o yml precisa de um default global (default: true sem dia) para rodar -a")
    if len(globals_dflt) > 1:
        raise ValueError("só pode haver um default global (default: true sem dia)")
