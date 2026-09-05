# Changelog

## 2.2.0 — 2026-09-05

Pedimos desculpas: as versões anteriores ainda não eram compatíveis de forma confiável com vídeos no motor nativo. Esta versão corrige a reprodução de vídeos, elimina a tela preta após trocas de mídia, mantém o último frame durante a pausa e estabiliza loop, áudio e retomada da agenda.

### Destaques

- `wallp`/`wallpha -c -p` alterna play/pause do vídeo atual.
- O estado `Paused` é persistido e enviado ao plug-in nativo via D-Bus.
- O último frame permanece visível durante a pausa.
- Ajustes de loop, áudio, duração e mídia respeitam o ciclo atual.
- URI de vídeos com espaços e caracteres acentuados é tratada corretamente.

