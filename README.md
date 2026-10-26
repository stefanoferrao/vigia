# VigIA

> O uso dos seus agentes de IA de relance — uma pílula flutuante para Linux.

![Prévia do VigIA](docs/preview.png)

VigIA fica sobre a tela, sem moldura e sem ícone no painel, mostrando quanto do
seu limite cada agente de IA já consumiu. Os números usam o ícone real de cada
provedor (Claude, Codex, OpenCode, Gemini, Grok…), e opcionalmente CPU, RAM e GPU
na mesma linha.

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

- Linux com **GTK 3** e PyGObject (testado no **Linux Mint 22 / Cinnamon, X11**).
- **Python 3.11+** (usa `tomllib`).
- **gir1.2-keybinder-3.0** para o atalho global (sem ele, o app funciona, só sem atalho).
- O CLI **[ai-usagebar](https://github.com/akitaonrails/ai-usagebar)**, que lê as cotas dos provedores.
- GPU: funciona via `gpu_busy_percent` do driver (amdgpu, entre outros). Se a sua máquina não expõe, o item GPU simplesmente não aparece.

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-keybinder-3.0
```

## Instalação

```bash
git clone https://github.com/stefanoferrao/vigia.git
cd vigia
./install.sh
```

Depois abra com `vigia` ou procure **VigIA** no menu de aplicativos.

O instalador copia o script para `~/.local/bin/vigia`, os ícones para
`~/.local/share/vigia/icons`, e cria o atalho de menu. O autostart é criado no
primeiro uso (e pode ser desligado no menu).

<details>
<summary>Instalação manual</summary>

```bash
install -Dm755 vigia ~/.local/bin/vigia
mkdir -p ~/.local/share/vigia/icons
cp icons/*.svg ~/.local/share/vigia/icons/
install -Dm644 assets/vigia.svg ~/.local/share/icons/hicolor/scalable/apps/vigia.svg
gtk-update-icon-cache -f -t ~/.local/share/icons/hicolor
```

</details>

## Uso

Ao abrir, a pílula aparece no canto superior direito do monitor principal.

- **Passar o mouse** clareia o fundo e revela a engrenagem de configurações.
- **Arrastar** move a pílula; a posição fica salva por monitor.
- **Engrenagem** abre o menu com todos os ajustes.
- **Atalho padrão `Ctrl+Alt+U`** mostra/esconde (e inicia, se não estiver rodando).
- **Sair de verdade** é pelo menu → *Sair*.

> Atalhos começando com `Super` costumam ser capturados pelo Cinnamon antes de
> chegar ao app. Por isso o padrão é `Ctrl+Alt+U`; trocar é uma linha no config.

## Configuração

Tudo fica em `~/.config/vigia/vigia.toml`. O menu grava nesse arquivo; edições
manuais são aplicadas com `vigia --reload` (ou ao reiniciar).

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
```

A tabela `[overlay.positions]` guarda o deslocamento de cada monitor depois de
um arrasto — não precisa mexer nela. *Restaurar posição* no menu limpa esses
valores e volta ao encaixe escolhido.

## Idiomas

O padrão é **Automático**, que segue o `LANG` do sistema. Para fixar um idioma,
use o menu **Idioma** ou `language = "en"` no config. Idiomas disponíveis:
`pt`, `en`, `es`, `fr`, `de`.

## Linha de comando

| Comando | O que faz |
|---|---|
| `vigia` | abre a pílula (inicia o processo se necessário) |
| `vigia --show` | mostra, iniciando se preciso |
| `vigia --toggle` | mostra/esconde (bom para atalho) |
| `vigia --reload` | relê o `vigia.toml` sem reiniciar |
| `vigia --quit` | encerra a instância |
| `vigia --version` | imprime a versão |

## Como os dados são lidos

- **Provedores**: `ai-usagebar usage --json`, a cada 5 minutos. Cada pílula mostra o
  valor principal (*headline*) do relatório daquele provedor.
- **CPU/RAM**: `/proc/stat` e `/proc/meminfo`, a cada 2 segundos.
- **GPU**: `gpu_busy_percent` do `sysfs`.

Nada sai da sua máquina além das chamadas que o `ai-usagebar` já faz.

## Limitações conhecidas

- Testado em **X11/Cinnamon**. Em Wayland o posicionamento e o atalho global podem não funcionar.
- A GPU depende do driver expor `gpu_busy_percent`; sem isso, o item é omitido (em vez de mostrar zero).
- O atalho global depende do Keybinder; sem ele o app roda, mas sem atalho.
- As traduções de espanhol, francês e alemão são contribuições iniciais — correções são bem-vindas.

## Problemas?

- **Nada aparece na pílula**: rode `ai-usagebar usage --json` e veja se há dados.
- **Sem atalho**: instale `gir1.2-keybinder-3.0` e reinicie o app.
- **Log**: `~/.cache/vigia/vigia.log`.
- **Diagnóstico do layout**: `AI_USAGEBAR_DEBUG=1 vigia` grava as decisões de encaixe no log.

## Desinstalação

```bash
vigia --quit
rm -f  ~/.local/bin/vigia
rm -rf ~/.config/vigia ~/.local/share/vigia
rm -f  ~/.local/share/applications/vigia.desktop ~/.config/autostart/vigia.desktop
rm -f  ~/.local/share/icons/hicolor/scalable/apps/vigia.svg
```

## Créditos

- Dados de cota: [ai-usagebar](https://github.com/akitaonrails/ai-usagebar).
- Os ícones dos provedores são marcas dos respectivos donos, usados aqui apenas
  para identificação, e vêm do pacote do `ai-usagebar`/Omarchy.
- Feito para Linux Mint / Cinnamon.

## Licença

MIT — veja [LICENSE](LICENSE).
