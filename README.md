# AutoClick Pro

Automatizador "faz tudo" pra Windows. Clica, digita, espera, decide, encadeia ações — tudo sem código, com gravador visual e editor de macros.

**Grátis. Sem login. Sem nuvem. Sem propaganda.**

---

## ✨ Features principais

- **🖱 AutoClick** — clicks automáticos em posição fixa, no cursor ou em sequência. Burst, humanização, jitter, "modo janela" (clica numa janela sem mover o cursor real).
- **⌨ AutoKeyboard** — digita texto repetidamente. Aceita Unicode (acentos, emoji), tokens (`{ENTER}`, `{F1}`), modo paste (Ctrl+V), intervalo aleatório.
- **🤖 Macro Editor** — sequência visual de ações. 18+ tipos: click, drag, type, wait, wait_image, scroll, key_press, pixel_check, image_click, **click_text (OCR)**, ocr_read, set_var, call_macro, if/else/endif.
- **⏺ Gravador** — aperta F10, faz suas ações, F10 de novo. Vira macro editável.
- **✨ Hotstrings** — atalhos de texto que expandem em qualquer app (`:mail:` → seu email).
- **📡 Monitoramento via Celular** — alertas e controle remoto via [ntfy.sh](https://ntfy.sh). Pareie via QR code, mande `/run`, `/stop`, `/screen`, `/status` etc do celular.
- **🎯 Stop Conditions** — para automaticamente se uma imagem aparece / pixel bate cor / variável atinge valor.
- **💾 3 slots de perfis** + export/import JSON.
- **🌗 Tema escuro/claro**, tray icon, fullscreen, hotkeys globais.

---

## 🎮 Funciona em jogos (incluindo Roblox)

Usa `SendInput` com scan codes — passa pelo Raw Input do Roblox e outros jogos AAA que filtram inputs sintéticos. Modo "janela alvo" permite clicar numa janela específica sem perder foco da janela ativa.

---

## 📥 Instalação (Windows)

1. Baixe o ZIP da [release mais recente](../../releases).
2. Extraia em qualquer pasta.
3. Rode `instalar.bat` — ele baixa Python e Tesseract OCR automaticamente se faltarem, e cria o atalho na área de trabalho.
4. Pronto. Abra pelo atalho.

> Detecta versão anterior e oferece upgrade preservando seus perfis salvos.

---

## ⌨ Hotkeys globais (padrão)

| Tecla | Ação |
|-------|------|
| `F6`  | Liga/desliga AutoClick |
| `F7`  | Liga/desliga AutoKeyboard |
| `F8`  | 🚨 Parada de emergência |
| `F9`  | Inicia/para o Macro |
| `F10` | Inicia/para a Gravação |
| `Pause/Break` | Pausa/Retoma o macro |

Reconfiguráveis em **Configurações → Hotkeys**.

**Parada de emergência extra:** jogue o cursor pro canto superior esquerdo da tela rapidamente — para tudo instantaneamente.

---

## 📱 Controle remoto via celular (ntfy.sh)

1. Instale o app **ntfy** ([Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy) / [App Store](https://apps.apple.com/us/app/ntfy/id1625396347)) — gratuito, open-source.
2. Na aba **📡 Monitoramento**, clique em **Mostrar QR Code**.
3. Abra o app ntfy → `+` → escanear QR.
4. Marque **🟢 Ativar Conexão** no PC.
5. Pronto. Mande comandos pelo app:

| Comando | O que faz |
|---------|-----------|
| `/run` | Inicia macro atual |
| `/run 1` ou `/run nome` | Carrega slot e inicia |
| `/stop` | Para tudo |
| `/pause` / `/resume` | Pausa/retoma macro |
| `/status` | Recebe estado atual |
| `/screen` | Recebe screenshot da tela |
| `/help` | Lista comandos disponíveis |

Você também pode criar **Monitores** que disparam notificações quando algo aparece na tela (ex: "Game Over detectado").

---

## 🔧 Pra desenvolvedores

Rodar do código fonte:

```bash
pip install -r requirements.txt
python AutoClickPro.py
```

Gerar pacote distribuível (.exe via Nuitka):

```bash
python build.py
```

Estrutura:
- `core/` — lógica de automação, sem UI (driver Windows, engine, OCR, ntfy, hotstrings)
- `ui/` — interface Tkinter (app principal + diálogos)
- `profiles/` — perfis e configurações do usuário (gitignored)
- `assets/` — ícones e recursos

---

## 📜 Licença

[AGPL-3.0](LICENSE) — você pode usar, modificar e distribuir, mas qualquer modificação ou serviço derivado precisa também ser open source sob a mesma licença. **Não é permitido vender versões fechadas/modificadas deste app.**

---

## 🤝 Comunidade

- **Issues:** reporte bugs ou sugira features [aqui no GitHub](../../issues).
- **Pull Requests:** contribuições são bem-vindas.

---

## ⚠ Aviso

Este software é fornecido "como está", sem garantias. O uso de automação em jogos online pode violar os Termos de Serviço de alguns jogos — use por sua conta e risco.
