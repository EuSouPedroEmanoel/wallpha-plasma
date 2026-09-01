import sys

flags = ("-c", "-n", "-r", "-t", "-m", "-q", "-l", "-rep", "-i", "-v", "-int", "-s", "-y", "-yl", "-a", "-x", "-d", "-log", "-h", "--help", "--init", "-al", "--list", "--al", "-ps", "--ps", "--profile", "--check")
mode_flags = ("-c", "-n", "-r", "-a", "-x", "-d", "--init", "-al", "--list", "--al", "-ps", "--ps", "--profile", "--check")
value_flags = ("-t", "-m", "-q", "-l", "-s", "-y", "-yl")


def parse():
    args = sys.argv[1:]
    opts = {
        "change": False,
        "next": False,
        "random": False,
        "auto": False,
        "stop": False,
        "daemon": False,
        "init": False,
        "log": False,
        "log_lines": None,
        "help": False,
        "list": False,
        "ps": False,
        "ps_count": None,
        "profile": False,
        "target": None,
        "tempo": None,
        "max": None,
        "qtd": None,
        "loop": None,
        "rep": False,
        "images": False,
        "videos": False,
        "integro": False,
        "som": None,
        "yt": None,
        "yt_list": None,
    }
    modes = set()
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            opts["help"] = True
        elif a in ("-ps", "--ps"):
            modes.add("-ps")
            opts["ps"] = True
            # -ps [N] opcional, sem N = só atual (1)
            if i + 1 < len(args) and args[i + 1].isdigit():
                opts["ps_count"] = int(args[i + 1])
                i += 1
            else:
                opts["ps_count"] = 1
        elif a in ("--profile", "--check"):
            modes.add("--profile")
            opts["profile"] = True
        elif a in ("-c", "-n", "-r", "-a", "-x", "-d", "--init", "-al", "--list", "--al"):
            modes.add(a)
            if a == "-c":
                opts["change"] = True
            elif a == "-n":
                opts["next"] = True
            elif a == "-r":
                opts["random"] = True
            elif a == "-a":
                opts["auto"] = True
            elif a == "-x":
                opts["stop"] = True
            elif a == "-d":
                opts["daemon"] = True
            elif a == "--init":
                opts["init"] = True
            elif a in ("-al", "--list", "--al"):
                opts["list"] = True
        elif a == "-log":
            opts["log"] = True
            if i + 1 < len(args) and args[i + 1].isdigit():
                opts["log_lines"] = int(args[i + 1])
                i += 1
        elif a in ("-rep", "-i", "-v", "-int"):
            if a == "-rep":
                opts["rep"] = True
            elif a == "-i":
                opts["images"] = True
            elif a == "-v":
                opts["videos"] = True
            elif a == "-int":
                opts["integro"] = True
        elif a in value_flags:
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                print(f"Erro: {a} precisa de um valor")
                sys.exit(1)
            if a == "-t":
                opts["tempo"] = args[i + 1]
            elif a == "-m":
                opts["max"] = args[i + 1]
            elif a == "-q":
                opts["qtd"] = args[i + 1]
            elif a == "-l":
                opts["loop"] = args[i + 1]
            elif a == "-s":
                opts["som"] = args[i + 1]
            elif a == "-y":
                opts["yt"] = args[i + 1]
            elif a == "-yl":
                opts["yt_list"] = args[i + 1]
            i += 1
        elif a.startswith("-") and a not in flags:
            print(f"Erro: argumento desconhecido '{a}'")
            help()
            sys.exit(1)
        else:
            if opts["target"] is None:
                opts["target"] = a
            else:
                print(f"Erro: mais de um caminho/nome fornecido ('{a}')")
                sys.exit(1)
        i += 1

    if opts["help"]:
        help()
        sys.exit(0)

    if opts["yt"] is not None or opts["yt_list"] is not None:
        opts["random"] = True
        modes.add("-r")

    # ps pode ser combinado com -c/-r/-a (e -n); demais combos continuam exclusivos
    if len(modes) > 1:
        if "-ps" in modes:
            other = modes - {"-ps"}
            if len(other) == 1 and other.issubset({"-c", "-n", "-r", "-a"}):
                pass
            else:
                print("Erro: use apenas um comando por vez (-c, -n, -r, -a, -x, -d, -al, -ps, --profile ou --init) — ps só pode ser combinado com -c, -r ou -a")
                sys.exit(1)
        else:
            print("Erro: use apenas um comando por vez (-c, -n, -r, -a, -x, -d, -al, -ps, --profile ou --init)")
            sys.exit(1)

    if opts["next"] and opts["target"] is not None:
        print("Erro: -n não aceita caminho/nome (use -c para escolher)")
        sys.exit(1)

    if opts["ps"] and opts["target"] is not None and not (opts["change"] or opts["random"] or opts["auto"] or opts["next"]):
        print("Erro: -ps não aceita caminho/nome (use -ps [N] apenas) — com -c/-r/-a use o alvo desses comandos")
        sys.exit(1)

    if opts["profile"] and opts["target"] is not None:
        print("Erro: --profile/--check não aceita caminho/nome")
        sys.exit(1)

    used_values = opts["tempo"] is not None or opts["max"] is not None or opts["qtd"] is not None or opts["loop"] is not None or opts["rep"] or opts["images"] or opts["videos"] or opts["integro"] or opts["som"] is not None
    if used_values and not (opts["random"] or opts["change"]):
        print("Erro: -t, -m, -q, -l, -rep, -i, -v, -int e -s só são válidos com -r ou com -c <lista>")
        sys.exit(1)

    if opts["images"] and opts["videos"]:
        print("Erro: -i (imagens) e -v (vídeos) são mutuamente exclusivos")
        sys.exit(1)

    if opts["som"] is not None and opts["som"].strip().lower() not in ("on", "off"):
        print("Erro: -s aceita apenas on ou off")
        sys.exit(1)

    return opts


def help():
    print("wallp — wallpaper animado/imagem no KDE Plasma")
    print()
    print("Uso:")
    print("  wallp -ps [N]             Mostra wallpaper atual (sem N) ou próximos N da agenda — tamanho, nome, duração, loop, integro (combinável com -c/-r/-a)")
    print("  wallp --profile           Perfil: varre yml e avisa vídeos >500MB, arquivos faltando, yt sem cache")
    print("  wallp --check             Alias para --profile (compat install.sh --check)")
    print("  wallp -al [regex]         Lista wallpapers do yml (filtra por regex no nome/local)")
    print("  wallp -c [caminho|nome]   Troca o wallpaper")
    print("                              caminho = arquivo (vídeo/imagem) ou pasta")
    print("                              nome    = nome definido no yml (item ou lista)")
    print("                              sem nada = próximo wallpaper do yml")
    print("                              lista aceita os mesmos args do -r (slideshow):")
    print("                                -t tempo | -m máx | -q N | -l true|N | -rep")
    print("                                -i (imagens) | -v (vídeos) | -int | -s on|off")
    print("                              sem args: uma passada; -l true: loop até -x;")
    print("                              -l N: N passadas e volta à agenda")
    print("  wallp -n                  Próximo wallpaper do yml")
    print("  wallp -r [dir] [-t tempo] Modo aleatório (slideshow embaralhado)")
    print("                              dir = pasta (recursivo) ou arquivo (usa a pasta dele)")
    print("                              sem dir = varre a pasta pessoal (~) inteira (subpastas)")
    print("                              -i       = só imagens | -v = só vídeos")
    print("                              -t tempo = intervalo (padrão 30m)")
    print("                              -m tempo = máximo de duração (padrão 1h)")
    print("                              -q N     = quantidade de wallpapers a mostrar")
    print("                              -l true  = loop infinito (não aceita -m nem -q)")
    print("                              -l N     = N passadas na fila e volta à agenda")
    print("                                         (também não aceita -m nem -q)")
    print("                              -rep     = vídeos repetem a reprodução (loop playback)")
    print("                              -int     = vídeo toca inteiro; com -t, se terminar antes")
    print("                                        fica no último frame até o tempo (com -rep,")
    print("                                        repete até completar o tempo; imagem usa 30m)")
    print("                              -s on|off= vídeo com som ou mudo (padrão off)")
    print("                              ao terminar, volta para a agenda do yml (-a)")
    print("                              roda no daemon; Ctrl+C não fecha — pare com -x")
    print("  wallp -y <link>            Baixa um vídeo do YouTube e roda o modo aleatório")
    print("                              só com ele (aceita -t, -m, -q, -l, -rep, -int, -s)")
    print("                              fica num buffer em RAM (tmpfs /run/user/<uid>/wallp, limite 500MB LRU, env WALLP_YT_CACHE_MB); o sistema limpa no logout")
    print("  wallp -yl <playlist>       Baixa playlist do YouTube como lista e roda embaralhada")
    print("                              sem baixar tudo de uma vez (cache LRU 500MB, baixa sob demanda)")
    print("                              aceita os mesmos -t, -m, -q, -l, -rep, -int, -s que -y/-r")
    print("  wallp -a [nome]           Ativa o modo automático")
    print("                              sem nome = agenda completa do yml")
    print("                              com nome = igual -c <nome> mas persistente até -x")
    print("                              (lista usa o campo loop do yml; item único fica)")
    print("  wallp -x                  Desativa o modo automático/aleatório e esvazia o buffer do YouTube (500MB LRU)")
    print("  wallp -x cache            Limpa só o buffer do YouTube (tmpfs), sem parar o daemon")
    print("  wallp -log [N]            Logs do daemon (em /tmp/wallp.log, apagado no boot)")
    print("                              sozinho: mostra as últimas N linhas (padrão 50)")
    print("                              junto de -a/-r/-c/-n/-x: roda o comando e segue")
    print("                              o log (como tail -f, mostrando N linhas)")
    print("  wallp -ps                 Wallpaper atual (tamanho/duração/loop/integro, arquivo = dir/arquivo)")
    print("  wallp -ps 5               Próximos 5 da agenda")
    print("  wallp -ps -c <nome>       Troca e mostra o atual (ps combinável com -c/-r/-a)")
    print("  wallp --profile           Avisa pesados >500MB e faltando")
    print("  wallp -h                  Mostra esta ajuda")
    print("  wallp --init              Cria um wallp.yml de exemplo")
    print()
    print("Yml padrão: ~/.config/wallp/wallp.yml")
    print("  - nome:    nome usado no -c")
    print("  - local:   caminho do wallpaper (vídeo, imagem ou pasta)")
    print("  - type:    diretório (opcional) — tempo = intervalo entre os arquivos")
    print("  - loop:    true/N/false (opcional) — diretório/lista: true cicla infinito,")
    print("             N cicla N vezes e termina, false mostra 1x; em vídeo/youtube:")
    print("             true trava o playback em loop infinito (não pode ter tempo junto)")
    print("  - shuffled: true (opcional) — diretório em ordem aleatória (muda à meia-noite)")
    print("  - hora:    HH:MM, '9h', '9h30m' ou range '9h-10h' (sem range, exige tempo)")
    print("  - tempo:   duração ativo: 30m, 2h, 1d, 1h30m10s")
    print("  - dia:     só roda em dias específicos:")
    print("               seg|ter|qua|qui|sex|sab|dom = toda semana nesse dia")
    print("               N (1-31)                    = todo dia N do mês")
    print("               DD-MM                       = todo ano nesse dia (ex.: 01-04)")
    print("               DD-MM-AAAA                  = só nesse dia (ex.: 20-12-2026)")
    print("               sem dia = todos os dias")
    print("  - default: true (opcional) — o padrão, preenche os intervalos vazios.")
    print("             -a exige um default global (default: true sem dia)")
    print("  - list:    lista de sub-itens (opcional) — cada sub-item é um wallpaper")
    print("             completo. Com hora/tempo na lista: item único que cicla os")
    print("             sub-itens; sem: os sub-itens entram direto na agenda (grupo).")
    print("             Aceita listas dentro de listas; subs sem dia herdam o da lista")
    print("             -c <nome> roda a lista; -a <nome> roda persistente")
    print("  - repetir: true (opcional) — o vídeo repete a reprodução (loop playback)")
    print("             só até o tempo do item acabar (não ignora o tempo). Para travar")
    print("             um vídeo infinitamente use loop: true (sem tempo)")
    print("  - som:     true/false (opcional) — vídeo com som (padrão false = mudo)")
    print("  - integro: true (opcional) — vídeo toca inteiro; com tempo, se terminar antes")
    print("             fica no último frame até o tempo acabar; repetir: true faz repetir")
    print("             até completar o tempo. Em diretório sem tempo, troca quando o")
    print("             vídeo termina (sem repetir)")
    print()
    print("Exemplos:")
    print("  wallp -c ~/Vídeos/Wallpaper/manha.mp4")
    print("  wallp -c celeste")
    print("  wallp -n")
    print("  wallp -r -t 30m")
    print("  wallp -r ~/Vídeos/Wallpaper -t 2h -m 6h")
    print("  wallp -r -i -t 30m")
    print("  wallp -r -v -s on -t 30m")
    print("  wallp -r -v -int -q 10")
    print("  wallp -r -v -int -t 1m -rep   (vídeo curto repete até completar 1m)")
    print("  wallp -r -q 10 -t 15m")
    print("  wallp -r -l true -t 30m")
    print("  wallp -r -l 3 -t 30m           (3 passadas na fila e volta à agenda)")
    print("  wallp -r -rep -t 30m")
    print("  wallp -y https://youtu.be/xyz -s on -l true")