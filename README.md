# DinoTube

Um "mini YouTube" para o seu computador: cole um link, assista, baixe, organize e continue de onde parou.
Feito em Python com PySide6 (Qt), para Windows (roda também em Linux e macOS a partir do código-fonte).

## O que faz

- **Link ou busca** na barra do topo: abre o vídeo na tela de reprodução.
- **Salvar na biblioteca** (só o registro) ou **baixar** (arquivo na sua pasta). Vídeos baixados ficam destacados.
- **Player grande**: toca o arquivo local quando ele existe e foi verificado; senão, usa o player incorporado do YouTube.
- **Qualidade do download** já começa na qualidade que está tocando; fila de downloads com cancelar/tentar de novo,
  junção de vídeo e áudio com ffmpeg e validação do arquivo final.
- **Biblioteca** com busca (sem acento), filtros, ordenação, categorias, playlists e playlists inteligentes.
- **Continuar assistindo**, histórico por dia e retomada da posição.
- **Manutenção**: espaço em disco, arquivos ausentes ou soltos, backups (manual e automático), exportação JSON/CSV.
- **Mini player** flutuante sempre por cima (botão no player ou tecla `I`).
- **22 temas** (escuro, claro, sistema, oceano, floresta, pôr do sol e mais 17: Minimalista, Cinema, Vidro fosco, Vidro cinza, Relevo suave,
  Nord, Dracula, Terminal, Pixel Art, Luxo, Pastel, Editorial, Fluent, Cyberpunk, Monocromático, Objetos físicos e Terra),
  todos com contraste de texto verificado por teste (WCAG AA), e **idiomas** (português do Brasil e inglês).
  Os temas mudam também a **estrutura**, não só a cor: fundo (vidro com manchas de luz, grade, linhas de varredura, papel, aurora…),
  tipo de cartão (vidro translúcido, borda dura, neon, só um fio, relevo…), navegação (pílula, barra lateral, bloco, sublinhado),
  forma dos botões, densidade, títulos em maiúsculas, sombras e espessura dos ícones. O **Vidro fosco** é translúcido sobre manchas de luz; o **Vidro cinza** deixa ver o que está aberto atrás do aplicativo
  (janela translúcida; no Windows 10/11 o sistema desfoca o fundo, podendo ser trocado em *Configurações → Tema* entre fosco (desfocado) e transparente (sem desfoque); em outros sistemas ela fica apenas transparente).
- **6 layouts**, combináveis com qualquer tema (*Configurações → Layout*, com prévia):
  - **Biblioteca clássica**: menu lateral, player central, relacionados abaixo e painel de detalhes opcional.
  - **Streaming**: início com vídeo em destaque, fileiras horizontais e recomendações feitas só com a sua biblioteca.
  - **Modo cinema**: o player ocupa a janela; controles e título somem quando o mouse para.
  - **Gerenciador**: biblioteca em tabela (colunas escolhíveis, ordenação, seleção em lote) com filtros avançados no topo.
  - **Estação de trabalho**: biblioteca à esquerda, player no centro, detalhes, **notas por vídeo** e categorias à direita.
  - **Compacto e flutuante**: janela pequena com controles essenciais e **fila de reprodução**; pode ficar por cima das outras.
- **Fila de reprodução** em qualquer layout (menu ⋮ de um vídeo → *Adicionar à fila* / *Tocar em seguida*).
- A engrenagem fica no canto inferior direito.

## Instalação (a partir do código-fonte)

Requisitos: Python 3.11 ou mais novo.

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

O ffmpeg e o ffprobe já acompanham o projeto em `third_party/ffmpeg/bin` (build GPL; mantenha `LICENSE` e `README.txt`).
Em *Configurações → Downloads* dá para apontar outro ffmpeg.

## Primeiro uso

1. Escolha onde guardar a biblioteca. Sugestão: `A:\pytube` (ou qualquer pasta).
   - **100% em pasta (portátil)**: tudo fica dentro da pasta (`videos`, `thumbnails`, `data`, `backups`, `logs` e `tmp`).
   - **Banco de dados**: a biblioteca fica num SQLite na pasta de dados do aplicativo; vídeos e miniaturas ficam na pasta escolhida.
2. Na primeira vez que baixar, leia e aceite o aviso sobre uso responsável.
3. Cole um link na barra do topo e escolha **Salvar** ou **Baixar**.

## Atalhos

| Tecla | Ação |
| --- | --- |
| `Espaço` / `K` | tocar e pausar |
| `←` / `→` | voltar / avançar 5 s |
| `↑` / `↓` | volume |
| `M` | silenciar |
| `F` / `Esc` | tela cheia / sair |
| `I` | mini player |
| `Ctrl+K` | buscar na biblioteca |
| `Ctrl+L` | colar um link |
| `Ctrl+,` | configurações |

## Gerar o executável (Windows)

```bat
packaging\build_windows.bat
```

O resultado fica em `dist\DinoTube\DinoTube.exe` (pasta única; copie a pasta inteira).

## Desenvolvimento

```bash
pip install -r requirements-dev.txt
python -m pytest tests
```

Os testes não usam a internet: provedores e player são simulados, e o ffmpeg real é usado para gerar mídia de teste.

## Limitações conhecidas

- Os provedores (`pytubefix` e `yt-dlp`) dependem do YouTube e quebram de tempos em tempos.
  Se um download falhar, use *Configurações → Atualizar provedores*.
- Alguns vídeos não permitem ser incorporados; nesses casos o app oferece abrir no navegador.
- Baixe apenas conteúdo que você tem o direito de baixar.
