---
version: alpha
name: Light
description: "Pilula clara de papel, texto tinta, estados escurecidos para AA sobre branco."
colors:
  surface: "#fafafa"
  surface-border: "#dcdce0"
  text-primary: "#171717"
  text-secondary: "#5c5f66"
  text-disabled: "#73757b"
  divider: "#e3e3e6"
  state-ok: "#0b7a4b"
  state-warning: "#8a5300"
  state-critical: "#c50000"
  primary: "#0066cc"
  menu-surface: "#ffffff"
  menu-border: "#dcdce0"
  menu-hover: "#ececf0"
typography:
  label:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 10px
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: 0.01em
  value:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 10px
    fontWeight: 600
    lineHeight: 1.2
    fontFeature: "tnum"
  caption:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 9px
    fontWeight: 500
    lineHeight: 1.2
  menu:
    fontFamily: "Inter, Segoe UI, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.3
rounded:
  sm: 4px
  md: 8px
  lg: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 6px
  md: 9px
  lg: 16px
  xl: 28px
components:
  pill:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.full}"
    padding: 9px
    typography: "{typography.label}"
  pill-label:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    typography: "{typography.label}"
  pill-value-ok:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.state-ok}"
    typography: "{typography.value}"
  pill-value-warning:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.state-warning}"
    typography: "{typography.value}"
  pill-value-critical:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.state-critical}"
    typography: "{typography.value}"
  pill-primary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    typography: "{typography.value}"
  island-handle:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.full}"
    height: 8px
    width: 120px
  menu:
    backgroundColor: "{colors.menu-surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: 4px
    typography: "{typography.menu}"
  menu-item-hover:
    backgroundColor: "{colors.menu-hover}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.sm}"
  pill-outline:
    backgroundColor: "{colors.surface-border}"
    height: 1px
  divider:
    backgroundColor: "{colors.divider}"
    width: 1px
  menu-outline:
    backgroundColor: "{colors.menu-border}"
    height: 1px
  menu-item-disabled:
    backgroundColor: "{colors.menu-surface}"
    textColor: "{colors.text-disabled}"
    rounded: "{rounded.sm}"
---

## Overview

Light: Limpo, editorial, sombra sutil em vez de brilho. Pilula flutuante no topo da tela (estilo Dynamic Island) que mostra cotas de IA e metricas do sistema de relance. Inspiracao de valores: Vercel (#171717/#fafafa, #ee0000, #f5a623), Apple (hairline #e0e0e0, canvas #f5f5f7). Sem marca ou logo de terceiros.

## Colors

- **Surface (#fafafa):** fundo da pilula; o codigo aplica alfa de opacidade em runtime.
- **Surface border (#dcdce0):** contorno de 1px.
- **Text primary / secondary:** `#171717` para valores e `#5c5f66` para rotulos e iniciais.
- **Divider (#e3e3e6):** linha vertical entre grupos.
- **State ok / warning / critical:** `#0b7a4b`, `#8a5300`, `#c50000`; todos com contraste AA sobre a superficie. Estado nunca depende so de cor: criticos ganham peso 700 e sufixo.
- **Primary / accent (#0066cc):** foco, item ativo no menu e realce customizavel pelo usuario.
- **Menu surface / hover:** `#ffffff` e `#ececf0`.

## Typography

Familia unica sans-serif do sistema com fallback. Valores usam numeros tabulares (`tnum`) para nao tremer ao atualizar. Escala fixa: caption 9, label/value 10, menu 13 px; o tamanho small/medium/large do app multiplica a escala.

## Layout

Escala de espacamento 4/6/9/16/28 px: `xs` e `sm` entre icone e texto, `md` padding horizontal, `lg` entre blocos, `xl` entre grupos. Alinhar numeros a direita da coluna; altura da pilula = 2 x raio.

## Elevation & Depth

Profundidade sutil: borda de 1px em `surface-border`, realce interno: none (sem brilho interno), sombra externa `0 4px 16px rgba(0,0,0,0.12)`. Hover da pilula eleva a opacidade, nao a sombra. Menu usa mesma borda e sombra um nivel acima.

## Shapes

Pilula totalmente arredondada (`full`, raio = altura/2). Menu `md` 8px; itens `sm` 4px. Handle da ilha colapsada: 120x8 px, `full`.

## Components

- **pill:** container principal; **pill-label** rotulo secundario; **pill-value-ok/warning/critical** valor por faixa (60% e 80% por padrao); **pill-primary** realce.
- **island-handle:** estado colapsado.
- **menu**, **menu-item-hover**, **menu-item-disabled:** menu de contexto (QMenu).
- Transicoes: mudanca de estado faz crossfade de cor em 200 ms; critico pulsa a opacidade 100%-70% a cada 2 s (desligado com reduzir movimento).

## Do's and Don'ts

- Faca: usar apenas tokens; manter contraste AA (4.5:1) em texto.
- Faca: usar o mesmo conjunto de chaves em todos os temas.
- Nao: usar cor como unico indicador de estado.
- Nao: sombras pesadas ou brilho neon; nao copiar marcas de terceiros.
- Nao: animar alem de 400 ms.
