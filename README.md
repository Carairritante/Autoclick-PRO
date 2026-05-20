# AutoClick Pro

Automatizador "faz tudo" pra Windows. Clica, digita, espera, decide, encadeia ações — tudo sem código, com gravador visual e editor de macros.

**Grátis. Sem login. Sem nuvem. Sem propaganda.**

---

## ✨ Features principais

- **🖱 AutoClick** — clicks automáticos em posição fixa, no cursor ou em sequência. Burst, humanização, jitter, "modo janela" (clica numa janela sem mover o cursor real).
- **⌨ AutoKeyboard** — digita texto repetidamente. Aceita Unicode (acentos, emoji), tokens (`{ENTER}`, `{F1}`), modo paste (Ctrl+V), intervalo aleatório.
- **🤖 Macro Editor** — sequência visual de ações. 22+ tipos de step:
  - Interação: `click`, `double_click`, `right_click`, `drag`, `move`, `scroll`
  - Teclado: `key_press`, `type`
  - Tempo: `wait`, `wait_window`
  - Visão: `pixel_check`, `image_click`, `wait_image`, `wait_pixel`, `click_text (OCR)`, `ocr_read`
  - Lógica: `if / else / endif`, `set_var`, `call_macro`
  - **🌐 `http_request`** — chama qualquer API REST (Discord webhook, Telegram bot, Home Assistant, etc.)
- **⏺ Gravador** — aperta F10, faz suas ações, F10 de novo. Vira macro editável.
- **✨ Hotstrings** — atalhos de texto que expandem em qualquer app (`:mail:` → seu email).
- **📅 Agendador** — execute macros em horários específicos, com recorrência diária/semanal.
- **📡 Monitoramento via Celular** — alertas e controle remoto via [ntfy.sh](https://ntfy.sh). Pareie via QR code e controle o PC do celular.
- **🎯 Stop Conditions** — para automaticamente se uma imagem aparece / pixel bate cor / variável atinge valor.
- **📚 Galeria de Exemplos** — templates prontos para jogos, trabalho, integrações e hotstrings.
- **💾 3 slots de perfis** + export/import JSON.
- **🌗 Tema escuro/claro**, tray icon, fullscreen, hotkeys globais.

---

## 🌐 HTTP Request — Integre com qualquer serviço

O step `http_request` permite chamar qualquer API REST de dentro de um macro, sem código:

```
Discord webhook → POST {"content": "Farm terminou!"} → notificação no celular
Telegram bot    → POST sendMessage                    → alerta no grupo
Home Assistant  → POST services/light/turn_on         → apaga a luz do quarto
OBS WebSocket   → POST requests/StartRecord           → inicia gravação
```

**Modos:** Simples (URL + método + body) e Avançado (headers livres, autenticação Bearer/Basic, timeout, salvar resposta em variável).

Suporta interpolação de variáveis no URL, body e headers: `{"user": "{nome}", "score": "{pontos}"}`.

---

## 🎮 Funciona em jogos (incluindo Roblox)

Usa `SendInput` com scan codes — passa pelo Raw Input do Roblox e outros jogos AAA que filtram inputs sintéticos. Modo "janela alvo" permite clicar numa janela específica sem perder foco da janela ativa.

### ⏳ wait_pixel — Reações em tempo real (200Hz)

Novo step que monitora um pixel específico da tela a 200Hz e age no instante em que a cor mudar:

- **Minigames de skill-check** (barra deslizante, círculo retrátil): coloca o watcher no centro da zona alvo e dispara um `key_press` quando o cursor passa por ali.
- **Trigger por cor**: espera pixel ficar vermelho (cooldown encerrou) → dispara habilidade.
- **Absent mode**: espera a cor desaparecer → reage.

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

### Comandos de macro

| Comando | O que faz |
|---------|-----------|
| `/run` | Inicia macro atual |
| `/run 1` ou `/run nome` | Carrega slot e inicia |
| `/stop` | Para tudo |
| `/pause` / `/resume` | Pausa/retoma macro |
| `/status` | Recebe estado atual |
| `/screen` | Recebe screenshot da tela |
| `/help` | Lista comandos disponíveis |

### Comandos de sistema (opt-in na aba Monitoramento)

| Comando | O que faz |
|---------|-----------|
| `/shutdown [N]` | Desliga o PC em N segundos (padrão: 30s) |
| `/abort` | Cancela shutdown agendado |
| `/sleep` | Suspende o PC |
| `/lock` | Bloqueia a tela |
| `/volume <0-100\|up\|down\|mute>` | Controla o volume |
| `/launch <app>` | Abre um app (chrome, discord, notepad, etc.) |
| `/window <nome>` | Traz janela pro foco |
| `/type <texto>` | Digita texto na janela ativa |
| `/click X Y` | Clica numa coordenada da tela |

> Comandos de sistema são **desativados por padrão** — marque explicitamente os que quiser permitir.

Você também pode criar **Monitores** que disparam notificações quando algo aparece na tela (ex: "Game Over detectado").

---

## 📚 Galeria de Exemplos

Templates prontos disponíveis em **📚 Exemplos**:

| Categoria | Templates |
|-----------|-----------|
| 🎮 Jogos | AFK Clicker, Spam Click, Pesca Minecraft, Anti-AFK Roblox, **Pesca GPO**, **Naramo Manutenção Usina**, **Naramo Estabilizar Reator** |
| 🔌 Integrações | Notificar Discord (Webhook), Notificar Telegram (Bot), Alerta texto na tela → Discord |
| 💼 Trabalho | Email, Assinatura, Chave PIX, Preencher formulário |
| ♿ Acessibilidade | Auto-refresh F5, Manter ativo, Scroll automático |
| ✨ Hotstrings | Saudação, Lorem ipsum, Horário comercial, Google Meet, Zoom |

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
- `core/` — lógica de automação, sem UI (driver Windows, engine, OCR, ntfy, hotstrings, agendador)
- `ui/` — interface Tkinter (app principal + diálogos)
- `profiles/` — perfis e configurações do usuário (gitignored)
- `assets/` — ícones e recursos

---

## 📜 Changelog resumido

| Versão | Destaques |
|--------|-----------|
| **v2.1** | Step `http_request`, step `wait_pixel`, 9 comandos ntfy novos, agendador, templates de jogos (GPO, Naramo) e integrações (Discord, Telegram), correções de estabilidade |
| **v2.0** | Refactor modular core/ui, drag, wait_window, wait_image, call_macro, if/else, OCR click_text, stop conditions, gravador melhorado, monitoramento ntfy v2, agendador |
| **v1.0** | AutoClick, AutoKeyboard, Macro básico, Hotstrings, Perfis |

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
