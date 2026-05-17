==============================
  AutoClick Pro — Instalação
==============================

REQUISITOS
----------
NENHUM — o instalador baixa tudo automaticamente.

(Internet necessária na 1ª instalação para baixar Python e Tesseract.)


INSTALAÇÃO
----------
Clique duas vezes em:  instalar.bat

O instalador faz tudo automaticamente:
  - Detecta seu Python (ou baixa e instala Python 3.13 se faltar)
    Instalação per-user, sem admin/UAC. ~30MB do site oficial.
  - Copia os arquivos para %LOCALAPPDATA%\AutoClickPro
  - Instala as dependências Python (pip)
  - Baixa e instala o Tesseract OCR (para feature de OCR no macro)
    ~75MB, pede confirmação de administrador uma vez
  - Cria atalhos na Área de Trabalho e Menu Iniciar
  - Gera desinstalador (desinstalar.bat dentro da pasta de instalação)

Após terminar, clique no ícone "AutoClick Pro" na Área de Trabalho.

OBS:
  - Se Python falhar (sem internet, antivírus), o instalador para e mostra
    instruções para instalar manualmente em https://python.org
  - Se o Tesseract falhar, o app funciona normalmente — só a feature OCR
    no macro fica indisponível. Pode instalar depois em:
    https://github.com/UB-Mannheim/tesseract/wiki


TECLAS DE ATALHO PADRÃO
------------------------
  F6   — Iniciar / Parar AutoClick
  F7   — Iniciar / Parar AutoKeyboard
  F9   — Executar / Parar Macro
  F10  — Iniciar / Parar Gravação de Macro
  F8   — Parar tudo
  F11  — Tela cheia / janela
  Esc  — Sair da tela cheia


PARADA DE EMERGÊNCIA
---------------------
Mova o mouse rapidamente para o canto SUPERIOR ESQUERDO da tela.


FUNCIONALIDADES
---------------
  AutoClick    — clica automaticamente; suporta sequência de posições,
                 humanização, jitter, modo background (PostMessage),
                 janela alvo específica
  AutoKeyboard — digita texto repetidamente; modo colar (Ctrl+V) para
                 Discord/Notepad; intervalo aleatório anti-detecção;
                 Enter automático; importar de arquivo .txt
  Macro        — sequência rica: click, digitar, aguardar, scroll, key_press,
                 pixel_check, image_click, OCR (ler texto), variáveis
  Gravador     — grava cliques + teclado, converte em macro editável
  Variáveis    — set/add/sub/mul/div/concat; interpolar com {nome}
                 painel ao vivo durante execução
  OCR          — lê texto da tela em qualquer região; suporta números;
                 whitelist de caracteres; idiomas múltiplos (eng/por/...)
  Step-by-step — modo debug que pausa após cada step do macro
  Velocidade   — playback ½× / 1× / 2× / 4× para o macro
  Perfis       — salva/carrega configurações em slots ou arquivos JSON
  Temas        — dark / light, redimensionamento livre, tela cheia


COMO DESINSTALAR
----------------
Execute:  %LOCALAPPDATA%\AutoClickPro\desinstalar.bat
(remove o app, atalhos e cache; Tesseract OCR deve ser desinstalado
 separadamente em "Adicionar/Remover Programas" do Windows se quiser)


DÚVIDAS / PROBLEMAS
---------------------
Se o app não abrir, verifique o arquivo error.log na pasta de instalação.
