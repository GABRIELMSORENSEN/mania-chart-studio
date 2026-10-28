# Validação local — 28/10/2026

- `python -m pytest -q`: **15 testes passaram**. Links permitidos/proibidos, offset na exportação, LN, sobreposições, limites de duração, pacote .osz, edição via API e bloqueio de host/origem externos.
- `node --check web/app.js`: passou.
- `python -m compileall -q engine.py server.py start.py`: passou.
- Auditoria estática premium-ui strict: zero erros, avisos ou pendências. Decisão explícita: selects nativos com popup do sistema operacional.
- `python tests/browser_smoke.py`: passou em Chromium 145, com **download real pelo YouTube**, inferência Beat This small0 e cinco dificuldades. Exercitados erro de link, reprodução, ajuste de offset, desfazer, inserção de nota, salvamento e exportação. Nenhum erro JavaScript.
- Exportação real: **27.548.305 bytes**, cinco `.osu`, `audio.wav`, `cover.jpg` e aviso de AI draft. Os cinco charts foram lidos pelo parser rosu; estrelas no teste: 1,15 / 2,01 / 2,41 / 3,06 / 3,28. Isso não atende à faixa original de 3–7 estrelas e não é apresentado como tal.
- Viewports 1440×1100 e 390×844, sem overflow horizontal. Teclado em select nativo e modo de movimento reduzido exercitados.
- Instalação das dependências verificada em ambiente virtual que reutiliza pacotes do Python local. Não foi feita instalação integral numa máquina limpa.
- Download HTTPS oficial do modelo confirmado com validação TLS e checksum. O modelo não foi alterado nem treinado neste projeto.

## O que esses testes não comprovam

Não houve aprovação humana da musicalidade dos rascunhos, nem confirmação auditiva do timing de cada nota. Não se afirma que o pacote é ranqueável, equivalente a charts humanos ou uma correção aprovada dos lotes anteriores. O preview usa o mesmo relógio Web Audio para música e hits, mas a latência física de cada dispositivo não foi calibrada.

O teste de decoder anterior em Paparazzi comparou BASS do osu! e FFmpeg na mesma taxa de 48 kHz: diferença de zero amostras. Isso descarta divergência dos decoders nesse trecho, e não valida a distribuição de notas. Os lotes V1 e V2 rejeitados continuam separados; o editor não os reinstala.

Capturas e áudio de teste ficam em `test-results/` e `data/`, ignorados pelo Git. A release não contém músicas de terceiros ou dados do perfil pessoal.
