/*
 * wallp Wallpaper — plasmóide unificado imagem + vídeo, KDE Plasma 6
 * Leve: sem painel de config, sem blur/crossfade/effects. Compat com
 *  - org.kde.image (Image)
 *  - luisbocanegra.smart.video.wallpaper.reborn (VideoUrls)
 *  + Source unificado file:// (preferido pelo wallp-cli novo)
 *
 * wallp-cli manda via D-Bus org.kde.PlasmaShell.setWallpaper("com.wallp.wallpaper", {Image, Source, VideoUrls, MuteMode, Volume, Loop, FillMode})
 */

import QtQuick
import QtMultimedia
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root
    anchors.fill: parent

    // ——— props wallp ———
    property string cfgSource: wallpaper.configuration.Source || ""
    property string cfgImage: wallpaper.configuration.Image || ""
    property string cfgVideoUrls: wallpaper.configuration.VideoUrls || "[]"
    property int cfgMuteMode: wallpaper.configuration.MuteMode // 5=mudo (padrão wallp), 4=som
    property double cfgVolume: wallpaper.configuration.Volume !== undefined ? wallpaper.configuration.Volume : 1.0
    property bool cfgLoop: wallpaper.configuration.Loop || false
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
        // só toca quando é vídeo
        source: isVideo ? resolvedSrc : ""
        loops: cfgLoop ? MediaPlayer.Infinite : 1
        playbackRate: 1.0
        videoOutput: videoOut
        audioOutput: audioOut
        onErrorOccurred: function(error, errorString) {
            console.warn("wallp: video error", error, errorString, resolvedSrc);
        }
    }

    AudioOutput {
        id: audioOut
        muted: cfgMuteMode === 5 // wallp: 5=mudo, 4=som (compat Reborn)
        volume: cfgVolume
    }

    VideoOutput {
        id: videoOut
        anchors.fill: parent
        visible: isVideo
        fillMode: cfgFillMode === 0 ? VideoOutput.Stretch
                 : cfgFillMode === 1 ? VideoOutput.PreserveAspectFit
                 : VideoOutput.PreserveAspectCrop
    }

    // controla play/pause por visibilidade + troca de source
    onIsVideoChanged: {
        if (isVideo) {
            if (resolvedSrc) player.play();
        } else {
            player.stop();
        }
    }
    onResolvedSrcChanged: {
        if (isVideo && resolvedSrc) {
            // troca de wallpaper: stop + play garante reload mesmo se URI igual com query diferente
            player.stop();
            // QtMultimedia atualiza source via binding acima, dá um tick
            Qt.callLater(function() { if (isVideo) player.play(); });
        }
    }

    // pausa quando não visível (lock screen / desktop não ativo) — mais leve que monitorar janelas
    onVisibleChanged: {
        if (!visible) {
            if (isVideo) player.pause();
        } else {
            if (isVideo && resolvedSrc) player.play();
        }
    }

    Component.onCompleted: {
        if (isVideo && resolvedSrc) player.play();
    }

    // debug leve: plasmashell --replace ou journalctl --user -f | grep wallp
    // console.log("wallp: src", resolvedSrc, "isVideo", isVideo, "loop", cfgLoop, "mute", cfgMuteMode)
}
