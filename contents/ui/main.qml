/*
 * wallpha Wallpaper — plasmóide unificado imagem + vídeo, KDE Plasma 6
 * Leve: sem painel de config, sem blur/crossfade/effects. Compat com
 *  - org.kde.image (Image)
 *  - luisbocanegra.smart.video.wallpaper.reborn (VideoUrls)
 *  + Source unificado file:// (preferido pelo wallpha-cli novo)
 *
 * wallpha-cli manda via D-Bus org.kde.PlasmaShell.setWallpaper("com.wallpha.wallpaper", {Image, Source, VideoUrls, MuteMode, Volume, Loop, Paused, FillMode})
 */

import QtQuick
import QtMultimedia
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root
    anchors.fill: parent

    // ——— props wallpha ———
    property string cfgSource: wallpaper.configuration.Source || ""
    property string cfgImage: wallpaper.configuration.Image || ""
    property string cfgVideoUrls: wallpaper.configuration.VideoUrls || "[]"
    property int cfgMuteMode: wallpaper.configuration.MuteMode // 5=mudo (padrão wallpha), 4=som
    property double cfgVolume: wallpaper.configuration.Volume !== undefined ? wallpaper.configuration.Volume : 1.0
    property bool cfgLoop: wallpaper.configuration.Loop || false
    property bool cfgPaused: wallpaper.configuration.Paused === true || wallpaper.configuration.Paused === 1
    property int cfgFillMode: wallpaper.configuration.FillMode !== undefined ? wallpaper.configuration.FillMode : 2 // PreserveAspectCrop
    property string cfgBg: wallpaper.configuration.BackgroundColor || "#000000"

    // ——— resolve source unificado ———
    function pickVideoFromJson(jsonStr) {
        try {
            var arr = JSON.parse(jsonStr);
            if (Array.isArray(arr) && arr.length > 0) {
                for (var i = 0; i < arr.length; i++) {
                    var v = arr[i];
                    if (v && v.enabled !== false && v.filename) return v.filename;
                }
                if (arr[0] && arr[0].filename) return arr[0].filename;
            }
        } catch (e) {}
        return "";
    }

    property string resolvedSrc: {
        if (cfgSource && cfgSource.length > 0) return cfgSource;
        var fromJson = pickVideoFromJson(cfgVideoUrls);
        if (fromJson && fromJson.length > 0) return fromJson;
        return cfgImage;
    }

    property bool isVideo: {
        if (!resolvedSrc) return false;
        var s = resolvedSrc.toLowerCase();
        // cobre file:// e path cru
        return s.endsWith(".mp4") || s.endsWith(".mkv") || s.endsWith(".webm")
            || s.endsWith(".mov") || s.endsWith(".avi") || s.endsWith(".m4v")
            || s.endsWith(".mpeg") || s.endsWith(".mpg") || s.endsWith(".ogv") || s.endsWith(".ogg");
    }

    // A source is applied imperatively.  Binding MediaPlayer.source directly to
    // the configuration races QtMultimedia's teardown/reload path and can leave
    // a VideoOutput permanently black after a wallpaper change.
    property string pendingVideoSource: ""
    property bool videoPlaying: false
    // Indica que o backend já entregou pelo menos um frame. É separado de
    // videoPlaying para que a pausa mantenha o último frame congelado.
    property bool videoHasFrame: false

    function playerLog(message) {
        console.log("wallpha: player", message);
    }

    function canPlayVideo() {
        return visible && isVideo && pendingVideoSource !== "";
    }

    function queueVideoReload(reason) {
        playerLog("reload queued (" + reason + "): " + (isVideo ? resolvedSrc : "no video"));
        startupWatch.stop();
        player.stop();
        player.source = "";
        videoPlaying = false;
        videoHasFrame = false;
        pendingVideoSource = isVideo ? resolvedSrc : "";
        if (pendingVideoSource !== "" && visible)
            reloadTimer.restart();
    }

    function ensureVideoPlayback(reason) {
        if (!canPlayVideo() || cfgPaused || player.source === "")
            return;
        if (player.mediaStatus === MediaPlayer.InvalidMedia) {
            console.warn("wallpha: refusing invalid media:", player.source);
            return;
        }
        if (player.playbackState !== MediaPlayer.PlayingState) {
            playerLog("play (" + reason + "), status=" + player.mediaStatus);
            player.play();
        }
    }

    // KConfigPropertyMap nem sempre emite notify individual para uma chave
    // alterada por PlasmaShell.setWallpaper. Leia Paused diretamente quando a
    // configuração inteira mudar para que -p seja uma pausa efetiva.
    function syncPausedFromConfiguration(reason) {
        var value = wallpaper.configuration.Paused;
        var paused = value === true || value === 1 || String(value).toLowerCase() === "true";
        if (!isVideo)
            return;
        if (paused) {
            startupWatch.stop();
            reloadTimer.stop();
            player.pause();
            videoPlaying = false;
            playerLog("paused by configuration (" + reason + ")");
        } else {
            ensureVideoPlayback("configuration resumed (" + reason + ")");
        }
    }

    // ——— fundo ———
    Rectangle {
        anchors.fill: parent
        color: cfgBg
    }

    // ——— imagem ———
    Image {
        id: img
        anchors.fill: parent
        visible: !isVideo && resolvedSrc !== ""
        source: !isVideo ? resolvedSrc : ""
        fillMode: cfgFillMode === 0 ? Image.Stretch
                 : cfgFillMode === 1 ? Image.PreserveAspectFit
                 : cfgFillMode === 6 ? Image.Tile
                 : Image.PreserveAspectCrop // 2 = default KDE
        cache: false
        asynchronous: true
        smooth: true
        // evita warn de source vazio
        sourceSize.width: width * Screen.devicePixelRatio
        sourceSize.height: height * Screen.devicePixelRatio
    }

    // ——— vídeo leve ———
    // QtMultimedia 6 precisa de VideoOutput separado + MediaPlayer + AudioOutput
    MediaPlayer {
        id: player
        // source is assigned by reloadTimer after stop() and one event-loop tick
        loops: cfgLoop ? MediaPlayer.Infinite : 1
        playbackRate: 1.0
        videoOutput: videoOut
        audioOutput: audioOut
        onErrorOccurred: function(error, errorString) {
            videoPlaying = false;
            videoHasFrame = false;
            console.warn("wallpha: video error", error, errorString, source);
        }
        onSourceChanged: {
            playerLog("source=" + source);
        }
        onMediaStatusChanged: {
            playerLog("media status=" + mediaStatus + ", source=" + source);
            if (mediaStatus === MediaPlayer.LoadedMedia
                    || mediaStatus === MediaPlayer.BufferingMedia
                    || mediaStatus === MediaPlayer.BufferedMedia
                    || mediaStatus === MediaPlayer.EndOfMedia)
                ensureVideoPlayback("media status changed");
        }
        onPlaybackStateChanged: {
            videoPlaying = playbackState === MediaPlayer.PlayingState;
            if (videoPlaying)
                videoHasFrame = true;
            playerLog("playback state=" + playbackState + ", status=" + mediaStatus);
        }
    }

    AudioOutput {
        id: audioOut
        muted: cfgMuteMode === 5 // wallpha: 5=mudo, 4=som (compat Reborn)
        volume: cfgVolume
    }

    VideoOutput {
        id: videoOut
        anchors.fill: parent
        // Do not cover the configured background until Qt confirms playback.
        // This makes loading/failure visibly deterministic instead of a black
        // surface and still keeps the video above the background once running.
        visible: isVideo && videoHasFrame
        fillMode: cfgFillMode === 0 ? VideoOutput.Stretch
                 : cfgFillMode === 1 ? VideoOutput.PreserveAspectFit
                 : VideoOutput.PreserveAspectCrop
    }

    Timer {
        id: reloadTimer
        interval: 80
        repeat: false
        onTriggered: {
            if (!root.visible || !root.isVideo || root.pendingVideoSource === "")
                return;
            player.source = root.pendingVideoSource;
            root.playerLog("loading source after initialization delay: " + player.source);
            root.ensureVideoPlayback("initial source assignment");
            startupWatch.restart();
        }
    }

    // One diagnostic/retry after the backend had time to load.  Do not loop
    // endlessly: a decoder failure is reported through onErrorOccurred.
    Timer {
        id: startupWatch
        interval: 3000
        repeat: false
        onTriggered: {
            if (!root.cfgPaused && root.canPlayVideo() && player.playbackState !== MediaPlayer.PlayingState) {
                console.warn("wallpha: video did not enter PlayingState; status=",
                             player.mediaStatus, "source=", player.source);
                root.ensureVideoPlayback("startup watchdog");
            }
        }
    }

    Connections {
        target: wallpaper
        function onConfigurationChanged() {
            root.syncPausedFromConfiguration("configurationChanged");
        }
    }

    // controla play/pause por visibilidade + troca de source
    onIsVideoChanged: {
        queueVideoReload("media type changed");
    }
    onResolvedSrcChanged: {
        queueVideoReload("source changed");
    }
    onCfgPausedChanged: {
        syncPausedFromConfiguration("Paused changed");
        if (!cfgPaused && player.source === "" && pendingVideoSource !== "")
            reloadTimer.restart();
    }

    // pausa quando não visível (lock screen / desktop não ativo) — mais leve que monitorar janelas
    onVisibleChanged: {
        if (!visible) {
            reloadTimer.stop();
            startupWatch.stop();
            if (isVideo) player.pause();
        } else {
            if (isVideo && pendingVideoSource !== "") {
                if (player.source === "") reloadTimer.restart();
                else ensureVideoPlayback("became visible");
            }
        }
    }

    Component.onCompleted: {
        queueVideoReload("component completed");
    }

    // debug leve: plasmashell --replace ou journalctl --user -f | grep wallpha
    // console.log("wallpha: src", resolvedSrc, "isVideo", isVideo, "loop", cfgLoop, "mute", cfgMuteMode)
}
