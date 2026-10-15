@echo off
REM ===========================================================================
REM  GameMania - copia as imagens do site atual (imgs\) para img\ com os nomes
REM  novos. Clique duas vezes neste arquivo DENTRO da pasta do site.
REM  Nao apaga nem sobrescreve nada: so copia.
REM ===========================================================================
cd /d "%~dp0"
if not exist "imgs\" (
  echo Pasta imgs nao encontrada. Coloque este arquivo na pasta do site, ao lado de imgs.
  pause
  exit /b 1
)
if not exist "img\" mkdir "img"
set /a COPIADAS=0
set /a FALTANDO=0

call :copiar "Logo4.png" "mascote-principal.png"
call :copiar "Logo4.png" "favicon.png"
call :copiar "Logo3.png" "mascote-secundario.png"
call :copiar "carrinhocompra1.png" "icone-carrinho.png"
call :copiar "entreoucadastreseicone.png" "icone-usuario.png"
call :copiar "pcicon.png" "icone-destaques.png"
call :copiar "Address.png" "icone-endereco.png"
call :copiar "Telephone.png" "icone-telefone.png"
call :copiar "email.png" "icone-email.png"
call :copiar "horario.png" "icone-horario.png"
call :copiar "loginperfil.png" "icone-entrar.png"
call :copiar "cadastroimg.png" "icone-cadastro.png"
call :copiar "facebook.png" "rede-facebook.png"
call :copiar "instagram.png" "rede-instagram.png"
call :copiar "youtube.png" "rede-youtube.png"
call :copiar "tiktok.png" "rede-tiktok.png"
call :copiar "banner1.jpg" "banner-1.jpg"
call :copiar "banner4.png" "banner-2.png"
call :copiar "Banner5.jpg" "banner-3.jpg"
call :copiar "Banner3.jpg" "banner-4.jpg"
call :copiar "banner2.png" "banner-5.png"
call :copiar "pc1.png" "produto-pc-gamer-rtx3060.png"
call :copiar "pc2.png" "produto-pc-escritorio-dual-core.png"
call :copiar "pc3.png" "produto-pc-gamer-ryzen9-5900x.png"
call :copiar "pc4.png" "produto-pc-gamer-ryzen5-5600g.png"
call :copiar "pc5.png" "produto-notebook-intel.png"
call :copiar "pc6.png" "produto-computador-completo.png"
call :copiar "pc7.png" "produto-pc-gamer-nitro-x.png"
call :copiar "pc8.png" "produto-pc-profissional.png"
call :copiar "pc9.png" "produto-computador-gamer.png"
call :copiar "NotebookGamer.png" "produto-notebook-gamer.png"
call :copiar "x360.png" "produto-controle-xbox-360.png"
call :copiar "playstation5.webp" "produto-playstation-5.webp"
call :copiar "Headset7.1.webp" "produto-headset-gamer-7-1.webp"
call :copiar "XBoxSX.webp" "produto-xbox-series-x.webp"
call :copiar "VolanteGamer.webp" "produto-volante-gamer.webp"
call :copiar "NintendoSwitch-removebg-preview.png" "produto-nintendo-switch-oled.png"
call :copiar "SuporteHeadset.webp" "produto-suporte-headset.webp"
call :copiar "mininintendo.webp" "produto-super-nintendo-mini.webp"
call :copiar "monitor144hz.webp" "produto-monitor-gamer-144hz.webp"
call :copiar "playstation2.webp" "produto-playstation-2-slim.webp"
call :copiar "MonitorLed.png" "produto-monitor-24-led.png"
call :copiar "MouseGamer.png" "produto-mouse-gamer.png"
call :copiar "Headset.png" "produto-headset.png"
call :copiar "gtx1080.png" "produto-gtx1080.png"
call :copiar "cadeira.png" "produto-cadeira-office.png"
call :copiar "Computadores.computadores.png" "icone-computadores.png"
call :copiar "pc01.png" "produto-pc-escritorio.png"
call :copiar "pc02.png" "produto-pc-gamer-basico.png"
call :copiar "pc03.png" "produto-computador-ideal.png"
call :copiar "pc04.png" "produto-computador-produtivo.png"
call :copiar "pc05.png" "produto-pc-economico.png"
call :copiar "pc06.png" "produto-pc-ultra-performance.png"
call :copiar "pc07.png" "produto-pc-domestico.png"
call :copiar "pc08.png" "produto-pc-workstation.png"
call :copiar "pc09.png" "produto-pc-essencial.png"
call :copiar "placamaeicon.png" "icone-hardware.png"
call :copiar "Ryzen 75800x.png" "produto-ryzen7-5800x.png"
call :copiar "inteli510400f.png" "produto-intel-i5-10400f.png"
call :copiar "SSDGiga.png" "produto-ssd-aorus-512gb.png"
call :copiar "Asusb550.png" "produto-placa-mae-asus-b550.png"
call :copiar "Ram.png" "produto-memoria-aorus-ddr5.png"
call :copiar "Fonte.png" "produto-fonte-rm1000x.png"
call :copiar "RXVega.png" "produto-radeon-rx-vega-64.png"
call :copiar "Rtx2080ti.png" "produto-rtx2080-ti.png"
call :copiar "mouseiconpng.png" "icone-perifericos.png"
call :copiar "tecladomecanico.png" "produto-teclado-mecanico.png"
call :copiar "webcam.png" "produto-webcam-1080p.png"
call :copiar "caixadesom.png" "produto-caixa-de-som-usb.png"
call :copiar "Mousepad.png" "produto-mousepad-gamer.png"
call :copiar "impressora.png" "produto-impressora-multifuncional.png"
call :copiar "suportemonitor.png" "produto-suporte-monitor.png"
call :copiar "escritoriopng.png" "icone-escritorio.png"
call :copiar "Cadeiraergonomica.png" "produto-cadeira-ergonomica-executiva.png"
call :copiar "mesaescritorio.png" "produto-mesa-escritorio-gavetas.png"
call :copiar "Mesaescritorio2.png" "produto-mesa-compacta.png"
call :copiar "organizadormesa.png" "produto-organizador-de-mesa.png"
call :copiar "luminaria.png" "produto-luminaria-de-mesa.png"
call :copiar "mesaescritorio3.png" "produto-mesa-executiva.png"
call :copiar "filtro.png" "produto-estabilizador-500va.png"
call :copiar "protetortela.png" "produto-protetor-de-tela.png"

echo.
echo %COPIADAS% imagem(ns) copiada(s) para img\   ^|   %FALTANDO% nao encontrada(s) em imgs\
pause
exit /b 0

:copiar
if exist "img\%~2" goto :eof
if not exist "imgs\%~1" (
  echo FALTA  imgs\%~1
  set /a FALTANDO+=1
  goto :eof
)
copy /Y "imgs\%~1" "img\%~2" >nul
echo ok     %~1  -^>  img\%~2
set /a COPIADAS+=1
goto :eof
