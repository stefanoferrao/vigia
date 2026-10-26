# VigIA

[![CI](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml/badge.svg)](https://github.com/stefanoferrao/vigia/actions/workflows/ci.yml)

> O uso dos seus agentes de IA de relance — uma pílula flutuante para Linux e Windows.

![Prévia do VigIA](docs/preview.png)

VigIA fica sobre a tela, sem moldura e sem ícone no painel, mostrando quanto do
seu limite cada agente de IA já consumiu. Os números aparecem ao lado do ícone
real de cada provedor (Claude, Codex, OpenCode, Gemini, Grok…) e, se você quiser,
CPU, RAM e GPU na mesma linha.

## O que ela faz

- **Uma linha só**: ícone do provedor + porcentagem do limite, no canto que você escolher.
- **Fundo translúcido** ajustável de 40% a 100% — o texto continua nítido.
- **Nove posições** de encaixe (topo/meio/base × esquerda/centro/direita).
- **Três tamanhos** (pequeno, médio, grande).
- **Arrasta e lembra** a posição de cada monitor; em "ambos", uma pílula por tela.
- **Nunca atravessa a divisa** entre monitores: nas bordas compartilhadas ela mantém margem.
- **Largura estável**: a pílula não muda de tamanho quando o uso oscila.
- **Ícones** em três estilos: cor da marca, monocromático, ou monocromático com alerta de cor quando o uso aperta.
- **CPU / RAM / GPU** opcionais, desligados por padrão.
- **Cinco idiomas**: português, inglês, espanhol, francês e alemão (ou automático pelo sistema).
- **Atalho global** e autostart opcional.

## Requisitos

- **Python 3.11+** (usa `tomllib`).
- **PySide6** (Qt 6) — o instalador cria um ambiente privado e baixa (~82 MB de download, ~245 MB em disco).
- No Linux: **libxcb-cursor0** (o instalador tenta resolver; veja *Problemas*).
- O CLI **[ai-usagebar](https://github.com/akitaonrails/ai-usagebar)**, que lê as cotas dos provedores. Há builds para Linux e Windows.

## Instalação

### Linux

```bash
git clone https://github.com/stefanoferrao/vigia.git
cd vigia
./install.sh
```

O instalador copia o app para `~/.local/share/vigia`, cria um venv com PySide6,
instala em `~/.local/bin/vigia` e registra o atalho de menu. Ele reconhece
apt/dnf/pacman ao avisar sobre dependências do sistema.

### Windows 11

No PowerShell, dentro da pasta clonada:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Isso cria `%LOCALAPPDATA%\vigia` com o venv, PySide6, um atalho no menu Iniciar e
o launcher `vigia.cmd`. O autostart usa a chave `HKCU\...\Run` (desligável no menu).

Depois de instalar, abra com `vigia` (Linux) ou pelo atalho **VigIA** no menu Iniciar (Windows).

## Uso

Ao abrir, a pílula aparece no canto superior direito do monitor principal.

- **Passar o mouse** clareia o fundo e revela a engrenagem de configurações.
- **Arrastar** move a pílula; a posição fica salva por monitor.
- **Engrenagem** (ou botão direito) abre o menu com todos os ajustes. O menu
  **fica aberto** enquanto você muda as opções — só *Esconder* e *Sair* o fecham.
- **Atalho padrão `Ctrl+Alt+U`** mostra/esconde (e inicia, se não estiver rodando).
- **Sair de verdade** é pelo menu → *Sair*.

> Atalhos começando com `Super` costumam ser capturados pelo sistema antes de
> chegar ao app. Por isso o padrão é `Ctrl+Alt+U`; trocar é uma linha no config.

## Configuração

Linux: `~/.config/vigia/vigia.toml` · Windows: `%APPDATA%\vigia\vigia.toml`.
O menu grava nesse arquivo; edições manuais são aplicadas com `vigia --reload`.

```toml
[overlay]
opacity = 0.82          # 0.40 a 1.00 — transparência só do fundo
size = "medium"         # small | medium | large
icon_style = "brand"    # brand | mono | alert
monitor = "primary"     # primary | secondary | all | "0", "1", ...
anchor = "top-right"    # top-left | top-center | top-right
                        # middle-left | middle-center | middle-right
                        # bottom-left | bottom-center | bottom-right
always_on_top = true
show_system = false     # CPU / RAM / GPU
autostart = true
refresh_minutes = 5     # 1 a 60
max_providers = 4       # 1 a 8
hotkey = "<Control><Alt>u"
language = "auto"       # auto | pt | en | es | fr | de
alert_warn = 60         # icon_style = "alert": âmbar a partir daqui
alert_critical = 80     # ... e vermelho a partir daqui
hide_providers = ""     # ids separados por vírgula: "openai,gemini"
hide_system = ""        # "cpu,ram,gpu" para esconder itens do sistema
```

Para escolher o que aparece, use o menu **Itens** (checkbox por provedor e por
CPU/RAM/GPU) — a escolha vai para `hide_providers` e `hide_system`. Itens ocultos
continuam listados no menu, então dá para trazê-los de volta. Com `icon_style =
"alert"`, os números ficam âmbar e vermelho conforme `alert_warn` / `alert_critical`.

A tabela `[overlay.positions]` guarda o deslocamento de cada monitor (chave = nome
da tela) depois de um arrasto — não precisa mexer nela. *Restaurar posição* no
menu limpa esses valores e volta ao encaixe escolhido.

## Idiomas

O padrão é **Automático** (segue o locale do sistema; no Windows, o idioma da
interface). Para fixar, use o menu **Idioma** ou `language = "en"`.
Disponíveis: `pt`, `en`, `es`, `fr`, `de`.

## Linha de comando

| Comando | O que faz |
|---|---|
| `vigia` | abre a pílula (mostra a instância existente, se houver) |
| `vigia --show` | mostra, iniciando se preciso |
| `vigia --toggle` | mostra/esconde (bom para atalho) |
| `vigia --reload` | relê o config sem reiniciar |
| `vigia --quit` | encerra a instância |
| `vigia --version` | imprime a versão |

## Como os dados são lidos

- **Provedores**: `ai-usagebar usage --json`, a cada 5 minutos. Cada pílula mostra o
  valor principal (*headline*) do relatório daquele provedor.
- **CPU/RAM**: `psutil` quando disponível; no Linux, `/proc/stat` e `/proc/meminfo`; no Windows, a API do sistema.
- **GPU**: `gpu_busy_percent` do `sysfs` (Linux) ou `nvidia-smi` (quando existe).

Nada sai da sua máquina além das chamadas que o `ai-usagebar` já faz.

## Estrutura

```
vigia            launcher (Python)
vigia_qt.py      interface Qt — a mesma nos dois sistemas
vigia_core.py    dados, config, idiomas, métricas
icons/           marcas dos provedores (SVG)
assets/          ícone do app e engrenagem
tests/           testes do núcleo e smoke do Qt
install.sh       instalador Linux
install.ps1      instalador Windows
```

## Limitações conhecidas

- **Wayland**: atalho global e posicionamento livre de janela são restritos pelo
  compositor. A pílula aparece, mas o `hotkey` pode não funcionar — use o atalho
  do próprio desktop chamando `vigia --toggle`.
- **Windows 11**: o código é o mesmo e o CI roda os testes em `windows-latest`,
  mas a validação visual foi feita em Linux/X11. Se algo estiver fora do lugar,
  abra uma issue com o print.
- A GPU depende do driver expor `gpu_busy_percent` (Linux) ou do `nvidia-smi`
  existir; sem isso, o item é omitido (em vez de mostrar zero).
- Traduções de espanhol, francês e alemão são a primeira passada — correções são bem-vindas.

## Problemas?

- **Qt não abre (Linux)**: falta `libxcb-cursor0` → `sudo apt install libxcb-cursor0`
  (Fedora: `xcb-util-cursor`; Arch: `xcb-util-cursor`). O instalador tenta resolver.
- **Nada aparece na pílula**: rode `ai-usagebar usage --json` e veja se há dados.
- **Sem atalho no Wayland**: veja *Limitações*.
- **Log**: Linux `~/.cache/vigia/vigia.log` · Windows `%LOCALAPPDATA%\vigia\vigia.log`.

## Desinstalação

Linux:

```bash
vigia --quit
rm -f  ~/.local/bin/vigia
rm -rf ~/.local/share/vigia ~/.config/vigia
rm -f  ~/.local/share/applications/vigia.desktop ~/.config/autostart/vigia.desktop
rm -f  ~/.local/share/icons/hicolor/scalable/apps/vigia.svg
```

Windows (PowerShell):

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\vigia"
Remove-Item -Recurse -Force "$env:APPDATA\vigia"
Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\VigIA.lnk"
Remove-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name VigIA
```

## Créditos

- Dados de cota: [ai-usagebar](https://github.com/akitaonrails/ai-usagebar).
- Os ícones dos provedores são marcas dos respectivos donos, usados aqui apenas
  para identificação, e vêm do pacote do `ai-usagebar`/Omarchy.

## Licença

MIT — veja [LICENSE](LICENSE).
