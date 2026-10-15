"""
GameMania 2.0 — front-end estático servido pela API (somente em desenvolvimento).

Em produção quem serve o site é o Nginx (ver README → Produção). Em dev, com
GM_SERVE_FRONTEND=true, o FastAPI monta a pasta frontend/ na raiz e esta classe
cuida das rotas que não existem:

  • /api/...           → JSON {"detail": "Não encontrado"} com 404 (nunca a página HTML:
                         o front-end chama a API com fetch e espera JSON);
  • qualquer outra     → frontend/404.html com status 404 (o navegador mostra a página
                         amigável, e buscadores/monitoramento enxergam o erro real).

Caminhos relativos × rota aninhada: as páginas usam caminhos RELATIVOS (css/, img/…)
para abrirem também com duplo clique. Em /pasta/inexistente esses caminhos virariam
/pasta/css/… (quebrando o estilo). Por isso, só nesse caso, inserimos <base href="/">
logo depois do <head> — permitido pela CSP (base-uri 'self'). O gm-ui.js trata os
links "#ancora" da 404 para continuarem na mesma página mesmo com o <base>.
"""
from __future__ import annotations

import anyio
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

PAGINA_404 = "404.html"
BASE_RAIZ = '<base href="/">'


class FrontendEstatico(StaticFiles):
    """StaticFiles com 404 amigável para o site e 404 em JSON para a API."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # path chega sem a barra inicial (ex.: "api/v1/xyz", "pcgamer.html", "a/b/c")
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Não encontrado"}, status_code=404)
        try:
            resposta = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            resposta = None
        if resposta is not None and resposta.status_code != 404:
            return resposta
        return await self._pagina_nao_encontrada(path, scope)

    async def _pagina_nao_encontrada(self, path: str, scope: Scope) -> Response:
        full_path, stat_result = await anyio.to_thread.run_sync(self.lookup_path, PAGINA_404)
        if not stat_result:
            raise StarletteHTTPException(status_code=404)
        html = await anyio.Path(full_path).read_text(encoding="utf-8")
        if "/" in path.strip("/"):                       # rota aninhada → ancora os caminhos relativos na raiz
            html = html.replace("<head>", "<head>\n  " + BASE_RAIZ, 1)
        resposta = HTMLResponse(html, status_code=404)
        resposta.headers["Cache-Control"] = "no-store"   # um 404 de hoje pode virar página amanhã
        return resposta                                  # em HEAD o servidor (uvicorn) descarta o corpo
