# AutoClick Pro

Ferramenta de automação para Windows com auto-clicker, auto-keyboard, gravador e executor de macros, OCR e suporte a variáveis. Interface gráfica em Tkinter, em português, com temas claro/escuro.

> **Licença:** [GNU AGPL v3.0](LICENSE) — se você usar este código em um serviço acessível pela rede, precisa disponibilizar o código-fonte modificado aos usuários.

---

## Funcionalidades

- **AutoClick** — cliques automatizados, sequência de posições, humanização, jitter, modo background (PostMessage), janela alvo específica
- **AutoKeyboard** — digitação repetida, modo colar (Ctrl+V) para Discord/Notepad, intervalo aleatório anti-detecção, Enter automático, importar de `.txt`
- **Macros** — sequências ricas: `click`, `digitar`, `aguardar`, `scroll`, `key_press`, `pixel_check`, `image_click`, `OCR`, variáveis
- **Gravador** — grava cliques + teclado, converte em macro editável
- **Variáveis** — `set`/`add`/`sub`/`mul`/`div`/`concat`, interpolação com `{nome}`, painel ao vivo
- **OCR** — lê texto da tela em qualquer região, suporta números, whitelist de caracteres, múltiplos idiomas (eng/por/...)
- **Step-by-step** — modo debug que pausa após cada passo do macro
- **Velocidade** — playback ½× / 1× / 2× / 4×
- **Perfis** — salva/carrega configurações em slots ou arquivos JSON
- **Temas** — dark / light, redimensionamento, tela cheia

---

## Instalação (Windows — usuário final)

1. Baixe o ZIP do repositório (ou `git clone`)
2. Clique duas vezes em **`instalar.bat`**

O instalador faz tudo automaticamente:

- Detecta seu Python (ou baixa Python 3.13 per-user, sem admin/UAC, ~30MB)
- Copia arquivos para `%LOCALAPPDATA%\AutoClickPro`
- Instala dependências Python via `pip`
- Baixa e instala Tesseract OCR (~75MB, pede confirmação admin uma vez) — opcional, só pra OCR
- Cria atalhos na Área de Trabalho e Menu Iniciar
- Gera `desinstalar.bat` na pasta de instalação

> **Internet obrigatória** apenas na primeira instalação para baixar Python/Tesseract.

### Falhas comuns

- **Python não baixa** (sem internet, antivírus): instale manualmente em <https://python.org>
- **Tesseract falha**: o app abre normalmente, apenas a feature OCR fica indisponível. Instale depois em <https://github.com/UB-Mannheim/tesseract/wiki>

---

## Instalação (desenvolvedor)

```powershell
git clone https://github.com/Carairritante/Autoclick-PRO.git
cd Autoclick-PRO
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python AutoClickPro.py
```

### Build (executável standalone)

```powershell
python -m nuitka --standalone --windows-disable-console --enable-plugin=tk-inter `
  --include-data-dir=assets=assets --output-dir=dist AutoClickPro.py
```

---

## Teclas de atalho padrão

| Tecla | Ação                                    |
|------:|-----------------------------------------|
|  F6   | Iniciar / Parar AutoClick               |
|  F7   | Iniciar / Parar AutoKeyboard            |
|  F9   | Executar / Parar Macro                  |
|  F10  | Iniciar / Parar Gravação de Macro       |
|  F8   | Parar tudo                              |
|  F11  | Tela cheia / janela                     |
|  Esc  | Sair da tela cheia                      |

### Parada de emergência

Mova o mouse rapidamente para o **canto SUPERIOR ESQUERDO** da tela.

---

## Requisitos técnicos

- Windows 10/11
- Python 3.10+ (instalado automaticamente pelo `instalar.bat`)
- Dependências em [`requirements.txt`](requirements.txt):
  - `pyautogui`, `keyboard`, `pystray`, `Pillow`, `pynput`, `opencv-python`, `pytesseract`
- Tesseract OCR (opcional, apenas para feature OCR)

---

## Estrutura do projeto

```
AutoClickPro/
├── AutoClickPro.py        # Entry point
├── core/
│   ├── engine.py          # Loop de execução de cliques/teclas/macros
│   ├── driver.py          # Abstração de mouse/teclado (pyautogui + Win32)
│   ├── recorder.py        # Gravador de input
│   ├── macro_schema.py    # Schema/validação JSON dos macros
│   ├── hotstrings.py      # Substituição automática de texto
│   ├── icon_gen.py        # Gera ícones em runtime
│   └── paths.py           # Resolução de paths (AppData, etc.)
├── ui/
│   ├── app.py             # Janela principal Tkinter
│   ├── step_dialog.py     # Editor de steps de macro
│   └── widgets.py         # Widgets customizados
├── assets/                # Ícones e sons
├── requirements.txt
├── instalar.bat           # Instalador Windows (sem admin)
├── install_python.ps1     # Subscript: instala Python
├── install_tesseract.ps1  # Subscript: instala Tesseract
└── LICENSE                # GNU AGPL v3.0
```

---

## Aviso de uso responsável

Esta ferramenta automatiza entrada de mouse/teclado e leitura de tela. **Você é responsável por usar dentro dos Termos de Serviço** dos aplicativos/jogos/sites onde rodar. Muitos jogos online proíbem automação e podem banir contas — não nos responsabilizamos por consequências.

**Não use para:** spam, fraude, contornar CAPTCHAs ou medidas anti-abuso, manipular votações, criar tráfego artificial, ou qualquer atividade ilegal.

---

## Doações

Veja o botão "❤ Apoie o projeto" dentro do app, na aba **Configurações**.

---

## Licença

Distribuído sob **GNU Affero General Public License v3.0** — veja [LICENSE](LICENSE) para o texto completo.

Em resumo:

- ✅ Você pode usar, modificar e redistribuir
- ✅ Você pode usar comercialmente
- ⚠️ Trabalhos derivados **devem** ser distribuídos sob AGPL-3.0
- ⚠️ Se rodar este software em um **serviço de rede**, você **deve disponibilizar o código-fonte** (modificado) aos usuários desse serviço
- ❌ Sem garantias

---

## Contribuir

Pull requests são bem-vindos. Para mudanças grandes, abra uma **issue** primeiro para discutir o que você quer mudar.

Antes de submeter:

1. Não inclua credenciais, tokens, ou dados pessoais
2. Teste no Windows 10 e 11 se possível
3. Mantenha o estilo do código existente (PT-BR em comentários, type hints quando fizer sentido)
