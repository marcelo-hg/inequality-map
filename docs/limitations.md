# Limitações

- Disponibilidade mundial não significa dados confiáveis em todos os países ou anos. O relatório inclui a grade país × ano × série e explicita ausências.
- A WID pode publicar distribuições estimadas ou imputadas. Preservar a proveniência não transforma essas distribuições em medições diretas.
- O período padrão inclui o ano corrente, mesmo quando as fontes ainda não o publicaram. Anos vazios permanecem vazios.
- A carga por país não é um snapshot transacional da fonte: arquivos podem ter datas de atualização diferentes. Os arquivos efetivamente usados e seus hashes são congelados localmente.
- Renda média de um intervalo não identifica a distribuição dentro desse intervalo. Não se calculam percentuais de ganhadores ou perdedores nesta etapa.
- Renda PPP é comparável apenas com definições, unidades populacionais e bases monetárias compatíveis. Não há harmonização automática entre bases de preços diferentes.
- Códigos nacionais históricos sem ISO atual são conservados fora da dimensão ISO, com alerta. Não são fundidos automaticamente com países sucessores.
- Não há reconstrução de curvas, preenchimento com WIID, demografia UN adicional, IMF ou website nesta entrega. Os mapas SVG estáticos usam fronteiras Natural Earth e não substituem uma interface cartográfica interativa.
- Os dados brutos completos por país podem ocupar vários gigabytes antes da compressão. Um download mundial exige tempo e espaço; os arquivos locais são comprimidos sem perda e os downloads concluídos são reutilizados na retomada.
- Acesso de escrita simultâneo à mesma captura de download não é suportado. Use uma captura por processo. Leitores devem resolver o ponteiro da construção uma vez para manter consistência entre os artefatos.
